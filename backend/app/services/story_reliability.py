import json
import re
from typing import Any

from app.services.ollama_text import call_text_model
from app.services.story_analyzer import analyze_story, validate_story_result_structure
from app.services.story_grounding import ground_story_result


PRIMARY_ROLES = {"dialogue", "narration", "thought"}
CONTEXT_ROLES = {"game_ui", "other"}
EXCLUDED_ROLES = {"translator_note", "sfx"}


def run_reliable_story_analysis(
    story_input: dict[str, Any],
    analyzer_max_retries: int = 2,
) -> dict[str, Any]:
    analyzed = analyze_story(story_input, max_retries=analyzer_max_retries)
    grounded = ground_story_result(story_input, analyzed)
    before = build_story_coverage(story_input, grounded)

    recovery_attempts = 0
    recovery_result = {"events": [], "non_story_relevant": []}
    merged = analyzed
    if before["important_uncovered_regions"]:
        recovery_attempts = 1
        recovery_result = recover_story_coverage(
            story_input,
            grounded,
            before["important_uncovered_regions"],
        )
        merged = merge_story_recovery(analyzed, recovery_result)
        grounded = ground_story_result(story_input, merged)

    after = build_story_coverage(
        story_input,
        grounded,
        recovery_result.get("non_story_relevant", []),
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
    prompt = _recovery_prompt(story_input, grounded_result, uncovered_regions)
    raw = call_text_model(prompt=prompt)
    return validate_recovery_result(raw, uncovered_regions)


def validate_recovery_result(
    result: dict[str, Any],
    uncovered_regions: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(result, dict) or not isinstance(result.get("decisions"), list):
        raise ValueError("Coverage recovery must return a decisions list.")
    allowed = {_region_key(item) for item in uncovered_regions}
    seen: set[tuple[str, int, int]] = set()
    resolved: set[tuple[str, int, int]] = set()
    events: list[dict[str, Any]] = []
    non_story: list[dict[str, Any]] = []
    progression: list[str] = []
    issues: list[dict[str, Any]] = []

    for decision in result["decisions"]:
        if not isinstance(decision, dict) or not _valid_region_reference(decision):
            raise ValueError("Coverage recovery decision has invalid reference.")
        key = _region_key(decision)
        if key not in allowed or key in seen:
            raise ValueError("Coverage recovery decision is unknown or duplicated.")
        seen.add(key)
        disposition = decision.get("disposition")
        if disposition == "non_story_relevant":
            reason = decision.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                issues.append(
                    {
                        "code": "missing_non_story_reason",
                        "asset_id": key[0],
                        "page_order": key[1],
                        "region_id": key[2],
                    }
                )
                continue
            non_story.append(
                {
                    "asset_id": key[0],
                    "page_order": key[1],
                    "region_id": key[2],
                    "reason": reason.strip(),
                }
            )
            resolved.add(key)
        elif disposition == "new_event":
            event = decision.get("event")
            if not isinstance(event, dict):
                issues.append(
                    {
                        "code": "missing_recovery_event",
                        "asset_id": key[0],
                        "page_order": key[1],
                        "region_id": key[2],
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
                        "asset_id": key[0],
                        "page_order": key[1],
                        "region_id": key[2],
                        "message": str(error),
                    }
                )
                continue
            events.append(normalized_event)
            resolved.add(key)
            if normalized_event.get("story_role") == "main_story":
                progression.append(normalized_event.get("id"))
        else:
            raise ValueError("Unknown coverage recovery disposition.")

    return {
        "events": events,
        "main_progression": progression,
        "non_story_relevant": non_story,
        "issues": issues,
        "unresolved": [
            item for item in uncovered_regions if _region_key(item) not in resolved
        ],
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
) -> str:
    page_orders = {item["page_order"] for item in uncovered}
    nearby = [
        page for page in story_input.get("pages", [])
        if page.get("page_order") in page_orders
    ]
    return f"""
You are ComicAI Studio's limited story coverage recovery pass.
Do not rewrite, replace or restate existing events. Review ONLY the uncovered
regions. For each region, either create one new atomic event when it carries
missing story meaning, or mark it non_story_relevant when it is only a name,
exclamation, repetition or minor text. Use neutral wording when speaker is
unknown. Never use excluded text. Return one decision per uncovered region.

CURRENT GROUNDED STORY:
{json.dumps(grounded_result, ensure_ascii=False, indent=2)}

UNCOVERED REGIONS:
{json.dumps(uncovered, ensure_ascii=False, indent=2)}

NEARBY PAGE CONTEXT:
{json.dumps(nearby, ensure_ascii=False, indent=2)}

Return ONLY JSON:
{{"decisions":[{{"asset_id":"...","page_order":1,"region_id":1,
"disposition":"new_event","event":{{"id":"recovery_event_1",
"summary":"...","importance":0.5,"emotion":"neutral",
"story_role":"main_story","claims":[{{"id":"recovery_event_1_claim_1",
"text":"...","claim_type":"fact","sources":[{{"asset_id":"...",
"page_order":1,"region_ids":[1]}}]}}]}}}}]}}
"""


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
