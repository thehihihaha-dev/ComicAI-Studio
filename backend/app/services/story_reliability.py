import json
import hashlib
import re
import unicodedata
from typing import Any

from app.services.ollama_text import call_text_model
from app.services.story_analyzer import analyze_story, validate_story_result_structure
from app.services.story_grounding import ground_story_result
from app.services.performance import measure_stage, model_call_context, timed_stage
from app.services.model_runtime import generation_option_overrides


PRIMARY_ROLES = {"dialogue", "narration", "thought"}
CONTEXT_ROLES = {"game_ui", "other"}
EXCLUDED_ROLES = {"translator_note", "sfx"}
COVERAGE_RECOVERY_NUM_PREDICT = 2048
NON_STORY_REASON_CODES = frozenset(
    {
        "standalone_label",
        "repeated_information",
        "non_story_ui",
        "greeting_or_filler",
        "sfx_or_annotation",
        "redundant_context",
        "no_factual_story_content",
    }
)


@timed_stage("reliability_total")
def run_reliable_story_analysis(
    story_input: dict[str, Any],
    analyzer_max_retries: int = 2,
) -> dict[str, Any]:
    analyzed = analyze_story(story_input, max_retries=analyzer_max_retries)
    grounded = ground_story_result(story_input, analyzed)
    with measure_stage("coverage_calculation"):
        before = build_story_coverage(story_input, grounded)

    recovery_attempts = 0
    recovery_result = {"events": [], "non_story_relevant": []}
    merged = analyzed
    if before["important_uncovered_regions"]:
        recovery_attempts = 1
        with measure_stage("coverage_recovery"):
            recovery_result = recover_story_coverage(
                story_input, grounded, before["important_uncovered_regions"]
            )
        merged = merge_story_recovery(analyzed, recovery_result)
        grounded = ground_story_result(story_input, merged)

    with measure_stage("coverage_calculation"):
        after = build_story_coverage(
            story_input, grounded, recovery_result.get("non_story_relevant", [])
        )
    return {
        "reliability_version": "story_reliability.v1",
        "project_id": story_input.get("project_id"),
        "analysis_attempts": analyzed.get("analysis_attempts", 1),
        "recovery_attempts": recovery_attempts,
        "analyzer_result": merged,
        "grounded_result": grounded,
        "coverage_before_recovery": before,
        "recovery_result": recovery_result,
        "coverage": after,
    }


def build_story_coverage(
    story_input: dict[str, Any],
    grounded_result: dict[str, Any],
    non_story_relevant: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    regions = _coverage_regions(story_input)
    covered_keys = _grounded_region_keys(grounded_result)
    marked_non_story = {
        _region_key(item)
        for item in (non_story_relevant or [])
        if _valid_region_reference(item)
    }

    for region in regions:
        key = _region_key(region)
        if region["category"] == "primary" and _is_name_only(
            region["evidence_text"]
        ):
            marked_non_story.add(key)

    eligible = [region for region in regions if region["category"] != "excluded"]
    important = [region for region in eligible if region["category"] == "primary"]
    covered = [
        region
        for region in eligible
        if _region_key(region) in covered_keys
        and _region_key(region) not in marked_non_story
    ]
    non_story = [
        region for region in eligible if _region_key(region) in marked_non_story
    ]
    important_uncovered = [
        region
        for region in important
        if _region_key(region) not in covered_keys
        and _region_key(region) not in marked_non_story
    ]
    optional_context = [
        region
        for region in eligible
        if region["category"] == "context"
        and _region_key(region) not in covered_keys
    ]
    resolved_important = sum(
        _region_key(region) in covered_keys or _region_key(region) in marked_non_story
        for region in important
    )
    score = resolved_important / len(important) if important else 1.0

    return {
        "eligible_regions": len(eligible),
        "important_regions": len(important),
        "covered_regions": len(covered),
        "non_story_relevant_regions": len(non_story),
        "unresolved_regions": len(important_uncovered),
        "optional_context_regions": len(optional_context),
        "coverage_score": round(score, 4),
        "important_uncovered_regions": important_uncovered,
        "non_story_relevant": non_story,
        "optional_context": optional_context,
    }


def recover_story_coverage(
    story_input: dict[str, Any],
    grounded_result: dict[str, Any],
    uncovered_regions: list[dict[str, Any]],
) -> dict[str, Any]:
    slots = build_recovery_slots(uncovered_regions, grounded_result)
    prompt = _fixed_slot_recovery_prompt(slots, grounded_result)
    with generation_option_overrides({"num_predict": COVERAGE_RECOVERY_NUM_PREDICT}):
        with model_call_context("coverage_recovery", attempt=1):
            raw = call_text_model(prompt=prompt, json_mode=True)
    result = validate_fixed_slot_recovery(
        raw,
        slots,
        story_input=story_input,
        grounded_result=grounded_result,
    )
    result["fixed_slots"] = slots
    result["initial_response"] = raw
    result["recovery_path"] = "single_fixed_slot_call"
    return result


def build_recovery_slots(
    uncovered_regions: list[dict[str, Any]],
    grounded_result: dict[str, Any],
) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int, int]] = set()
    existing_event_ids = {
        event.get("id") for event in grounded_result.get("events", [])
    }
    for index, region in enumerate(uncovered_regions, start=1):
        key = _region_key(region)
        if key in seen_keys:
            raise ValueError(f"Duplicate uncovered region cannot create slots: {key!r}.")
        seen_keys.add(key)
        asset_suffix = hashlib.sha256(key[0].encode("utf-8")).hexdigest()[:8]
        event_id = f"coverage_recovery_p{key[1]}_r{key[2]}_{asset_suffix}"
        if event_id in existing_event_ids:
            raise ValueError(f"Coverage recovery event ID collision: {event_id!r}.")
        closest_text, overlap = _closest_grounded_claim(
            _semantic_tokens(region.get("evidence_text", "")), grounded_result
        )
        slots.append(
            {
                "slot_id": f"slot_{index}",
                "asset_id": key[0],
                "page_order": key[1],
                "region_id": key[2],
                "event_id": event_id,
                "evidence_text": region.get("evidence_text", ""),
                "text_role": region.get("text_role", "other"),
                "overlap_evidence": {
                    "closest_grounded_claim": closest_text,
                    "normalized_token_overlap": round(overlap, 4),
                    "equivalent_grounded_proposition": overlap >= 0.8,
                },
            }
        )
    return slots


