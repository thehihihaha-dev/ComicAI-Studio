from __future__ import annotations

import re
import unicodedata
from typing import Any


REQUIRED_CANDIDATE_KEYS = {
    "schema_version",
    "checkpoint",
    "candidate_model",
    "input",
    "performance",
    "correctness",
    "safety",
}


def validate_candidate_artifact(artifact: dict[str, Any]) -> None:
    if not isinstance(artifact, dict):
        raise ValueError("Candidate artifact must be an object")
    missing = REQUIRED_CANDIDATE_KEYS - artifact.keys()
    if missing:
        raise ValueError(f"Candidate artifact missing keys: {sorted(missing)}")
    if artifact.get("schema_version") != 1 or artifact.get("checkpoint") != "11.2":
        raise ValueError("Unsupported candidate artifact schema/checkpoint")
    if not isinstance(artifact.get("candidate_model"), str):
        raise ValueError("candidate_model must be a string")
    unsupported = artifact.get("correctness", {}).get("accepted_unsupported_claims")
    if not isinstance(unsupported, int) or isinstance(unsupported, bool) or unsupported < 0:
        raise ValueError("accepted_unsupported_claims must be a non-negative integer")


def event_source_keys(event: dict[str, Any]) -> set[tuple[str, int, int]]:
    return {
        (source["asset_id"], source["page_order"], region_id)
        for claim in event.get("claims", [])
        if isinstance(claim, dict)
        for source in claim.get("sources", [])
        if isinstance(source, dict)
        and isinstance(source.get("asset_id"), str)
        and isinstance(source.get("page_order"), int)
        for region_id in source.get("region_ids", [])
        if isinstance(region_id, int)
    }


def _event_text(event: dict[str, Any]) -> str:
    value = " ".join(
        str(claim.get("text", ""))
        for claim in event.get("claims", [])
        if isinstance(claim, dict)
    )
    return " ".join(value.casefold().split())


def compare_events(
    control_events: list[dict[str, Any]], candidate_events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Create a conservative source-based diff without inventing quality scores."""
    matched_control_ids: set[str] = set()
    diff: list[dict[str, Any]] = []
    for candidate in candidate_events:
        candidate_sources = event_source_keys(candidate)
        ranked = sorted(
            control_events,
            key=lambda event: len(candidate_sources & event_source_keys(event)),
            reverse=True,
        )
        control = ranked[0] if ranked else None
        overlap = (
            candidate_sources & event_source_keys(control) if control is not None else set()
        )
        unsupported = bool(candidate.get("unsupported_claims")) or not candidate_sources
        if unsupported:
            classification = "unsupported"
            human_judgment = False
        elif control is None or not overlap:
            classification = "more specific but supported"
            human_judgment = True
        elif (
            candidate_sources == event_source_keys(control)
            and _event_text(candidate) == _event_text(control)
        ):
            classification = "equivalent"
            human_judgment = False
        elif candidate_sources < event_source_keys(control):
            classification = "less complete"
            human_judgment = True
        else:
            classification = "more specific but supported"
            human_judgment = True
        if control is not None and overlap and isinstance(control.get("id"), str):
            matched_control_ids.add(control["id"])
        diff.append(
            {
                "control_event_id": control.get("id") if control and overlap else None,
                "candidate_event_id": candidate.get("id"),
                "classification": classification,
                "human_judgment_required": human_judgment,
                "shared_source_count": len(overlap),
            }
        )
    diff.extend(
        {
            "control_event_id": event.get("id"),
            "candidate_event_id": None,
            "classification": "missing",
            "human_judgment_required": False,
            "shared_source_count": 0,
        }
        for event in control_events
        if event.get("id") not in matched_control_ids
    )
    return diff


def observe_output_language(events: list[dict[str, Any]]) -> str:
    texts = [
        str(claim.get("text", "")).strip()
        for event in events
        for claim in event.get("claims", [])
        if isinstance(claim, dict) and str(claim.get("text", "")).strip()
    ]
    if not texts:
        return "malformed"
    vietnamese_marks = set("ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
    vietnamese_words = re.compile(r"\b(là|và|của|một|đã|đang|không|trong|với|người|nhân vật)\b", re.I)
    english_words = re.compile(r"\b(the|and|is|are|was|were|with|character|story|game)\b", re.I)
    vi = sum(
        bool(set(unicodedata.normalize("NFC", text).casefold()) & vietnamese_marks)
        or bool(vietnamese_words.search(text))
        for text in texts
    )
    en = sum(bool(english_words.search(text)) for text in texts)
    if vi == len(texts) and en == 0:
        return "fully Vietnamese"
    if vi and en:
        return "mixed language"
    if en and not vi:
        return "English"
    return "mixed language"
