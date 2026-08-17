import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.project_story_analysis import ProjectStoryAnalysis


PERSISTENCE_VERSION = "project_story_analysis.v1"


def story_source_revision(story_input: dict[str, Any]) -> str:
    source = {
        "contract_version": story_input.get("contract_version"),
        "project_id": story_input.get("project_id"),
        "status": story_input.get("status"),
        "pages": story_input.get("pages", []),
    }
    canonical = json.dumps(
        source,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def story_result_status(result: dict[str, Any]) -> str:
    coverage = result.get("coverage", {})
    grounded = result.get("grounded_result", {})
    has_safe_main_event = any(
        event.get("story_role") == "main_story" and event.get("script_ready") is True
        for event in grounded.get("events", [])
        if isinstance(event, dict)
    )
    return "ready" if coverage.get("unresolved_regions") == 0 and has_safe_main_event else "partial"


def save_story_result(
    db: Session,
    project_id: str,
    result: dict[str, Any],
    source_revision: str,
) -> ProjectStoryAnalysis:
    record = (
        db.query(ProjectStoryAnalysis)
        .filter(ProjectStoryAnalysis.project_id == project_id)
        .first()
    )
    now = datetime.now(timezone.utc)
    if record is None:
        record = ProjectStoryAnalysis(project_id=project_id, created_at=now)
    record.result = result
    record.status = story_result_status(result)
    record.source_revision = source_revision
    record.pipeline_version = result.get("reliability_version")
    if record.approval_story_fingerprint:
        record.approval_story_fingerprint = f"invalidated:{record.approval_story_fingerprint}"
    record.updated_at = now
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def serialize_story_record(
    record: ProjectStoryAnalysis,
    current_source_revision: str,
) -> dict[str, Any]:
    stale = record.source_revision != current_source_revision
    return {
        "persistence_version": PERSISTENCE_VERSION,
        "status": "stale" if stale else record.status,
        "story_status": record.status,
        "stale": stale,
        "source_revision": record.source_revision,
        "current_source_revision": current_source_revision,
        "pipeline_version": record.pipeline_version,
        "analyzed_at": record.updated_at,
        "result": record.result,
    }
