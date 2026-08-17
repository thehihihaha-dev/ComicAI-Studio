import json
import re
from typing import Any

from app.services.ollama_text import call_text_model
from app.services.performance import model_call_context, timed_stage


SCRIPT_VERSION = "short_script.v1"
SCRIPT_STYLES = {"natural", "funny", "emotional", "dramatic"}
SEGMENT_TYPES = ("hook", "setup", "development", "payoff", "ending")

STYLE_PHRASES = {
    "natural": {
        "hook": {"natural_hook": "Mở đầu câu chuyện, "},
        "setup": {"natural_setup": "Trong hoàn cảnh đó, "},
        "development": {"natural_development": "Sau đó, "},
        "payoff": {"natural_payoff": "Điểm quan trọng là, "},
        "ending": {"natural_ending": "Cuối cùng, "},
    },
    "funny": {
        "hook": {"funny_hook": "Nói vui một chút: "},
        "setup": {"funny_setup": "Trước hết: "},
        "development": {"funny_development": "Rồi câu chuyện tiếp tục: "},
        "payoff": {"funny_payoff": "Điểm đáng chú ý là: "},
        "ending": {"funny_ending": "Chốt lại: "},
    },
    "emotional": {
        "hook": {"emotional_hook": "Chậm lại một nhịp: "},
        "setup": {"emotional_setup": "Từ bối cảnh ấy: "},
        "development": {"emotional_development": "Tiếp theo: "},
        "payoff": {"emotional_payoff": "Điểm đọng lại là: "},
        "ending": {"emotional_ending": "Khép lại: "},
    },
    "dramatic": {
        "hook": {"dramatic_hook": "Mở đầu: "},
        "setup": {"dramatic_setup": "Bối cảnh: "},
        "development": {"dramatic_development": "Rồi: "},
        "payoff": {"dramatic_payoff": "Điểm nhấn: "},
        "ending": {"dramatic_ending": "Kết lại: "},
    },
}

FALLBACK_PHRASES = {
    "hook": "Mở đầu, ",
    "setup": "Về bối cảnh, ",
    "development": "Tiếp đó, ",
    "payoff": "Điểm chính là: ",
    "ending": "Tóm lại, ",
}


@timed_stage("short_script_engine")
def generate_short_script(
    reliability_result: dict[str, Any],
    style: str,
) -> dict[str, Any]:
    script_input = build_script_input(reliability_result)
    normalized_style = _validate_style(style)
    content_plan = build_content_plan(script_input)
    fallback = render_deterministic_fallback(content_plan, normalized_style)
    model_candidate: dict[str, Any] | None = None
    model_error: str | None = None

    try:
        with model_call_context("short_script_engine", attempt=1):
            raw = call_text_model(
                prompt=_build_script_prompt(content_plan, normalized_style)
            )
        selections = _validate_style_selections(raw, content_plan, normalized_style)
        model_candidate = _render_plan(
            content_plan,
            normalized_style,
            selections,
        )
        normalized = validate_short_script(
            model_candidate,
            script_input["safe_events"],
            normalized_style,
        )
        renderer_mode = "bounded_model_style"
    except (RuntimeError, TimeoutError, ValueError) as error:
        model_error = str(error)
        normalized = validate_short_script(
            fallback,
            script_input["safe_events"],
            normalized_style,
        )
        renderer_mode = "deterministic_fallback"

    return {
        "script_version": SCRIPT_VERSION,
        "project_id": script_input["project_id"],
        "style": normalized_style,
        "generation_attempts": 1,
        "renderer_mode": renderer_mode,
        "content_plan": content_plan,
        "segments": normalized["segments"],
        "model_candidate": model_candidate,
        "deterministic_fallback": fallback,
        "model_error": model_error,
        "summary": {
            "segment_count": len(normalized["segments"]),
            "word_count": _word_count(normalized["segments"]),
            "source_event_count": len(
                {
                    event_id
                    for segment in normalized["segments"]
                    for event_id in segment["source_event_ids"]
                }
            ),
            "unresolved_evidence_excluded": script_input[
                "unresolved_evidence_count"
            ],
        },
    }


