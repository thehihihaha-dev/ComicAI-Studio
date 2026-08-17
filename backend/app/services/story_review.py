import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.project_story_analysis import ProjectStoryAnalysis


REVIEW_VERSION = "story_review.v1"
MAX_STORY_TEXT_LENGTH = 2000


def empty_review_state() -> dict[str, Any]:
    return {
        "review_version": REVIEW_VERSION,
        "event_edits": {},
        "resolutions": {},
    }


def source_key(asset_id: str, region_id: int) -> str:
    return f"{asset_id}:{region_id}"


def normalize_story_text(value: str) -> str:
    text = value.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Story text cannot be empty.")
    if len(text) > MAX_STORY_TEXT_LENGTH:
        raise HTTPException(status_code=422, detail="Story text is too long.")
    return text


def require_current_review(
    record: ProjectStoryAnalysis,
    requested_revision: str,
    current_revision: str,
) -> dict[str, Any]:
    if requested_revision != current_revision or record.source_revision != current_revision:
        raise HTTPException(status_code=409, detail="Story sources have changed. Re-analyze before reviewing.")
    if record.review_source_revision not in (None, current_revision):
        raise HTTPException(status_code=409, detail="Story review belongs to an older source revision.")
    state = copy.deepcopy(record.review_state or empty_review_state())
    state.setdefault("event_edits", {})
    state.setdefault("resolutions", {})
    return state


def unresolved_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = result.get("coverage", {})
    items = coverage.get("important_uncovered_regions", []) if isinstance(coverage, dict) else []
    return [item for item in items if isinstance(item, dict)]


