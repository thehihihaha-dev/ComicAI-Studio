import json
from typing import Any

from app.services.ollama_text import call_text_model


ANALYZER_VERSION = "story_analyzer.v1"


def analyze_story(
    story_input: dict[str, Any],
    max_retries: int = 2,
) -> dict[str, Any]:
    _validate_story_input_status(story_input)
    if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
        raise ValueError("max_retries must be a non-negative integer.")

    source_json = json.dumps(
        story_input,
        ensure_ascii=False,
        indent=2,
    )
    prompt = f"""
You are ComicAI Studio's grounded story analyzer.

You receive STRUCTURED STORY INPUT containing ordered comic pages and
authoritative dialogues. Analyze only that input. Do not perform OCR and do
not assume facts that are not supported by the supplied dialogue sources.

STORY INPUT:

{source_json}

Tasks:
- Identify characters explicitly mentioned by name.
- A standalone displayed name is valid evidence that the named character
  exists, even when it does not prove who speaks another region.
- Game titles, place names, achievement names and UI labels are not characters.
- Identify factual story events and the main progression.
- Give every event an emotion/mood and an importance score from 0.0 to 1.0.
- Attach source references to every character and every atomic factual claim.
- A character source must contain the character's explicit name.
- Split every event into atomic claims. Each claim must express one independently
  supportable factual proposition and list every region needed for that claim.
- The event summary may only combine facts present in its claims.
- Preserve materially relevant conditions or qualifiers from adjacent primary
  regions and cite those regions; do not silently drop them to reduce coverage.
- Do not attribute speech or actions to a named character unless the supplied
  evidence explicitly proves that attribution. Use neutral wording otherwise.
- Uncertain speaker identity is NOT a reason to discard an otherwise factual
  event. Describe it neutrally, for example: "A character says they married
  in the game."
- Use evidence_text for facts. Never use excluded_text as story evidence.
- Treat dialogue, narration and thought as primary evidence. Treat game_ui as
  contextual evidence and use it only when narratively relevant.
- Classify each event as main_story or supporting_context. Descriptions of the
  setting and standalone system/UI notifications are normally supporting_context.
- main_progression may contain only main_story event IDs.
- Do not return empty events when STORY INPUT contains factual primary story
  evidence. Exclude unsupported attribution, not the supported event itself.
- Extract the factual development from primary evidence with neutral subjects.
  Preserve useful setting or UI facts as supporting_context instead of placing
  them in main_progression.
- Coverage example: if one region says "I married" and the next says "in the
  game", use separate atomic claims or one claim citing BOTH region IDs.
- claim_type must be one of: fact, speaker_attribution, actor_attribution,
  causal_relation. speaker_attribution and actor_attribution require subject.
- Use causal_relation only when the cited text explicitly states causality.
  Adjacent UI notifications do not prove that one caused the other.
- Do not hide attribution or causality inside a generic fact claim.
- Use only asset_id, page_order and region_id values present in STORY INPUT.
- If speaker identity, relationship, timeline or backstory is uncertain, omit
  it instead of guessing.
- You may summarize and paraphrase, but must not invent facts.
- IDs must be stable within this response: character_1, event_1, and so on.

Return ONLY valid JSON using this schema:

{{
  "characters": [
    {{
      "id": "character_1",
      "name": "Name explicitly present in the source",
      "sources": [
        {{
          "asset_id": "source asset id",
          "page_order": 1,
          "region_ids": [1]
        }}
      ]
    }}
  ],
  "events": [
    {{
      "id": "event_1",
      "summary": "Grounded event summary",
      "importance": 0.8,
      "emotion": "neutral",
      "story_role": "main_story",
      "claims": [
        {{
          "id": "event_1_claim_1",
          "text": "One atomic factual proposition",
          "claim_type": "fact",
          "sources": [
            {{
              "asset_id": "source asset id",
              "page_order": 1,
              "region_ids": [1]
            }}
          ]
        }}
      ]
    }}
  ],
  "main_progression": ["event_1"]
}}
"""

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 2):
        try:
            model_result = call_text_model(prompt=prompt)
            normalized = validate_story_result_structure(model_result)
            if _has_primary_evidence(story_input) and not normalized["events"]:
                raise ValueError("Story model returned no events for primary evidence.")
            break
        except (RuntimeError, TimeoutError, ValueError) as error:
            last_error = error
            if attempt > max_retries:
                raise RuntimeError(
                    f"Story Analyzer failed after {attempt} attempts: {error}"
                ) from error
    else:  # pragma: no cover - loop always returns or raises
        raise RuntimeError(f"Story Analyzer failed: {last_error}")

    return {
        "analyzer_version": ANALYZER_VERSION,
        "project_id": story_input["project_id"],
        "analysis_attempts": attempt,
        **normalized,
    }


def _has_primary_evidence(story_input: dict[str, Any]) -> bool:
    return any(
        dialogue.get("text_role", "dialogue")
        in {"dialogue", "narration", "thought"}
        and bool(dialogue.get("evidence_text", dialogue.get("final_text", "")))
        for page in story_input.get("pages", [])
        if isinstance(page, dict)
        for dialogue in page.get("dialogues", [])
        if isinstance(dialogue, dict)
    )