def build_content_plan(script_input: dict[str, Any]) -> list[dict[str, Any]]:
    events = script_input.get("safe_events", [])
    by_id = {event["id"]: event for event in events}
    ordered_main_ids = list(script_input.get("main_progression", []))
    ordered_main_ids.extend(
        event["id"]
        for event in events
        if event["story_role"] == "main_story"
        and event["id"] not in ordered_main_ids
    )
    main_units = _claim_units([by_id[event_id] for event_id in ordered_main_ids])
    context_units = _claim_units(
        [event for event in events if event["story_role"] == "supporting_context"]
    )
    if not main_units:
        raise ValueError("No script-ready main_story claims are available.")

    assignments: list[list[dict[str, str]]] = [[] for _ in SEGMENT_TYPES]
    for index, unit in enumerate(main_units):
        assignments[min(index, len(SEGMENT_TYPES) - 1)].append(unit)
    for index, units in enumerate(assignments):
        if not units:
            units.append(main_units[min(index, len(main_units) - 1)])
    if context_units:
        assignments[1].append(context_units[0])
    return [
        _make_beat(index, role, units)
        for index, (role, units) in enumerate(
            zip(SEGMENT_TYPES, assignments, strict=True), start=1
        )
    ]


def render_deterministic_fallback(
    content_plan: list[dict[str, Any]], style: str
) -> dict[str, Any]:
    _validate_style(style)
    return {
        "segments": [
            _render_beat(beat, FALLBACK_PHRASES[beat["role"]])
            for beat in content_plan
        ]
    }


