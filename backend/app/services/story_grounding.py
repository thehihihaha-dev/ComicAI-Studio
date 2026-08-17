import re
import unicodedata
from typing import Any
from app.services.performance import timed_stage


GROUNDING_VERSION = "story_grounding.v1"


def build_story_source_index(
    story_input: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if not isinstance(story_input, dict):
        raise ValueError("Story Input must be an object.")
    if story_input.get("contract_version") != "story_input.v1":
        raise ValueError("Unsupported Story Input contract version.")
    if story_input.get("status") != "ready":
        raise ValueError("Story Input must be ready before grounding.")

    pages = story_input.get("pages")
    if not isinstance(pages, list):
        raise ValueError("Story Input pages must be a list.")

    source_index: dict[str, dict[str, Any]] = {}
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("Every Story Input page must be an object.")

        asset_id = page.get("asset_id")
        page_order = page.get("page_order")
        dialogues = page.get("dialogues")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError("Story Input asset_id must be a non-empty string.")
        if not _is_positive_int(page_order):
            raise ValueError("Story Input page_order must be a positive integer.")
        if not isinstance(dialogues, list):
            raise ValueError("Story Input dialogues must be a list.")
        if asset_id in source_index:
            raise ValueError(f"Duplicate Story Input asset_id: {asset_id!r}.")

        region_ids: set[int] = set()
        region_texts: dict[int, str] = {}
        region_roles: dict[int, str] = {}
        for dialogue in dialogues:
            if not isinstance(dialogue, dict):
                raise ValueError("Every Story Input dialogue must be an object.")
            region_id = dialogue.get("region_id")
            if not _is_positive_int(region_id):
                raise ValueError("Story Input region_id must be a positive integer.")
            if region_id in region_ids:
                raise ValueError(
                    f"Duplicate region_id {region_id} for asset {asset_id!r}."
                )
            region_ids.add(region_id)
            evidence_text = dialogue.get(
                "evidence_text",
                dialogue.get("final_text", ""),
            )
            region_texts[region_id] = (
                evidence_text if isinstance(evidence_text, str) else ""
            )
            text_role = dialogue.get("text_role", "dialogue")
            region_roles[region_id] = (
                text_role if isinstance(text_role, str) else "other"
            )

        source_index[asset_id] = {
            "page_order": page_order,
            "region_ids": frozenset(region_ids),
            "region_texts": region_texts,
            "region_roles": region_roles,
        }

    return source_index


@timed_stage("story_grounding")
def ground_story_result(
    story_input: dict[str, Any],
    story_result: dict[str, Any],
) -> dict[str, Any]:
    source_index = build_story_source_index(story_input)
    if not isinstance(story_result, dict):
        raise ValueError("Story Result must be an object.")

    project_id = story_input.get("project_id")
    issues: list[dict[str, Any]] = []
    if story_result.get("project_id") != project_id:
        issues.append(
            {
                "code": "project_id_mismatch",
                "expected_project_id": project_id,
                "actual_project_id": story_result.get("project_id"),
            }
        )

    characters = story_result.get("characters", [])
    events = story_result.get("events", [])
    progression = story_result.get("main_progression", [])
    if not isinstance(characters, list):
        raise ValueError("Story Result characters must be a list.")
    if not isinstance(events, list):
        raise ValueError("Story Result events must be a list.")
    if not isinstance(progression, list):
        raise ValueError("Story Result main_progression must be a list.")

    grounded_characters: list[dict[str, Any]] = []
    unsupported_characters: list[dict[str, Any]] = []
    for character in characters:
        entity_id = _entity_id(character, "character")
        valid_sources = _validate_entity_sources(
            entity=character,
            entity_type="character",
            entity_id=entity_id,
            source_index=source_index,
            issues=issues,
        )
        if valid_sources:
            name = character.get("name", "")
            name_sources = _character_name_sources(
                name=name,
                sources=valid_sources,
                source_index=source_index,
            )
            if not name_sources:
                issues.append(
                    _entity_issue(
                        code="character_name_not_in_source",
                        entity_type="character",
                        entity_id=entity_id,
                    )
                )
                unsupported_characters.append(
                    {
                        "id": entity_id,
                        "name": name,
                        "reason": "No source contains character name evidence.",
                    }
                )
                continue
            grounded_characters.append(
                {
                    "id": entity_id,
                    "name": name,
                    "sources": name_sources,
                }
            )
        else:
            unsupported_characters.append(
                {
                    "id": entity_id,
                    "name": character.get("name", ""),
                    "reason": "No valid source references.",
                }
            )

    grounded_events: list[dict[str, Any]] = []
    unsupported_events: list[dict[str, Any]] = []
    all_event_ids: set[str] = set()
    grounded_event_ids: set[str] = set()
    deattributable_names = [
        character.get("name", "")
        for character in characters
        if isinstance(character, dict)
    ]
    deattributable_names.extend(_standalone_name_candidates(source_index))
    salient_tokens = _repeated_salient_tokens(source_index)
    extracted_names = [*deattributable_names, *salient_tokens]
    for event in events:
        entity_id = _entity_id(event, "event")
        all_event_ids.add(entity_id)
        grounded_claims, unsupported_claims = _ground_event_claims(
            event=event,
            event_id=entity_id,
            source_index=source_index,
            extracted_names=extracted_names,
            deattributable_names=deattributable_names,
            issues=issues,
        )
        total_claims = len(event.get("claims", []))
        script_ready = total_claims > 0 and not unsupported_claims
        grounded_event = {
            "id": entity_id,
            "summary": event.get("summary", ""),
            "importance": event.get("importance"),
            "emotion": event.get("emotion", ""),
            "story_role": event.get("story_role", "main_story"),
            "claims": grounded_claims,
            "unsupported_claims": unsupported_claims,
            "sources": _merge_claim_sources(grounded_claims),
            "script_ready": script_ready,
        }
        grounded_events.append(grounded_event)
        if script_ready:
            grounded_event_ids.add(entity_id)
        if not grounded_claims:
            unsupported_events.append(
                {
                    "id": entity_id,
                    "summary": event.get("summary", ""),
                    "reason": "No grounded factual claims.",
                }
            )

    grounded_progression = _validate_progression(
        progression=progression,
        all_event_ids=all_event_ids,
        grounded_event_ids=grounded_event_ids,
        event_roles={
            event["id"]: event.get("story_role", "main_story")
            for event in grounded_events
        },
        issues=issues,
    )

    return {
        "grounding_version": GROUNDING_VERSION,
        "project_id": project_id,
        "characters": grounded_characters,
        "events": grounded_events,
        "main_progression": grounded_progression,
        "unsupported_characters": unsupported_characters,
        "unsupported_events": unsupported_events,
        "issues": issues,
        "summary": {
            "total_characters": len(characters),
            "grounded_characters": len(grounded_characters),
            "unsupported_characters": len(unsupported_characters),
            "total_events": len(events),
            "grounded_events": len(grounded_events),
            "unsupported_events": len(unsupported_events),
            "script_ready_events": sum(
                event["script_ready"] for event in grounded_events
            ),
        },
    }


def _ground_event_claims(
    event: dict[str, Any],
    event_id: str,
    source_index: dict[str, dict[str, Any]],
    extracted_names: list[Any],
    deattributable_names: list[Any],
    issues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    claims = event.get("claims")
    if not isinstance(claims, list) or not claims:
        issues.append(
            _entity_issue(
                code="missing_atomic_claims",
                entity_type="event",
                entity_id=event_id,
            )
        )
        return [], [{"id": None, "reason": "Event has no atomic claims."}]

    grounded: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = _entity_id(claim, "claim")
        valid_sources = _validate_entity_sources(
            entity=claim,
            entity_type="claim",
            entity_id=claim_id,
            source_index=source_index,
            issues=issues,
        )
        evaluated_claim = claim
        reason = _claim_semantic_failure(
            claim,
            valid_sources,
            source_index,
            extracted_names,
        )
        if not valid_sources:
            reason = "No valid source references."
        repair: dict[str, Any] | None = None
        if reason == "Named entity attribution is not present in the sources.":
            repair = _repair_unsupported_attribution(
                claim,
                valid_sources,
                source_index,
                deattributable_names,
            )
            if repair is not None:
                evaluated_claim = repair["claim"]
                reason = _claim_semantic_failure(
                    evaluated_claim,
                    valid_sources,
                    source_index,
                    extracted_names,
                )
        if reason:
            code = {
                "speaker_attribution": "unsupported_speaker_attribution",
                "actor_attribution": "unsupported_actor_attribution",
                "causal_relation": "unsupported_causal_inference",
            }.get(claim.get("claim_type"), "unsupported_claim")
            if reason == "Named entity attribution is not present in the sources.":
                code = "unsupported_named_attribution"
            elif reason == "Claim implies causality not stated by the sources.":
                code = "unsupported_causal_inference"
            elif reason == "Game UI evidence requires review before script use.":
                code = "game_ui_claim_requires_review"
            issues.append(
                _entity_issue(
                    code=code,
                    entity_type="claim",
                    entity_id=claim_id,
                    event_id=event_id,
                )
            )
            unsupported.append(
                {"id": claim_id, "text": claim.get("text", ""), "reason": reason}
            )
            continue

        item = {
            "id": claim_id,
            "text": evaluated_claim.get("text", ""),
            "claim_type": evaluated_claim.get("claim_type", "fact"),
            "sources": valid_sources,
        }
        if evaluated_claim.get("subject") is not None:
            item["subject"] = evaluated_claim.get("subject")
        if repair is not None:
            item.update(
                {
                    "repair_type": "remove_unsupported_attribution",
                    "original_text": claim.get("text", ""),
                    "removed_attribution": repair["removed_attribution"],
                }
            )
            issues.append(
                _entity_issue(
                    code="claim_deattributed",
                    entity_type="claim",
                    entity_id=claim_id,
                    event_id=event_id,
                    removed_attribution=repair["removed_attribution"],
                )
            )
        grounded.append(item)
    return grounded, unsupported


def _claim_semantic_failure(
    claim: dict[str, Any],
    sources: list[dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
    extracted_names: list[Any],
) -> str | None:
    claim_type = claim.get("claim_type", "fact")
    if claim_type in {"speaker_attribution", "actor_attribution"}:
        subject = _normalize_name(claim.get("subject"))
        if not subject or not _sources_contain_name(sources, source_index, subject):
            return "Source evidence does not identify the attributed subject."
    if claim_type == "causal_relation" and not _sources_state_causality(
        sources, source_index
    ):
        return "Source evidence does not explicitly state a causal relation."
    claim_text = claim.get("text", "")
    for name in extracted_names:
        normalized_name = _normalize_name(name)
        if (
            normalized_name
            and _contains_normalized_name(claim_text, normalized_name)
            and not _sources_contain_name(sources, source_index, normalized_name)
        ):
            return "Named entity attribution is not present in the sources."
    if _text_states_causality(claim_text) and not _sources_state_causality(
        sources, source_index
    ):
        return "Claim implies causality not stated by the sources."
    if _sources_include_role(sources, source_index, "game_ui"):
        return "Game UI evidence requires review before script use."
    return None


def _repair_unsupported_attribution(
    claim: dict[str, Any],
    sources: list[dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
    deattributable_names: list[Any],
) -> dict[str, Any] | None:
    if not sources or claim.get("claim_type") == "causal_relation":
        return None
    text = claim.get("text")
    if not isinstance(text, str) or not text.strip():
        return None

    unsupported: list[str] = []
    seen: set[str] = set()
    for name in deattributable_names:
        normalized = _normalize_name(name)
        if (
            normalized
            and normalized not in seen
            and _contains_normalized_name(text, normalized)
            and not _sources_contain_name(sources, source_index, normalized)
        ):
            unsupported.append(str(name).strip())
            seen.add(normalized)
    if len(unsupported) != 1:
        return None

    name = unsupported[0]
    repaired_text, replacements = re.subn(
        rf"(?<![\w]){re.escape(name)}(?:[’']s)?(?![\w])",
        "a character",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    if replacements != 1 or repaired_text.strip() == text.strip():
        return None
    repaired_text = repaired_text.strip()
    if repaired_text.startswith("a character"):
        repaired_text = "A character" + repaired_text[len("a character"):]
    repaired_claim = {**claim, "text": repaired_text, "claim_type": "fact"}
    repaired_claim.pop("subject", None)
    return {"claim": repaired_claim, "removed_attribution": name}


def _sources_include_role(
    sources: list[dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
    role: str,
) -> bool:
    return any(
        source_index[source["asset_id"]]["region_roles"].get(region_id) == role
        for source in sources
        for region_id in source["region_ids"]
    )


def _standalone_name_candidates(
    source_index: dict[str, dict[str, Any]],
) -> list[str]:
    candidates: list[str] = []
    for page in source_index.values():
        for text in page.get("region_texts", {}).values():
            if not isinstance(text, str):
                continue
            words = re.findall(r"[\wÀ-ỹ]+", text, flags=re.UNICODE)
            if len(words) == 1 and len(text.strip()) <= 30 and not re.search(
                r"[!?]", text
            ):
                candidates.append(text.strip())
    return candidates


def _repeated_salient_tokens(
    source_index: dict[str, dict[str, Any]],
) -> list[str]:
    token_regions: dict[str, int] = {}
    for page in source_index.values():
        for text in page.get("region_texts", {}).values():
            normalized = _normalize_name(text)
            tokens = {
                token
                for token in re.findall(r"[A-Z0-9]+", normalized)
                if len(token) >= 4 and not token.isdigit()
            }
            for token in tokens:
                token_regions[token] = token_regions.get(token, 0) + 1
    return sorted(
        token for token, region_count in token_regions.items() if region_count >= 2
    )


def _sources_contain_name(
    sources: list[dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
    normalized_name: str,
) -> bool:
    return any(
        _contains_normalized_name(
            source_index[source["asset_id"]]["region_texts"].get(region_id, ""),
            normalized_name,
        )
        for source in sources
        for region_id in source["region_ids"]
    )


def _sources_state_causality(
    sources: list[dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
) -> bool:
    text = " ".join(
        source_index[source["asset_id"]]["region_texts"].get(region_id, "")
        for source in sources
        for region_id in source["region_ids"]
    )
    return _text_states_causality(text)


def _text_states_causality(text: Any) -> bool:
    normalized = _normalize_name(text)
    causal_patterns = (
        r"\bVI\b",
        r"\bBOI\b",
        r"\bNHO\b",
        r"DAN DEN",
        r"CHO PHEP",
        r"\bBECAUSE\b",
        r"\bTHEREFORE\b",
        r"RESULTS? IN",
        r"\bCAUSES?\b",
        r"\bGRANTS?\b",
    )
    return any(re.search(pattern, normalized) for pattern in causal_patterns)


def _merge_claim_sources(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, int], set[int]] = {}
    order: list[tuple[str, int]] = []
    for claim in claims:
        for source in claim["sources"]:
            key = (source["asset_id"], source["page_order"])
            if key not in merged:
                merged[key] = set()
                order.append(key)
            merged[key].update(source["region_ids"])
    return [
        {"asset_id": key[0], "page_order": key[1], "region_ids": sorted(merged[key])}
        for key in order
    ]


def _validate_entity_sources(
    entity: dict[str, Any],
    entity_type: str,
    entity_id: str,
    source_index: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sources = entity.get("sources")
    if not isinstance(sources, list) or not sources:
        issues.append(
            _entity_issue(
                code="missing_source_references",
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )
        return []

    valid_sources: list[dict[str, Any]] = []
    seen_sources: set[tuple[str, int, tuple[int, ...]]] = set()

    for source in sources:
        if not isinstance(source, dict):
            issues.append(
                _entity_issue(
                    code="invalid_source_shape",
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
            )
            continue

        asset_id = source.get("asset_id")
        page_order = source.get("page_order")
        region_ids = source.get("region_ids")
        if (
            not isinstance(asset_id, str)
            or not asset_id.strip()
            or not _is_positive_int(page_order)
            or not isinstance(region_ids, list)
            or not region_ids
            or not all(_is_positive_int(region_id) for region_id in region_ids)
        ):
            issues.append(
                _entity_issue(
                    code="invalid_source_shape",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    asset_id=asset_id,
                )
            )
            continue

        indexed_source = source_index.get(asset_id)
        if indexed_source is None:
            issues.append(
                _entity_issue(
                    code="invalid_asset_reference",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    asset_id=asset_id,
                )
            )
            continue

        if page_order != indexed_source["page_order"]:
            issues.append(
                _entity_issue(
                    code="wrong_page_order",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    asset_id=asset_id,
                    page_order=page_order,
                    expected_page_order=indexed_source["page_order"],
                )
            )
            continue

        unique_region_ids = sorted(set(region_ids))
        if len(unique_region_ids) != len(region_ids):
            issues.append(
                _entity_issue(
                    code="duplicate_region_reference",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    asset_id=asset_id,
                )
            )

        invalid_region_ids = [
            region_id
            for region_id in unique_region_ids
            if region_id not in indexed_source["region_ids"]
        ]
        if invalid_region_ids:
            for region_id in invalid_region_ids:
                issues.append(
                    _entity_issue(
                        code="invalid_region_reference",
                        entity_type=entity_type,
                        entity_id=entity_id,
                        asset_id=asset_id,
                        page_order=page_order,
                        region_id=region_id,
                    )
                )
            continue

        signature = (asset_id, page_order, tuple(unique_region_ids))
        if signature in seen_sources:
            issues.append(
                _entity_issue(
                    code="duplicate_source_reference",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    asset_id=asset_id,
                    page_order=page_order,
                )
            )
            continue

        seen_sources.add(signature)
        valid_sources.append(
            {
                "asset_id": asset_id,
                "page_order": page_order,
                "region_ids": unique_region_ids,
            }
        )

    return valid_sources


def _validate_progression(
    progression: list[Any],
    all_event_ids: set[str],
    grounded_event_ids: set[str],
    event_roles: dict[str, str],
    issues: list[dict[str, Any]],
) -> list[str]:
    result: list[str] = []
    seen_ids: set[str] = set()

    for event_id in progression:
        if not isinstance(event_id, str) or not event_id.strip():
            issues.append(
                {
                    "code": "invalid_progression_event_id",
                    "event_id": event_id,
                }
            )
            continue

        event_id = event_id.strip()
        if event_id in seen_ids:
            issues.append(
                {
                    "code": "duplicate_progression_event",
                    "event_id": event_id,
                }
            )
            continue
        seen_ids.add(event_id)

        if event_id not in all_event_ids:
            issues.append(
                {
                    "code": "nonexistent_progression_event",
                    "event_id": event_id,
                }
            )
            continue
        if event_id not in grounded_event_ids:
            issues.append(
                {
                    "code": "unsupported_progression_event",
                    "event_id": event_id,
                }
            )
            continue
        if event_roles.get(event_id) != "main_story":
            issues.append(
                {
                    "code": "contextual_progression_event",
                    "event_id": event_id,
                }
            )
            continue

        result.append(event_id)

    return result


def _character_name_sources(
    name: Any,
    sources: list[dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_name = _normalize_name(name)
    if not normalized_name:
        return []

    supported: list[dict[str, Any]] = []
    for source in sources:
        page = source_index[source["asset_id"]]
        texts = page.get("region_texts", {})
        if any(
            _contains_normalized_name(texts.get(region_id, ""), normalized_name)
            for region_id in source["region_ids"]
        ):
            supported.append(source)
    return supported


def _normalize_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(char for char in decomposed if not unicodedata.combining(char))
        .upper()
        .split()
    )


def _contains_normalized_name(text: Any, normalized_name: str) -> bool:
    normalized_text = _normalize_name(text)
    return re.search(
        rf"(?<![A-Z0-9]){re.escape(normalized_name)}(?![A-Z0-9])",
        normalized_text,
    ) is not None


def _entity_id(entity: Any, entity_type: str) -> str:
    if not isinstance(entity, dict):
        raise ValueError(f"Every {entity_type} must be an object.")
    entity_id = entity.get("id")
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise ValueError(f"Every {entity_type} must have a non-empty id.")
    return entity_id.strip()


def _entity_issue(
    code: str,
    entity_type: str,
    entity_id: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "entity_type": entity_type,
        "entity_id": entity_id,
        **{
            key: value
            for key, value in details.items()
            if value is not None
        },
    }


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
