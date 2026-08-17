import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.project_short_script import ProjectShortScript


SCRIPT_PERSISTENCE_VERSION = "project_short_script.v1"
SEGMENT_TYPES = ("hook", "setup", "development", "payoff", "ending")
NARRATION_WORDS_PER_MINUTE = 150
MAX_SEGMENT_TEXT_LENGTH = 4000


def save_generated_script(
    db: Session,
    project_id: str,
    result: dict[str, Any],
    style: str,
    story_fingerprint: str,
    story_approved_at: datetime,
) -> ProjectShortScript:
    record = db.query(ProjectShortScript).filter_by(project_id=project_id).first()
    now = datetime.now(timezone.utc)
    if record is None:
        record = ProjectShortScript(project_id=project_id, created_at=now)
    record.result = result
    record.segment_edits = {}
    record.style = style
    record.source_story_fingerprint = story_fingerprint
    record.source_story_approved_at = story_approved_at
    record.status = "generated"
    record.approved_at = None
    record.approval_fingerprint = None
    record.updated_at = now
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def edit_script_segment(
    db: Session,
    record: ProjectShortScript,
    segment_id: str,
    text: str,
    story_review: dict[str, Any],
) -> dict[str, Any]:
    current = serialize_short_script(record, story_review)
    if current["stale"]:
        raise HTTPException(status_code=409, detail="Script belongs to an older Final Story.")
    segment = next(
        (item for item in record.result.get("segments", []) if item.get("id") == segment_id),
        None,
    )
    if segment is None:
        raise HTTPException(status_code=404, detail="Script segment not found.")
    normalized = _normalize_text(text)
    edits = copy.deepcopy(record.segment_edits or {})
    edits[segment_id] = {
        "text": normalized,
        "source": "human",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    record.segment_edits = edits
    record.status = "edited"
    record.updated_at = datetime.now(timezone.utc)
    db.add(record)
    db.commit()
    db.refresh(record)
    return serialize_short_script(record, story_review)


def approve_short_script(
    db: Session,
    record: ProjectShortScript,
    story_review: dict[str, Any],
) -> dict[str, Any]:
    serialized = serialize_short_script(record, story_review)
    if serialized["script_approved"]:
        return serialized
    if serialized["stale"] or not story_review.get("story_approved"):
        raise HTTPException(status_code=409, detail="Script source Story is not currently approved.")
    _validate_final_segments(serialized["final_script"]["segments"], story_review)
    record.approved_at = datetime.now(timezone.utc)
    record.approval_fingerprint = serialized["script_fingerprint"]
    record.status = "approved"
    db.add(record)
    db.commit()
    db.refresh(record)
    return serialize_short_script(record, story_review)


def serialize_short_script(
    record: ProjectShortScript,
    story_review: dict[str, Any],
) -> dict[str, Any]:
    story_fingerprint = story_review.get("final_story_fingerprint")
    stale = bool(
        not story_review.get("story_approved")
        or record.source_story_fingerprint != story_fingerprint
        or record.source_story_approved_at != story_review.get("approved_at")
    )
    final_result = copy.deepcopy(record.result)
    edits = record.segment_edits or {}
    for segment in final_result.get("segments", []):
        edit = edits.get(str(segment.get("id")))
        segment["provenance"] = "human_edited" if edit else "ai_generated"
        if edit:
            segment["generated_text"] = segment.get("text", "")
            segment["text"] = edit["text"]
    word_count = _word_count(final_result.get("segments", []))
    duration = round(word_count / NARRATION_WORDS_PER_MINUTE * 60, 1)
    fingerprint = short_script_fingerprint(
        final_result,
        record.style,
        record.source_story_fingerprint,
    )
    approved = bool(
        not stale
        and record.approved_at
        and record.approval_fingerprint == fingerprint
    )
    approval_invalidated = bool(record.approved_at and not approved)
    status = "stale" if stale else "approved" if approved else "edited" if edits else "generated"
    final_result["summary"] = {
        **final_result.get("summary", {}),
        "word_count": word_count,
        "estimated_duration_seconds": duration,
    }
    return {
        "persistence_version": SCRIPT_PERSISTENCE_VERSION,
        "script_id": record.id,
        "project_id": record.project_id,
        "status": status,
        "stale": stale,
        "style": record.style,
        "source_story_fingerprint": record.source_story_fingerprint,
        "source_story_approved_at": record.source_story_approved_at,
        "current_story_fingerprint": story_fingerprint,
        "script_fingerprint": fingerprint,
        "approved_fingerprint": record.approval_fingerprint,
        "script_approved": approved,
        "approval_invalidated": approval_invalidated,
        "approved_at": record.approved_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "final_script": final_result,
        "tts_handoff": _tts_handoff(record, final_result, fingerprint) if approved else None,
    }


def short_script_fingerprint(
    final_result: dict[str, Any],
    style: str,
    story_fingerprint: str,
) -> str:
    payload = {
        "style": style,
        "source_story_fingerprint": story_fingerprint,
        "segments": [
            {
                "id": segment.get("id"),
                "type": segment.get("type"),
                "text": segment.get("text"),
                "source_event_ids": segment.get("source_event_ids", []),
                "source_claim_ids": segment.get("source_claim_ids", []),
            }
            for segment in final_result.get("segments", [])
            if isinstance(segment, dict)
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_final_segments(
    segments: list[dict[str, Any]],
    story_review: dict[str, Any],
) -> None:
    if len(segments) != len(SEGMENT_TYPES):
        raise HTTPException(status_code=409, detail="Final Script must contain five segments.")
    valid_events = {
        event.get("id")
        for event in story_review.get("final_story", {}).get("grounded_result", {}).get("events", [])
        if isinstance(event, dict) and event.get("script_ready") is True
    }
    for expected_type, segment in zip(SEGMENT_TYPES, segments, strict=True):
        if segment.get("type") != expected_type or not _normalize_text(segment.get("text", "")):
            raise HTTPException(status_code=409, detail="Final Script segments are incomplete.")
        source_ids = segment.get("source_event_ids", [])
        if not source_ids or any(event_id not in valid_events for event_id in source_ids):
            raise HTTPException(status_code=409, detail="Final Script source references are invalid.")


def _normalize_text(value: str) -> str:
    text = value.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Script segment text cannot be empty.")
    if len(text) > MAX_SEGMENT_TEXT_LENGTH:
        raise HTTPException(status_code=422, detail="Script segment text is too long.")
    return text


def _word_count(segments: list[dict[str, Any]]) -> int:
    return sum(len(str(segment.get("text", "")).split()) for segment in segments)


def _tts_handoff(
    record: ProjectShortScript,
    final_result: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    summary = final_result["summary"]
    return {
        "script_id": record.id,
        "project_id": record.project_id,
        "language": "vi",
        "style": record.style,
        "status": "approved",
        "script_fingerprint": fingerprint,
        "source_story_fingerprint": record.source_story_fingerprint,
        "word_count": summary["word_count"],
        "estimated_duration_seconds": summary["estimated_duration_seconds"],
        "segments": [
            {
                "id": segment["id"],
                "type": segment["type"],
                "text": segment["text"],
                "source_event_ids": segment.get("source_event_ids", []),
                "source_claim_ids": segment.get("source_claim_ids", []),
            }
            for segment in final_result.get("segments", [])
        ],
    }