def build_script_input(reliability_result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(reliability_result, dict):
        raise ValueError("Story Reliability result must be an object.")
    grounded = reliability_result.get("grounded_result")
    if not isinstance(grounded, dict):
        raise ValueError("Story Reliability result has no grounded_result.")

    safe_events: list[dict[str, Any]] = []
    for event in grounded.get("events", []):
        if not isinstance(event, dict) or event.get("script_ready") is not True:
            continue
        claims = event.get("claims")
        if (
            not isinstance(claims, list)
            or not claims
            or event.get("unsupported_claims")
        ):
            continue
        safe_events.append(
            {
                "id": event.get("id"),
                "story_role": event.get("story_role", "main_story"),
                "importance": event.get("importance"),
                "emotion": event.get("emotion", "neutral"),
                "claims": [
                    {"id": claim.get("id"), "text": claim.get("text", "")}
                    for claim in claims
                ],
            }
        )
    if not safe_events:
        raise ValueError("No script-ready grounded events are available.")
    if not any(event["story_role"] == "main_story" for event in safe_events):
        raise ValueError("No script-ready main_story events are available.")

    safe_ids = {event["id"] for event in safe_events}
    progression = [
        event_id
        for event_id in grounded.get("main_progression", [])
        if event_id in safe_ids
    ]
    coverage = reliability_result.get("coverage", {})
    unresolved_count = (
        coverage.get("unresolved_regions", 0)
        if isinstance(coverage, dict)
        else 0
    )
    return {
        "project_id": reliability_result.get("project_id"),
        "safe_events": safe_events,
        "main_progression": progression,
        "unresolved_evidence_count": unresolved_count,
    }


def validate_short_script(
    result: dict[str, Any],
    grounded_events: list[dict[str, Any]],
    style: str,
) -> dict[str, Any]:
    _validate_style(style)
    if not isinstance(result, dict):
        raise ValueError("Short Script result must be an object.")
    segments = result.get("segments")
    if not isinstance(segments, list) or len(segments) != len(SEGMENT_TYPES):
        raise ValueError("Short Script must contain exactly five segments.")

    safe_event_ids = {
        event.get("id")
        for event in grounded_events
        if isinstance(event, dict)
        and event.get("id")
        and event.get("script_ready", True) is True
        and not event.get("unsupported_claims")
    }
    event_claim_ids = {
        event.get("id"): {
            claim.get("id")
            for claim in event.get("claims", [])
            if isinstance(claim, dict) and claim.get("id")
        }
        for event in grounded_events
        if isinstance(event, dict) and event.get("id") in safe_event_ids
    }
    claim_texts = {
        claim.get("id"): claim.get("text", "")
        for event in grounded_events
        if isinstance(event, dict) and event.get("id") in safe_event_ids
        for claim in event.get("claims", [])
        if isinstance(claim, dict) and claim.get("id")
    }
    known_names = _known_claim_names(claim_texts.values())
    seen_segment_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError("Every script segment must be an object.")
        segment_id = _required_text(segment.get("id"), "segment.id")
        if segment_id in seen_segment_ids:
            raise ValueError(f"Duplicate segment id: {segment_id!r}.")
        seen_segment_ids.add(segment_id)
        segment_type = _required_text(segment.get("type"), "segment.type").lower()
        if segment_type != SEGMENT_TYPES[index]:
            raise ValueError(
                f"Segment {index + 1} must have type {SEGMENT_TYPES[index]!r}."
            )
        source_ids = segment.get("source_event_ids")
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or not all(isinstance(item, str) and item.strip() for item in source_ids)
        ):
            raise ValueError(f"Segment {segment_id!r} needs source_event_ids.")
        normalized_sources = [item.strip() for item in source_ids]
        if len(set(normalized_sources)) != len(normalized_sources):
            raise ValueError(f"Segment {segment_id!r} has duplicate event references.")
        invalid_ids = [item for item in normalized_sources if item not in safe_event_ids]
        if invalid_ids:
            raise ValueError(
                f"Segment {segment_id!r} references unsafe or unknown events: "
                f"{invalid_ids}."
            )
        claim_ids = _required_id_list(
            segment.get("source_claim_ids"),
            f"Segment {segment_id!r} needs source_claim_ids.",
        )
        allowed_claim_ids = set().union(
            *(event_claim_ids[event_id] for event_id in normalized_sources)
        )
        invalid_claim_ids = [
            claim_id for claim_id in claim_ids if claim_id not in allowed_claim_ids
        ]
        if invalid_claim_ids:
            raise ValueError(
                f"Segment {segment_id!r} references claims not belonging to its "
                f"safe events: {invalid_claim_ids}."
            )
        factual_claims_used = _required_id_list(
            segment.get("factual_claims_used"),
            f"Segment {segment_id!r} needs factual_claims_used.",
        )
        if set(factual_claims_used) != set(claim_ids):
            raise ValueError(
                f"Segment {segment_id!r} factual_claims_used must match "
                "source_claim_ids."
            )
        cited_text = " ".join(claim_texts[claim_id] for claim_id in claim_ids)
        leaked_names = [
            name
            for name in known_names
            if _contains_token(segment.get("text", ""), name)
            and not _contains_token(cited_text, name)
        ]
        if leaked_names:
            raise ValueError(
                f"Segment {segment_id!r} uses names absent from its cited claims: "
                f"{leaked_names}."
            )
        normalized.append(
            {
                "id": segment_id,
                "type": segment_type,
                "text": _required_text(segment.get("text"), "segment.text"),
                "source_event_ids": normalized_sources,
                "source_claim_ids": claim_ids,
                "factual_claims_used": factual_claims_used,
            }
        )
    return {"segments": normalized}


def _build_script_prompt(content_plan: list[dict[str, Any]], style: str) -> str:
    choices = {
        beat["beat_id"]: list(STYLE_PHRASES[style][beat["role"]])
        for beat in content_plan
    }
    return f"""
You are selecting pacing for ComicAI Studio. You cannot write or rewrite story
text. Choose exactly one allowed style_phrase_id for each existing beat. Do not
add, remove, reorder, merge or split beats. Return JSON only.

STYLE: {style}
ALLOWED CHOICES:
{json.dumps(choices, ensure_ascii=False, indent=2)}

{{"beats":[
{{"beat_id":"beat_1","style_phrase_id":"..."}},
{{"beat_id":"beat_2","style_phrase_id":"..."}},
{{"beat_id":"beat_3","style_phrase_id":"..."}},
{{"beat_id":"beat_4","style_phrase_id":"..."}},
{{"beat_id":"beat_5","style_phrase_id":"..."}}
]}}
"""