def validate_story_result_structure(
    result: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("Story model result must be an object.")

    characters = result.get("characters")
    events = result.get("events")
    progression = result.get("main_progression")

    if not isinstance(characters, list):
        raise ValueError("Story result characters must be a list.")
    if not isinstance(events, list):
        raise ValueError("Story result events must be a list.")
    if not isinstance(progression, list) or not all(
        isinstance(event_id, str) and event_id.strip()
        for event_id in progression
    ):
        raise ValueError("Story result main_progression must be a list of IDs.")

    normalized_characters = _validate_characters(characters)
    normalized_events = _validate_events(events)

    return {
        "characters": normalized_characters,
        "events": normalized_events,
        "main_progression": progression,
    }


def _validate_story_input_status(story_input: dict[str, Any]) -> None:
    if not isinstance(story_input, dict):
        raise ValueError("Story input must be an object.")
    if story_input.get("contract_version") != "story_input.v1":
        raise ValueError("Unsupported Story Input contract version.")
    if story_input.get("status") != "ready":
        raise ValueError(
            f"Story Input is not ready: {story_input.get('status')!r}."
        )
    if not isinstance(story_input.get("project_id"), str):
        raise ValueError("Story Input project_id must be a string.")
    if not isinstance(story_input.get("pages"), list):
        raise ValueError("Story Input pages must be a list.")


def _validate_characters(
    characters: list[Any],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for character in characters:
        if not isinstance(character, dict):
            raise ValueError("Every character must be an object.")

        character_id = _required_text(character.get("id"), "character.id")
        name = _required_text(character.get("name"), "character.name")
        if character_id in seen_ids:
            raise ValueError(f"Duplicate character id: {character_id!r}.")
        seen_ids.add(character_id)

        normalized.append(
            {
                "id": character_id,
                "name": name,
                "sources": _validate_source_shape(
                    character.get("sources"),
                    owner=f"character {character_id}",
                ),
            }
        )

    return normalized


def _validate_events(events: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Every event must be an object.")

        event_id = _required_text(event.get("id"), "event.id")
        summary = _required_text(event.get("summary"), "event.summary")
        emotion = _required_text(event.get("emotion"), "event.emotion")
        story_role = _required_text(
            event.get("story_role"),
            "event.story_role",
        )
        if story_role not in {"main_story", "supporting_context"}:
            raise ValueError(
                f"Event {event_id!r} story_role must be main_story or "
                "supporting_context."
            )
        if event_id in seen_ids:
            raise ValueError(f"Duplicate event id: {event_id!r}.")
        seen_ids.add(event_id)

        importance = event.get("importance")
        if (
            not isinstance(importance, (int, float))
            or isinstance(importance, bool)
            or not 0.0 <= float(importance) <= 1.0
        ):
            raise ValueError(
                f"Event {event_id!r} importance must be between 0.0 and 1.0."
            )

        normalized.append(
            {
                "id": event_id,
                "summary": summary,
                "importance": float(importance),
                "emotion": emotion,
                "story_role": story_role,
                "claims": _validate_claims(event.get("claims"), event_id),
            }
        )

    return normalized


def _validate_claims(claims: Any, event_id: str) -> list[dict[str, Any]]:
    if not isinstance(claims, list) or not claims:
        raise ValueError(f"Event {event_id!r} must have at least one claim.")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    allowed_types = {
        "fact",
        "speaker_attribution",
        "actor_attribution",
        "causal_relation",
    }
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError(f"Every claim for event {event_id!r} must be an object.")
        claim_id = _required_text(claim.get("id"), "claim.id")
        if claim_id in seen_ids:
            raise ValueError(f"Duplicate claim id: {claim_id!r}.")
        seen_ids.add(claim_id)
        claim_type = _required_text(claim.get("claim_type"), "claim.claim_type")
        if claim_type not in allowed_types:
            raise ValueError(f"Claim {claim_id!r} has invalid claim_type.")

        item = {
            "id": claim_id,
            "text": _required_text(claim.get("text"), "claim.text"),
            "claim_type": claim_type,
            "sources": _validate_source_shape(
                claim.get("sources"),
                owner=f"claim {claim_id}",
            ),
        }
        if claim_type in {"speaker_attribution", "actor_attribution"}:
            subject = claim.get("subject")
            if isinstance(subject, str) and subject.strip():
                item["subject"] = subject.strip()
        normalized.append(item)
    return normalized


def _validate_source_shape(
    sources: Any,
    owner: str,
) -> list[dict[str, Any]]:
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"{owner} must have at least one source.")

    normalized: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError(f"Every source for {owner} must be an object.")

        asset_id = _required_text(source.get("asset_id"), "source.asset_id")
        page_order = source.get("page_order")
        region_ids = source.get("region_ids")
        if not _is_positive_int(page_order):
            raise ValueError(f"Source page_order for {owner} is invalid.")
        if not isinstance(region_ids, list) or not region_ids or not all(
            _is_positive_int(region_id)
            for region_id in region_ids
        ):
            raise ValueError(f"Source region_ids for {owner} are invalid.")

        normalized.append(
            {
                "asset_id": asset_id,
                "page_order": page_order,
                "region_ids": region_ids,
            }
        )

    return normalized


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