def validate_fixed_slot_recovery(
    result: dict[str, Any],
    slots: list[dict[str, Any]],
    *,
    story_input: dict[str, Any],
    grounded_result: dict[str, Any],
) -> dict[str, Any]:
    raw_outputs = result.get("slots") if isinstance(result, dict) else None
    if not isinstance(raw_outputs, list):
        raw_outputs = []
    slots_by_id = {slot["slot_id"]: slot for slot in slots}
    returned_ids = [
        item.get("slot_id") for item in raw_outputs
        if isinstance(item, dict) and isinstance(item.get("slot_id"), str)
    ]
    duplicates = {slot_id for slot_id in returned_ids if returned_ids.count(slot_id) > 1}
    unknown = sorted({slot_id for slot_id in returned_ids if slot_id not in slots_by_id})
    events: list[dict[str, Any]] = []
    non_story: list[dict[str, Any]] = []
    progression: list[str] = []
    issues: list[dict[str, Any]] = []
    valid_slot_ids: set[str] = set()
    structurally_valid_slot_ids: set[str] = set()
    known_returned = {slot_id for slot_id in returned_ids if slot_id in slots_by_id}
    existing_event_ids = {
        event.get("id") for event in grounded_result.get("events", [])
    }
    forbidden_fields = {
        "asset_id", "page_order", "region_id", "event_id", "source", "sources"
    }

    for unknown_id in unknown:
        issues.append({"code": "unknown_recovery_slot", "slot_id": unknown_id})
    for slot_id in sorted(duplicates):
        issues.append({"code": "duplicate_recovery_slot", "slot_id": slot_id})

    for output in raw_outputs:
        if not isinstance(output, dict):
            issues.append({"code": "invalid_recovery_slot_output"})
            continue
        slot_id = output.get("slot_id")
        slot = slots_by_id.get(slot_id)
        if slot is None or slot_id in duplicates:
            continue
        supplied_backend_fields = set(forbidden_fields & output.keys())
        for claim in output.get("claims", []):
            if isinstance(claim, dict):
                supplied_backend_fields.update(forbidden_fields & claim.keys())
        flattened_fields = sorted(supplied_backend_fields)
        if flattened_fields:
            issues.append(
                {
                    "code": "model_supplied_backend_owned_field",
                    "slot_id": slot_id,
                    "fields": flattened_fields,
                }
            )
            continue
        decision = output.get("decision")
        if decision == "non_story_relevant":
            reason_code = output.get("reason_code")
            if reason_code not in NON_STORY_REASON_CODES:
                issues.append(
                    {"code": "invalid_non_story_reason_code", "slot_id": slot_id,
                     "reason_code": reason_code}
                )
                continue
            structurally_valid_slot_ids.add(slot_id)
            compatible, compatibility = _reason_code_compatible(
                reason_code,
                {
                    "evidence_text": slot["evidence_text"],
                    "text_role": slot["text_role"],
                },
                grounded_result,
            )
            if not compatible:
                issues.append(
                    {"code": "incompatible_non_story_reason_code", "slot_id": slot_id,
                     "reason_code": reason_code, "compatibility": compatibility}
                )
                continue
            non_story.append(
                {**_reference_only(slot), "reason_code": reason_code, "slot_id": slot_id}
            )
            valid_slot_ids.add(slot_id)
            continue
        if decision != "new_event":
            issues.append(
                {"code": "invalid_fixed_slot_decision", "slot_id": slot_id,
                 "decision": decision}
            )
            continue
        claims = output.get("claims")
        if not isinstance(claims, list) or not claims or not all(
            isinstance(claim, dict)
            and isinstance(claim.get("text"), str)
            and claim["text"].strip()
            for claim in claims
        ):
            issues.append({"code": "invalid_fixed_slot_claims", "slot_id": slot_id})
            continue
        structurally_valid_slot_ids.add(slot_id)
        event_id = slot["event_id"]
        if event_id in existing_event_ids or any(event.get("id") == event_id for event in events):
            issues.append(
                {"code": "coverage_recovery_event_id_collision", "slot_id": slot_id,
                 "event_id": event_id}
            )
            continue
        evidence_tokens = _semantic_tokens(slot["evidence_text"])
        unanchored_claims = [
            claim["text"] for claim in claims
            if not (_semantic_tokens(claim["text"]) & evidence_tokens)
        ]
        if unanchored_claims:
            issues.append(
                {
                    "code": "fixed_slot_claim_not_anchored_to_evidence",
                    "slot_id": slot_id,
                    "event_id": event_id,
                    "claim_count": len(unanchored_claims),
                }
            )
            continue
        event = _event_from_fixed_slot(slot, claims)
        checked = ground_story_result(
            story_input,
            {"project_id": story_input.get("project_id"), "characters": [],
             "events": [event], "main_progression": [event_id]},
        )
        checked_event = checked.get("events", [{}])[0]
        if checked_event.get("script_ready") is not True:
            issues.append(
                {"code": "unsafe_fixed_slot_event", "slot_id": slot_id,
                 "event_id": event_id, "grounding_issues": checked.get("issues", [])}
            )
            continue
        events.append(event)
        progression.append(event_id)
        valid_slot_ids.add(slot_id)

    missing_ids = [slot["slot_id"] for slot in slots if slot["slot_id"] not in valid_slot_ids]
    structural_missing = [
        slot["slot_id"] for slot in slots
        if slot["slot_id"] not in structurally_valid_slot_ids
    ]
    semantic_rejections = sum(
        issue.get("code") in {
            "incompatible_non_story_reason_code", "unsafe_fixed_slot_event",
            "fixed_slot_claim_not_anchored_to_evidence",
        }
        for issue in issues
    )
    requested = len(slots)
    return {
        "events": events,
        "main_progression": progression,
        "non_story_relevant": non_story,
        "issues": issues,
        "unresolved": [slot for slot in slots if slot["slot_id"] in missing_ids],
        "valid_decision_keys": [_reference_only(slot) for slot in slots if slot["slot_id"] in valid_slot_ids],
        "slot_metrics": {
            "requested_slots": requested,
            "returned_known_slots": len(known_returned),
            "structurally_valid_slots": len(structurally_valid_slot_ids),
            "valid_slots": len(valid_slot_ids),
            "missing_slots": structural_missing,
            "unresolved_slots": missing_ids,
            "duplicate_slots": sorted(duplicates & slots_by_id.keys()),
            "unknown_slots": unknown,
            "semantic_rejections": semantic_rejections,
            "structural_completeness": (
                round(len(structurally_valid_slot_ids) / requested, 4) if requested else 1.0
            ),
            "decision_completeness": (
                round(len(valid_slot_ids) / requested, 4) if requested else 1.0
            ),
        },
    }