def _claim_units(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "event_id": event["id"],
            "claim_id": claim["id"],
            "fact_text": _safe_fact_text(claim["text"]),
        }
        for event in events
        for claim in event["claims"]
        if claim.get("id") and isinstance(claim.get("text"), str)
        and claim["text"].strip()
    ]


def _make_beat(
    index: int, role: str, units: list[dict[str, str]]
) -> dict[str, Any]:
    return {
        "beat_id": f"beat_{index}",
        "role": role,
        "source_event_ids": list(dict.fromkeys(unit["event_id"] for unit in units)),
        "claim_ids": list(dict.fromkeys(unit["claim_id"] for unit in units)),
        "fact_text": " ".join(unit["fact_text"] for unit in units),
    }


def _safe_fact_text(text: str) -> str:
    # V1 narrates grounded claims instead of presenting them as direct dialogue.
    return text.strip().translate(str.maketrans("", "", '\"\'“”‘’«»'))


def _validate_style_selections(
    result: dict[str, Any],
    content_plan: list[dict[str, Any]],
    style: str,
) -> dict[str, str]:
    if not isinstance(result, dict):
        raise ValueError("Style selection result must be an object.")
    beats = result.get("beats")
    if not isinstance(beats, list) or len(beats) != len(content_plan):
        raise ValueError("Style selection must contain exactly five beats.")
    selections: dict[str, str] = {}
    for expected, selected in zip(content_plan, beats, strict=True):
        if not isinstance(selected, dict) or selected.get("beat_id") != expected["beat_id"]:
            raise ValueError("Style selection changed or reordered a beat.")
        phrase_id = selected.get("style_phrase_id")
        allowed = STYLE_PHRASES[style][expected["role"]]
        if phrase_id not in allowed:
            raise ValueError(f"Invalid style phrase for {expected['beat_id']!r}.")
        selections[expected["beat_id"]] = phrase_id
    return selections


def _render_plan(
    content_plan: list[dict[str, Any]],
    style: str,
    selections: dict[str, str],
) -> dict[str, Any]:
    return {
        "segments": [
            _render_beat(
                beat,
                STYLE_PHRASES[style][beat["role"]][selections[beat["beat_id"]]],
            )
            for beat in content_plan
        ]
    }


def _render_beat(beat: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {
        "id": beat["beat_id"].replace("beat", "segment"),
        "type": beat["role"],
        "text": f"{prefix}{beat['fact_text']}",
        "source_event_ids": beat["source_event_ids"],
        "source_claim_ids": beat["claim_ids"],
        "factual_claims_used": beat["claim_ids"],
    }


def _validate_style(style: Any) -> str:
    if not isinstance(style, str) or style.strip().lower() not in SCRIPT_STYLES:
        raise ValueError(f"Style must be one of: {sorted(SCRIPT_STYLES)}.")
    return style.strip().lower()


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _required_id_list(value: Any, message: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ValueError(message)
    normalized = [item.strip() for item in value]
    if len(set(normalized)) != len(normalized):
        raise ValueError("Claim references must be unique per segment.")
    return normalized


def _word_count(segments: list[dict[str, Any]]) -> int:
    return sum(
        len(re.findall(r"\S+", segment["text"]))
        for segment in segments
    )


def _known_claim_names(texts: Any) -> set[str]:
    ignored = {"A", "AN", "THE"}
    result: set[str] = set()
    for text in texts:
        if not isinstance(text, str):
            continue
        for token in re.findall(r"[A-Za-zÀ-ỹ]+", text):
            if len(token) >= 3 and (token.isupper() or token.istitle()):
                normalized = token.upper()
                if normalized not in ignored:
                    result.add(normalized)
    return result


def _contains_token(text: Any, token: str) -> bool:
    if not isinstance(text, str):
        return False
    return re.search(
        rf"(?<![\w]){re.escape(token)}(?![\w])",
        text.upper(),
        flags=re.UNICODE,
    ) is not None