def find_unresolved(
    record: ProjectStoryAnalysis,
    asset_id: str,
    region_id: int,
) -> dict[str, Any]:
    item = next(
        (
            item
            for item in unresolved_items(record.result)
            if item.get("asset_id") == asset_id and item.get("region_id") == region_id
        ),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Unresolved Story evidence not found.")
    return item


def edit_story_event(
    db: Session,
    record: ProjectStoryAnalysis,
    event_id: str,
    text: str,
    requested_revision: str,
    current_revision: str,
) -> dict[str, Any]:
    state = require_current_review(record, requested_revision, current_revision)
    human_resolution = next(
        (
            resolution for resolution in state["resolutions"].values()
            if isinstance(resolution, dict)
            and resolution.get("action") == "added_to_story"
            and resolution.get("event_id") == event_id
        ),
        None,
    )
    if human_resolution is not None:
        human_resolution["text"] = normalize_story_text(text)
        human_resolution["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_review(db, record, state, current_revision)
        return compose_story_review(record, current_revision)
    events = record.result.get("grounded_result", {}).get("events", [])
    event = next(
        (
            item for item in events
            if isinstance(item, dict)
            and item.get("id") == event_id
            and item.get("script_ready") is True
            and not item.get("unsupported_claims")
        ),
        None,
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Editable Story event not found.")
    now = datetime.now(timezone.utc).isoformat()
    state["event_edits"][event_id] = {
        "text": normalize_story_text(text),
        "source": "human",
        "action": "edited_event",
        "original_text": event.get("summary") or " ".join(
            claim.get("text", "") for claim in event.get("claims", []) if isinstance(claim, dict)
        ),
        "updated_at": now,
    }
    _save_review(db, record, state, current_revision)
    return compose_story_review(record, current_revision)


def resolve_unresolved(
    db: Session,
    record: ProjectStoryAnalysis,
    asset_id: str,
    region_id: int,
    action: str,
    requested_revision: str,
    current_revision: str,
    text: str | None = None,
) -> dict[str, Any]:
    item = find_unresolved(record, asset_id, region_id)
    state = require_current_review(record, requested_revision, current_revision)
    key = source_key(asset_id, region_id)
    if key in state["resolutions"]:
        raise HTTPException(status_code=409, detail="Story evidence has already been reviewed.")
    now = datetime.now(timezone.utc).isoformat()
    resolution: dict[str, Any] = {
        "source": "human",
        "action": action,
        "asset_id": item["asset_id"],
        "page_order": item["page_order"],
        "region_id": item["region_id"],
        "evidence_text": item.get("evidence_text", ""),
        "created_at": now,
        "updated_at": now,
    }
    if action == "added_to_story":
        resolution["text"] = normalize_story_text(text or "")
        resolution["event_id"] = _human_event_id(
            record.project_id, current_revision, asset_id, region_id
        )
    elif action != "non_story_relevant":
        raise HTTPException(status_code=422, detail="Unsupported Story review action.")
    state["resolutions"][key] = resolution
    _save_review(db, record, state, current_revision)
    return compose_story_review(record, current_revision)


def compose_story_review(
    record: ProjectStoryAnalysis,
    current_revision: str,
) -> dict[str, Any]:
    stale = record.source_revision != current_revision
    review_stale = bool(record.review_source_revision and record.review_source_revision != current_revision)
    applicable = not stale and not review_stale
    state = copy.deepcopy(record.review_state or empty_review_state())
    edits = state.get("event_edits", {}) if applicable else {}
    resolutions = state.get("resolutions", {}) if applicable else {}
    events: list[dict[str, Any]] = []
    grounded = record.result.get("grounded_result", {})
    progression = set(grounded.get("main_progression", []))
    for index, raw_event in enumerate(grounded.get("events", [])):
        if (
            not isinstance(raw_event, dict)
            or raw_event.get("script_ready") is not True
            or raw_event.get("unsupported_claims")
        ):
            continue
        event = copy.deepcopy(raw_event)
        event["provenance"] = "ai_grounded"
        event["_source_order"] = _event_source_order(event, index)
        edit = edits.get(str(event.get("id")))
        if isinstance(edit, dict):
            event["ai_original_summary"] = event.get("summary")
            event["summary"] = edit.get("text", "")
            event["provenance"] = "human_edited"
            event["claims"] = [{
                "id": f"human-edit-{event.get('id')}",
                "text": edit.get("text", ""),
                "sources": _event_sources(event),
                "claim_type": "human_authored",
            }]
        events.append(event)
    for resolution in resolutions.values():
        if not isinstance(resolution, dict) or resolution.get("action") != "added_to_story":
            continue
        events.append({
            "id": resolution["event_id"],
            "summary": resolution["text"],
            "story_role": "main_story",
            "importance": 1.0,
            "emotion": "neutral",
            "script_ready": True,
            "unsupported_claims": [],
            "provenance": "human_added",
            "created_at": resolution["created_at"],
            "updated_at": resolution["updated_at"],
            "claims": [{
                "id": f"{resolution['event_id']}-claim",
                "text": resolution["text"],
                "claim_type": "human_authored",
                "sources": [{
                    "asset_id": resolution["asset_id"],
                    "page_order": resolution["page_order"],
                    "region_ids": [resolution["region_id"]],
                }],
            }],
            "_source_order": (resolution["page_order"], resolution["region_id"], 1),
        })
    events.sort(key=lambda item: tuple(item.pop("_source_order")))
    valid_keys = {
        source_key(str(item.get("asset_id")), int(item.get("region_id")))
        for item in unresolved_items(record.result)
        if item.get("asset_id") is not None and isinstance(item.get("region_id"), int)
    }
    resolved_keys = valid_keys.intersection(resolutions)
    remaining = [
        item for item in unresolved_items(record.result)
        if source_key(str(item.get("asset_id")), int(item.get("region_id"))) not in resolved_keys
    ]
    ai_ready = record.status == "ready" and not stale
    review_complete = applicable and not remaining and (
        bool(record.review_source_revision) or not valid_keys
    )
    final_ready = ai_ready or review_complete
    final_result = copy.deepcopy(record.result)
    final_result["grounded_result"]["events"] = events
    final_result["grounded_result"]["main_progression"] = [
        event["id"] for event in events
        if event.get("story_role") == "main_story"
    ]
    final_result["coverage"]["important_uncovered_regions"] = remaining
    final_result["coverage"]["unresolved_regions"] = len(remaining)
    final_result["final_story_provenance"] = "human_reviewed" if review_complete else "ai"
    fingerprint = final_story_fingerprint(final_result, current_revision)
    approval_present = bool(record.approved_at and record.approval_story_fingerprint)
    story_approved = bool(
        final_ready
        and not stale
        and not review_stale
        and record.approval_source_revision == current_revision
        and record.approval_story_fingerprint == fingerprint
    )
    return {
        "review_version": REVIEW_VERSION,
        "status": "stale" if stale or review_stale else (
            "reviewed" if review_complete else "in_progress" if resolved_keys or edits else "none"
        ),
        "stale": stale or review_stale,
        "source_revision": current_revision,
        "review_source_revision": record.review_source_revision,
        "ai_status": record.status,
        "resolved_by_human": len(resolved_keys),
        "unresolved_total": len(valid_keys),
        "unresolved_remaining": len(remaining),
        "human_added_event_ids": [
            event["id"] for event in events if event.get("provenance") == "human_added"
        ],
        "review_complete": review_complete,
        "final_story_ready": final_ready and not stale and not review_stale,
        "story_approved": story_approved,
        "approval_invalidated": approval_present and not story_approved,
        "final_story_fingerprint": fingerprint,
        "approved_story_fingerprint": record.approval_story_fingerprint,
        "approved_at": record.approved_at,
        "final_story": final_result,
    }


def approve_final_story(
    db: Session,
    record: ProjectStoryAnalysis,
    current_revision: str,
) -> dict[str, Any]:
    composed = compose_story_review(record, current_revision)
    if composed["story_approved"]:
        return composed
    if (
        composed["stale"]
        or not composed["final_story_ready"]
        or not composed["review_complete"]
        or composed["unresolved_remaining"] != 0
    ):
        raise HTTPException(status_code=409, detail="Final Story is not ready for approval.")
    record.approved_at = datetime.now(timezone.utc)
    record.approval_source_revision = current_revision
    record.approval_story_fingerprint = composed["final_story_fingerprint"]
    db.add(record)
    db.commit()
    db.refresh(record)
    return compose_story_review(record, current_revision)


def final_story_fingerprint(
    final_story: dict[str, Any],
    source_revision: str,
) -> str:
    events = final_story.get("grounded_result", {}).get("events", [])
    canonical_events = []
    for event in events:
        if not isinstance(event, dict):
            continue
        canonical_events.append({
            "id": event.get("id"),
            "text": event.get("summary") or " ".join(
                claim.get("text", "")
                for claim in event.get("claims", [])
                if isinstance(claim, dict)
            ),
            "provenance": event.get("provenance"),
            "sources": _event_sources(event),
        })
    payload = {
        "source_revision": source_revision,
        "events": canonical_events,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _save_review(
    db: Session,
    record: ProjectStoryAnalysis,
    state: dict[str, Any],
    revision: str,
) -> None:
    record.review_state = state
    record.review_source_revision = revision
    record.review_status = "in_progress"
    record.updated_at = datetime.now(timezone.utc)
    db.add(record)
    db.commit()
    db.refresh(record)
    composed = compose_story_review(record, revision)
    if composed["review_complete"]:
        record.review_status = "reviewed"
        db.add(record)
        db.commit()
        db.refresh(record)


def _human_event_id(project_id: str, revision: str, asset_id: str, region_id: int) -> str:
    identity = f"{project_id}|{revision}|{asset_id}|{region_id}".encode("utf-8")
    return f"human-event-{hashlib.sha256(identity).hexdigest()[:16]}"


def _event_sources(event: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], set[int]] = {}
    for claim in event.get("claims", []):
        for source in claim.get("sources", []) if isinstance(claim, dict) else []:
            key = (str(source.get("asset_id")), int(source.get("page_order", 0)))
            grouped.setdefault(key, set()).update(source.get("region_ids", []))
    return [
        {"asset_id": asset_id, "page_order": page, "region_ids": sorted(region_ids)}
        for (asset_id, page), region_ids in grouped.items()
    ]


def _event_source_order(event: dict[str, Any], fallback: int) -> tuple[int, int, int]:
    sources = _event_sources(event)
    positions = [
        (source["page_order"], min(source["region_ids"], default=0), 0)
        for source in sources
    ]
    return min(positions, default=(10**9, fallback, 0))