def _event_from_fixed_slot(
    slot: dict[str, Any], claims: list[dict[str, Any]]
) -> dict[str, Any]:
    event_id = slot["event_id"]
    normalized_claims = [
        {
            "id": f"{event_id}_claim_{index}",
            "text": claim["text"].strip(),
            "claim_type": "fact",
            "sources": [
                {"asset_id": slot["asset_id"], "page_order": slot["page_order"],
                 "region_ids": [slot["region_id"]]}
            ],
        }
        for index, claim in enumerate(claims, start=1)
    ]
    return {
        "id": event_id,
        "summary": " ".join(claim["text"] for claim in normalized_claims),
        "importance": 0.5,
        "emotion": "neutral",
        "story_role": "main_story",
        "claims": normalized_claims,
    }


def repair_recovery_result_structure(
    invalid_result: dict[str, Any],
    validation_error: ValueError,
    uncovered_regions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Repair schema only; missing semantic justification cannot be invented."""
    prompt = f"""
Repair ONLY the JSON schema of this Coverage Recovery response.
Do not add, remove, or change a disposition, event, factual claim, source, or
story meaning. For non_story_relevant, reason_code must be copied or mapped
from an EXISTING reason in the invalid response. If no justification exists,
omit that decision. Allowed reason_code values:
{json.dumps(sorted(NON_STORY_REASON_CODES))}

VALIDATION ERROR: {validation_error}
ALLOWED REGION REFERENCES:
{json.dumps([_reference_only(item) for item in uncovered_regions], separators=(",", ":"))}
INVALID RESPONSE:
{json.dumps(invalid_result, ensure_ascii=False, separators=(",", ":"))}

Return JSON only: {{"decisions": [...]}}
"""
    with generation_option_overrides({"num_predict": COVERAGE_RECOVERY_NUM_PREDICT}):
        with model_call_context("coverage_recovery_repair", attempt=1):
            return call_text_model(prompt=prompt, json_mode=True)


def validate_recovery_result(
    result: dict[str, Any],
    uncovered_regions: list[dict[str, Any]],
    *,
    story_input: dict[str, Any] | None = None,
    grounded_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(result, dict) or not isinstance(result.get("decisions"), list):
        raise ValueError("Coverage recovery must return a decisions list.")
    allowed = {_region_key(item) for item in uncovered_regions}
    decision_keys = [
        _region_key(item)
        for item in result["decisions"]
        if _valid_region_reference(item)
    ]
    duplicate_keys = {
        key for key in decision_keys if decision_keys.count(key) > 1
    }
    seen: set[tuple[str, int, int]] = set()
    resolved: set[tuple[str, int, int]] = set()
    valid_decision_keys: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    non_story: list[dict[str, Any]] = []
    progression: list[str] = []
    issues: list[dict[str, Any]] = []

    for decision in result["decisions"]:
        if not isinstance(decision, dict) or not _valid_region_reference(decision):
            issues.append({"code": "invalid_region_reference"})
            continue
        key = _region_key(decision)
        if key not in allowed:
            issues.append({"code": "unknown_region", **_reference_only(decision)})
            continue
        if key in duplicate_keys:
            if key not in seen:
                issues.append({"code": "duplicate_region_decision", **_reference_only(decision)})
            seen.add(key)
            continue
        seen.add(key)
        disposition = decision.get("disposition")
        if disposition == "non_story_relevant":
            reason_code = decision.get("reason_code")
            if not isinstance(reason_code, str) or not reason_code.strip():
                issues.append(
                    {
                        "code": "missing_non_story_reason_code",
                        **_reference_only(decision),
                    }
                )
                continue
            if reason_code not in NON_STORY_REASON_CODES:
                issues.append(
                    {
                        "code": "unknown_non_story_reason_code",
                        "reason_code": reason_code,
                        **_reference_only(decision),
                    }
                )
                continue
            source_region = next(
                item for item in uncovered_regions if _region_key(item) == key
            )
            compatible, compatibility = _reason_code_compatible(
                reason_code, source_region, grounded_result or {}
            )
            if not compatible:
                issues.append(
                    {
                        "code": "incompatible_non_story_reason_code",
                        "reason_code": reason_code,
                        "compatibility": compatibility,
                        **_reference_only(decision),
                    }
                )
                continue
            non_story.append(
                {
                    **_reference_only(decision),
                    "reason_code": reason_code,
                }
            )
            resolved.add(key)
            valid_decision_keys.append(_reference_only(decision))
        elif disposition == "new_event":
            event = decision.get("event")
            if not isinstance(event, dict):
                issues.append(
                    {
                        "code": "missing_recovery_event",
                        **_reference_only(decision),
                    }
                )
                continue
            try:
                normalized_event = validate_story_result_structure(
                    {"characters": [], "events": [event], "main_progression": []}
                )["events"][0]
            except ValueError as error:
                issues.append(
                    {
                        "code": "invalid_recovery_event",
                        **_reference_only(decision),
                        "message": str(error),
                    }
                )
                continue
            event_source_keys = {
                (source["asset_id"], source["page_order"], region_id)
                for claim in normalized_event.get("claims", [])
                for source in claim.get("sources", [])
                for region_id in source.get("region_ids", [])
            }
            if key not in event_source_keys:
                issues.append(
                    {
                        "code": "recovery_event_does_not_cover_region",
                        "event_id": normalized_event.get("id"),
                        **_reference_only(decision),
                    }
                )
                continue
            if grounded_result and normalized_event.get("id") in {
                item.get("id") for item in grounded_result.get("events", [])
            }:
                issues.append(
                    {
                        "code": "recovery_event_id_conflict",
                        "event_id": normalized_event.get("id"),
                        **_reference_only(decision),
                    }
                )
                continue
            if story_input is not None:
                checked = ground_story_result(
                    story_input,
                    {
                        "project_id": story_input.get("project_id"),
                        "characters": [],
                        "events": [normalized_event],
                        "main_progression": (
                            [normalized_event["id"]]
                            if normalized_event.get("story_role") == "main_story"
                            else []
                        ),
                    },
                )
                checked_event = checked.get("events", [{}])[0]
                if checked_event.get("script_ready") is not True:
                    issues.append(
                        {
                            "code": "unsafe_recovery_event",
                            "event_id": normalized_event.get("id"),
                            **_reference_only(decision),
                        }
                    )
                    continue
            events.append(normalized_event)
            resolved.add(key)
            valid_decision_keys.append(_reference_only(decision))
            if normalized_event.get("story_role") == "main_story":
                progression.append(normalized_event.get("id"))
        else:
            issues.append(
                {
                    "code": "unknown_recovery_disposition",
                    "disposition": disposition,
                    **_reference_only(decision),
                }
            )

    return {
        "events": events,
        "main_progression": progression,
        "non_story_relevant": non_story,
        "issues": issues,
        "unresolved": [
            item for item in uncovered_regions if _region_key(item) not in resolved
        ],
        "valid_decision_keys": valid_decision_keys,
    }


def _reason_code_compatible(
    reason_code: str,
    region: dict[str, Any],
    grounded_result: dict[str, Any],
) -> tuple[bool, str]:
    text = region.get("evidence_text", "")
    role = region.get("text_role", "other")
    tokens = _semantic_tokens(text)
    sentence_punctuation = bool(re.search(r"[.!?;:]", text))
    if reason_code == "standalone_label":
        valid = bool(tokens) and len(tokens) <= 4 and len(text.strip()) <= 40 and not sentence_punctuation
        return valid, "requires short label-like text without sentence punctuation"
    if reason_code == "sfx_or_annotation":
        return role in {"sfx", "translator_note"}, "requires SFX or annotation role"
    if reason_code == "non_story_ui":
        ui_markers = {"system", "achievement", "unlocked", "level", "hp", "mp"}
        return role == "game_ui" or bool(tokens & ui_markers), "requires UI role or system marker"
    if reason_code in {"repeated_information", "redundant_context"}:
        threshold = 0.6 if reason_code == "repeated_information" else 0.5
        overlap = _maximum_grounded_overlap(tokens, grounded_result)
        return overlap >= threshold, f"requires grounded token overlap >= {threshold}; observed {overlap:.4f}"
    if reason_code == "greeting_or_filler":
        return bool(tokens) and len(tokens) <= 5, "requires short greeting/interjection-like text"
    if reason_code == "no_factual_story_content":
        return bool(tokens) and len(tokens) <= 2 and not any(char.isdigit() for char in text), "requires very short text with no obvious factual structure"
    return False, "reason code is not supported"


def _semantic_tokens(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return {
        token for token in re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
        if len(token) > 1
    }


def _maximum_grounded_overlap(
    source_tokens: set[str], grounded_result: dict[str, Any]
) -> float:
    if not source_tokens:
        return 0.0
    best = 0.0
    for event in grounded_result.get("events", []):
        for claim in event.get("claims", []):
            claim_tokens = _semantic_tokens(claim.get("text", ""))
            if not claim_tokens:
                continue
            overlap = len(source_tokens & claim_tokens) / len(source_tokens)
            best = max(best, overlap)
    return best


def _closest_grounded_claim(
    source_tokens: set[str], grounded_result: dict[str, Any]
) -> tuple[str | None, float]:
    closest: str | None = None
    best = 0.0
    for event in grounded_result.get("events", []):
        for claim in event.get("claims", []):
            text = claim.get("text", "")
            claim_tokens = _semantic_tokens(text)
            if not source_tokens or not claim_tokens:
                continue
            overlap = len(source_tokens & claim_tokens) / len(source_tokens)
            if overlap > best:
                closest = text
                best = overlap
    return closest, best


def _fixed_slot_recovery_prompt(
    slots: list[dict[str, Any]], grounded_result: dict[str, Any]
) -> str:
    model_slots = [
        {
            "slot_id": slot["slot_id"],
            "evidence_text": slot["evidence_text"],
            "text_role": slot["text_role"],
            "overlap_evidence": slot["overlap_evidence"],
        }
        for slot in slots
    ]
    existing_claims = [
        claim.get("text", "")
        for event in grounded_result.get("events", [])
        for claim in event.get("claims", [])
        if isinstance(claim.get("text"), str) and claim.get("text", "").strip()
    ]
    return f"""
You are ComicAI Studio's fixed-slot story coverage recovery pass.
Return exactly one output for every supplied slot_id. The backend owns all
asset, page, region, source, event and claim IDs. Never return those fields.

For factual story content choose new_event and return one or more compact,
atomic claim texts supported by that slot's evidence_text. Use neutral wording;
do not invent speaker identity, attribution, causality, timeline, or backstory.

For non-story content choose non_story_relevant with exactly one reason_code:
{json.dumps(sorted(NON_STORY_REASON_CODES))}
Repeated/redundant codes are allowed only when overlap_evidence supports them.
Do not omit slots, duplicate slots, or invent slot IDs.

FIXED SLOTS:
{json.dumps(model_slots, ensure_ascii=False, separators=(",", ":"))}

EXISTING GROUNDED CLAIM TEXTS (context only):
{json.dumps(existing_claims, ensure_ascii=False, separators=(",", ":"))}

Return JSON only:
{{"slots":[
{{"slot_id":"slot_1","decision":"new_event","claims":[{{"text":"..."}}]}},
{{"slot_id":"slot_2","decision":"non_story_relevant","reason_code":"standalone_label"}}
]}}
"""


def _repairable_legacy_reason_decisions(
    raw: dict[str, Any], result: dict[str, Any]
) -> list[dict[str, Any]]:
    unresolved = {_region_key(item) for item in result.get("unresolved", [])}
    decisions = raw.get("decisions", []) if isinstance(raw, dict) else []
    return [
        decision
        for decision in decisions
        if _valid_region_reference(decision)
        and _region_key(decision) in unresolved
        and decision.get("disposition") == "non_story_relevant"
        and isinstance(decision.get("reason"), str)
        and decision["reason"].strip()
        and not decision.get("reason_code")
    ]


def _merge_repaired_recovery_result(
    original: dict[str, Any], repaired: dict[str, Any]
) -> dict[str, Any]:
    repaired_keys = {
        _region_key(item)
        for group in (repaired.get("events", []), repaired.get("non_story_relevant", []))
        for item in group
        if _valid_region_reference(item)
    }
    # Recovered events store their references in claims, not at event level.
    if repaired.get("events"):
        repaired_keys.update(
            (source["asset_id"], source["page_order"], region_id)
            for event in repaired["events"]
            for claim in event.get("claims", [])
            for source in claim.get("sources", [])
            for region_id in source.get("region_ids", [])
        )
    return {
        "events": [*original.get("events", []), *repaired.get("events", [])],
        "main_progression": [
            *original.get("main_progression", []),
            *repaired.get("main_progression", []),
        ],
        "non_story_relevant": [
            *original.get("non_story_relevant", []),
            *repaired.get("non_story_relevant", []),
        ],
        "issues": [
            issue
            for issue in original.get("issues", [])
            if not (
                issue.get("code") == "missing_non_story_reason_code"
                and _valid_region_reference(issue)
                and _region_key(issue) in repaired_keys
            )
        ] + repaired.get("issues", []),
        "unresolved": [
            item
            for item in original.get("unresolved", [])
            if _region_key(item) not in repaired_keys
        ],
        "valid_decision_keys": [
            *original.get("valid_decision_keys", []),
            *repaired.get("valid_decision_keys", []),
        ],
        "structural_repair_attempts": 1,
    }


def _merge_continuation_result(
    initial: dict[str, Any], continuation: dict[str, Any]
) -> dict[str, Any]:
    initial_event_ids = {event.get("id") for event in initial.get("events", [])}
    continuation_events = [
        event for event in continuation.get("events", [])
        if event.get("id") not in initial_event_ids
    ]
    rejected_conflicts = [
        event for event in continuation.get("events", [])
        if event.get("id") in initial_event_ids
    ]
    conflict_issues = [
        {"code": "recovery_event_id_conflict", "event_id": event.get("id")}
        for event in rejected_conflicts
    ]
    conflict_source_keys = {
        (source["asset_id"], source["page_order"], region_id)
        for event in rejected_conflicts
        for claim in event.get("claims", [])
        for source in claim.get("sources", [])
        for region_id in source.get("region_ids", [])
    }
    valid_continuation_keys = [
        item for item in continuation.get("valid_decision_keys", [])
        if _region_key(item) not in conflict_source_keys
    ]
    resolved_keys = {
        _region_key(item)
        for item in [*initial.get("valid_decision_keys", []), *valid_continuation_keys]
    }
    return {
        **initial,
        "events": [*initial.get("events", []), *continuation_events],
        "main_progression": [
            *initial.get("main_progression", []),
            *[
                event_id for event_id in continuation.get("main_progression", [])
                if event_id not in initial.get("main_progression", [])
                and event_id not in initial_event_ids
            ],
        ],
        "non_story_relevant": [
            *initial.get("non_story_relevant", []),
            *continuation.get("non_story_relevant", []),
        ],
        "issues": [
            *initial.get("issues", []),
            *continuation.get("issues", []),
            *conflict_issues,
        ],
        "unresolved": [
            item for item in initial.get("unresolved", [])
            if _region_key(item) not in resolved_keys
        ],
        "valid_decision_keys": [
            *initial.get("valid_decision_keys", []), *valid_continuation_keys
        ],
    }


def _grounded_context_with_recovery(
    grounded_result: dict[str, Any], recovery_result: dict[str, Any]
) -> dict[str, Any]:
    return {
        **grounded_result,
        "events": [
            *grounded_result.get("events", []),
            *recovery_result.get("events", []),
        ],
        "main_progression": [
            *grounded_result.get("main_progression", []),
            *recovery_result.get("main_progression", []),
        ],
    }


def _unresolved_recovery_result(
    uncovered_regions: list[dict[str, Any]],
    code: str,
    message: str,
    *,
    structural_repair_attempts: int,
) -> dict[str, Any]:
    return {
        "events": [],
        "main_progression": [],
        "non_story_relevant": [],
        "issues": [{"code": code, "message": message}],
        "unresolved": list(uncovered_regions),
        "structural_repair_attempts": structural_repair_attempts,
    }


def merge_story_recovery(
    story_result: dict[str, Any],
    recovery_result: dict[str, Any],
) -> dict[str, Any]:
    merged = {
        **story_result,
        "characters": list(story_result.get("characters", [])),
        "events": list(story_result.get("events", [])),
        "main_progression": list(story_result.get("main_progression", [])),
    }
    existing_ids = {event.get("id") for event in merged["events"]}
    for event in recovery_result.get("events", []):
        if event.get("id") in existing_ids:
            raise ValueError("Coverage recovery cannot overwrite an existing event.")
        existing_ids.add(event.get("id"))
        merged["events"].append(event)
    for event_id in recovery_result.get("main_progression", []):
        if event_id not in merged["main_progression"]:
            merged["main_progression"].append(event_id)
    return merged


def _coverage_regions(story_input: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for page in story_input.get("pages", []):
        for dialogue in page.get("dialogues", []):
            role = dialogue.get("text_role", "dialogue")
            category = (
                "primary" if role in PRIMARY_ROLES
                else "context" if role in CONTEXT_ROLES
                else "excluded"
            )
            result.append(
                {
                    "asset_id": page["asset_id"],
                    "page_order": page["page_order"],
                    "region_id": dialogue["region_id"],
                    "text_role": role,
                    "category": category,
                    "evidence_text": dialogue.get(
                        "evidence_text", dialogue.get("final_text", "")
                    ),
                }
            )
    return result


def _grounded_region_keys(result: dict[str, Any]) -> set[tuple[str, int, int]]:
    return {
        (source["asset_id"], source["page_order"], region_id)
        for event in result.get("events", [])
        for claim in event.get("claims", [])
        for source in claim.get("sources", [])
        for region_id in source.get("region_ids", [])
    }


def _recovery_prompt(
    story_input: dict[str, Any],
    grounded_result: dict[str, Any],
    uncovered: list[dict[str, Any]],
    *,
    continuation: bool = False,
) -> str:
    page_orders = {item["page_order"] for item in uncovered}
    nearby = _compact_nearby_context(story_input, uncovered) if continuation else [
        page for page in story_input.get("pages", [])
        if page.get("page_order") in page_orders
    ]
    return f"""
You are ComicAI Studio's limited story coverage {"continuation" if continuation else "recovery pass"}.
Do not rewrite, replace or restate existing events. Review ONLY the uncovered
regions. For each region, either create one new atomic event when it carries
missing story meaning, or mark it non_story_relevant when it is only a name,
exclamation, repetition or minor text. Use neutral wording when speaker is
unknown. Never use excluded text. Return one decision per uncovered region.

ALLOWED DISPOSITIONS AND REQUIRED FIELDS:
- non_story_relevant: asset_id, page_order, region_id, disposition, reason_code.
- new_event: asset_id, page_order, region_id, disposition, event.

reason_code must be exactly one of:
{json.dumps(sorted(NON_STORY_REASON_CODES))}
Missing or unknown reason_code leaves a region unresolved. Never classify a
region as non_story_relevant merely to improve coverage. Use new_event for
factual story content and preserve atomic claims with exact source references.

CURRENT GROUNDED STORY:
{json.dumps(grounded_result, ensure_ascii=False, separators=(",", ":"))}

UNCOVERED REGIONS:
{json.dumps(uncovered, ensure_ascii=False, separators=(",", ":"))}

NEARBY PAGE CONTEXT:
{json.dumps(nearby, ensure_ascii=False, separators=(",", ":"))}

Return ONLY JSON in this exact outer schema:
{{"decisions":[
{{"asset_id":"...","page_order":1,"region_id":1,
"disposition":"non_story_relevant","reason_code":"standalone_label"}},
{{"asset_id":"...","page_order":1,"region_id":2,
"disposition":"new_event","event":{{"id":"recovery_event_1",
"summary":"...","importance":0.5,"emotion":"neutral",
"story_role":"main_story","claims":[{{"id":"recovery_event_1_claim_1",
"text":"...","claim_type":"fact","sources":[{{"asset_id":"...",
"page_order":1,"region_ids":[2]}}]}}]}}}}
]}}
"""


def _compact_nearby_context(
    story_input: dict[str, Any], missing: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    dialogue_orders = {
        (page.get("asset_id"), page.get("page_order"), dialogue.get("region_id")):
        dialogue.get("order", dialogue.get("region_id"))
        for page in story_input.get("pages", [])
        for dialogue in page.get("dialogues", [])
    }
    missing_orders: dict[tuple[str, int], set[int]] = {}
    for item in missing:
        missing_orders.setdefault(
            (item["asset_id"], item["page_order"]), set()
        ).add(
            dialogue_orders.get(
                (item["asset_id"], item["page_order"], item["region_id"]),
                item["region_id"],
            )
        )
    compact: list[dict[str, Any]] = []
    for page in story_input.get("pages", []):
        key = (page.get("asset_id"), page.get("page_order"))
        target_orders = missing_orders.get(key)
        if not target_orders:
            continue
        dialogues = [
            dialogue for dialogue in page.get("dialogues", [])
            if any(abs(dialogue.get("order", 0) - order) <= 1 for order in target_orders)
        ]
        compact.append(
            {
                "asset_id": page.get("asset_id"),
                "page_order": page.get("page_order"),
                "dialogues": dialogues,
            }
        )
    return compact


def _reference_only(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": item.get("asset_id"),
        "page_order": item.get("page_order"),
        "region_id": item.get("region_id"),
    }


def _region_key(item: dict[str, Any]) -> tuple[str, int, int]:
    return item["asset_id"], item["page_order"], item["region_id"]


def _valid_region_reference(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("asset_id"), str)
        and isinstance(item.get("page_order"), int)
        and isinstance(item.get("region_id"), int)
    )


def _is_name_only(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    words = re.findall(r"[\wÀ-ỹ]+", text, flags=re.UNICODE)
    return len(words) == 1 and len(text.strip()) <= 30 and not re.search(r"[!?]", text)
