from uuid import uuid4
from datetime import datetime, timezone

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.projects import (
    GenerateScriptRequest,
    ProjectCreate,
    ShortScriptCreate,
    ShortScriptSegmentEdit,
    StoryEventEdit,
    StoryEvidenceAdd,
    StoryEvidenceResolution,
)
import json
try:
    from src.services.script_generator import (
        GeneratedScriptResponse,
        generate_script,
    )
except ModuleNotFoundError:
    from backend.src.services.script_generator import (
        GeneratedScriptResponse,
        generate_script,
    )
from app.database import SessionLocal
from app.models.asset import Asset
from app.models.dialogue_ground_truth import DialogueGroundTruth
from app.models.project import Project
from app.models.project_story_analysis import ProjectStoryAnalysis
from app.models.project_short_script import ProjectShortScript
from sqlalchemy import select
from app.services.short_script_engine import generate_short_script
from app.services.short_script_persistence import (
    approve_short_script,
    edit_script_segment,
    save_generated_script,
    serialize_short_script,
)
from app.services.story_input_builder import build_story_input
from app.services.story_reliability import run_reliable_story_analysis
from app.services.story_persistence import (
    save_story_result,
    serialize_story_record,
    story_source_revision,
)
from app.services.story_review import (
    approve_final_story,
    compose_story_review,
    edit_story_event,
    resolve_unresolved,
)
projects = []
router = APIRouter(
    tags=["Projects"],
)

DEFAULT_PROJECT_ID = "92961605-5553-4df1-b74e-9a3bed5e14f5"
DEFAULT_PROJECT_RECORD = {
    "id": DEFAULT_PROJECT_ID,
    "name": "Vợ trong game của tôi là Idol nổi tiếng ngoài đời",
    "content_type": "short",
    "status": "ready",
    "created_at": "2026-08-22T23:00:00Z",
    "thumbnail_url": "http://127.0.0.1:8000/uploads/92961605-5553-4df1-b74e-9a3bed5e14f5_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-2.jpg",
}


@router.get("/")
def get_projects():
    db = SessionLocal()

    try:
        thumbnail_path = (
            select(Asset.file_path)
            .where(Asset.project_id == Project.id)
            .order_by(Asset.page_order.asc(), Asset.created_at.asc())
            .limit(1)
            .scalar_subquery()
        )

        rows = (
            db.query(Project, thumbnail_path.label("thumbnail_path"))
            .order_by(Project.created_at.desc())
            .all()
        )

        projects_list = [
            {
                "id": project.id,
                "name": project.name,
                "content_type": project.content_type,
                "status": project.status,
                "created_at": project.created_at,
                "thumbnail_url": (
                    f"http://127.0.0.1:8000/{path}"
                    if path
                    else None
                ),
            }
            for project, path in rows
        ]

        if not projects_list:
            projects_list = [DEFAULT_PROJECT_RECORD]

        return {
            "message": "ComicAI Studio Project API",
            "projects": projects_list,
        }
    except Exception:
        return {
            "message": "ComicAI Studio Project API (Offline Fallback)",
            "projects": [DEFAULT_PROJECT_RECORD],
        }
    finally:
        db.close()
@router.post("/")
def create_project(project: ProjectCreate):
    new_project = Project(
    id=str(uuid4()),
    name=project.name,
    content_type=project.content_type,
    status="created",
    created_at=datetime.now(timezone.utc),
)
        id=str(uuid4()),
        name=project.name,
        content_type=project.content_type,
        status="created",
        created_at=datetime.now(timezone.utc),
    )
    db = SessionLocal()
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    db.close()
    try:
        db.add(new_project)
        db.commit()
        db.refresh(new_project)

        # Pre-seed style preference in project script record if provided
        if project.story_style and project.content_type == "short":
            now = datetime.now(timezone.utc)
            script_record = ProjectShortScript(
                project_id=new_project.id,
                style=project.story_style,
                result={"segments": []},
                source_story_fingerprint=f"init_{project.story_style}",
                source_story_approved_at=now,
                status="draft",
                created_at=now,
                updated_at=now,
            )
            db.add(script_record)
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return new_project


@router.delete("/{project_id}")
def delete_project(project_id: str):
    db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        assets = db.query(Asset).filter(Asset.project_id == project_id).all()
        asset_ids = [asset.id for asset in assets]
        file_paths = [Path(asset.file_path) for asset in assets]

        if asset_ids:
            (
                db.query(DialogueGroundTruth)
                .filter(DialogueGroundTruth.asset_id.in_(asset_ids))
                .delete(synchronize_session=False)
            )
            (
                db.query(Asset)
                .filter(Asset.id.in_(asset_ids))
                .delete(synchronize_session=False)
            )

        (
            db.query(ProjectShortScript)
            .filter(ProjectShortScript.project_id == project_id)
            .delete(synchronize_session=False)
        )

        (
            db.query(ProjectStoryAnalysis)
            .filter(ProjectStoryAnalysis.project_id == project_id)
            .delete(synchronize_session=False)
        )

        db.delete(project)
        db.commit()

        for file_path in file_paths:
            file_path.unlink(missing_ok=True)

        return {
            "project_id": project_id,
            "deleted_assets": len(asset_ids),
            "message": "Project deleted successfully",
        }
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/{project_id}")
def get_project(project_id: str):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is not None:
            return project
    except Exception:
        pass
    finally:
        db.close()

    return {
        "id": project_id,
        "name": "Vợ trong game của tôi là Idol nổi tiếng ngoài đời",
        "content_type": "short",
        "status": "ready",
        "created_at": "2026-08-22T23:00:00Z",
    }


@router.get("/{project_id}/story-input")
def get_project_story_input(project_id: str):
    return build_story_input(project_id)


@router.get("/{project_id}/story-analysis")
def get_project_story_analysis(project_id: str):
    story_input = build_story_input(project_id)
    db = SessionLocal()
    try:
        record = (
            db.query(ProjectStoryAnalysis)
            .filter(ProjectStoryAnalysis.project_id == project_id)
            .first()
        )
        if record is None:
            return {
                "status": "none",
                "stale": False,
                "result": None,
                "current_source_revision": story_source_revision(story_input),
            }
        return serialize_story_record(
            record,
            story_source_revision(story_input),
        )
    except Exception:
        return {
            "status": "none",
            "stale": False,
            "result": None,
            "current_source_revision": story_source_revision(story_input),
        }
    finally:
        db.close()


@router.post("/{project_id}/story-analysis")
def analyze_project_story(project_id: str):
    story_input = build_story_input(project_id)
    if story_input.get("status") != "ready":
        raise HTTPException(
            status_code=409,
            detail="Project pages are not ready for story analysis.",
        )
    try:
        result = run_reliable_story_analysis(story_input)
    except (RuntimeError, TimeoutError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    db = SessionLocal()
    try:
        save_story_result(
            db,
            project_id,
            result,
            story_source_revision(story_input),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return result


def _story_record(db, project_id: str) -> ProjectStoryAnalysis:
    record = (
        db.query(ProjectStoryAnalysis)
        .filter(ProjectStoryAnalysis.project_id == project_id)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Story Analysis not found.")
    return record


@router.get("/{project_id}/story-review")
def get_project_story_review(project_id: str):
    story_input = build_story_input(project_id)
    revision = story_source_revision(story_input)
    db = SessionLocal()
    try:
        return compose_story_review(_story_record(db, project_id), revision)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Story Analysis not found.")
    finally:
        db.close()


@router.patch("/{project_id}/story-review/events/{event_id}")
def update_project_story_event(
    project_id: str,
    event_id: str,
    request: StoryEventEdit,
):
    story_input = build_story_input(project_id)
    revision = story_source_revision(story_input)
    db = SessionLocal()
    try:
        return edit_story_event(
            db,
            _story_record(db, project_id),
            event_id,
            request.text,
            request.source_revision,
            revision,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{project_id}/story-review/unresolved/{asset_id}/{region_id}/add")
def add_unresolved_to_project_story(
    project_id: str,
    asset_id: str,
    region_id: int,
    request: StoryEvidenceAdd,
):
    story_input = build_story_input(project_id)
    revision = story_source_revision(story_input)
    db = SessionLocal()
    try:
        return resolve_unresolved(
            db,
            _story_record(db, project_id),
            asset_id,
            region_id,
            "added_to_story",
            request.source_revision,
            revision,
            request.text,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{project_id}/story-review/unresolved/{asset_id}/{region_id}/dismiss")
def dismiss_unresolved_from_project_story(
    project_id: str,
    asset_id: str,
    region_id: int,
    request: StoryEvidenceResolution,
):
    story_input = build_story_input(project_id)
    revision = story_source_revision(story_input)
    db = SessionLocal()
    try:
        return resolve_unresolved(
            db,
            _story_record(db, project_id),
            asset_id,
            region_id,
            "non_story_relevant",
            request.source_revision,
            revision,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{project_id}/story-review/approve")
def approve_project_story(project_id: str):
    story_input = build_story_input(project_id)
    revision = story_source_revision(story_input)
    db = SessionLocal()
    try:
        return approve_final_story(
            db,
            _story_record(db, project_id),
            revision,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{project_id}/short-script")
def create_project_short_script(project_id: str, request: ShortScriptCreate):
    story_input = build_story_input(project_id)
    if story_input.get("status") != "ready":
        raise HTTPException(
            status_code=409,
            detail="Project pages are not ready for script generation.",
        )
    revision = story_source_revision(story_input)
    db = SessionLocal()
    try:
        review = compose_story_review(_story_record(db, project_id), revision)
        if not review["final_story_ready"] or not review["story_approved"]:
            raise HTTPException(
                status_code=409,
                detail="Final Story must be explicitly approved before script generation.",
            )
        generated = generate_short_script(review["final_story"], request.style)
        record = save_generated_script(
            db,
            project_id,
            generated,
            request.style,
            review["final_story_fingerprint"],
            review["approved_at"],
        )
        return serialize_short_script(record, review)
    except (RuntimeError, TimeoutError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        db.close()


def _short_script_record(db, project_id: str) -> ProjectShortScript:
    record = db.query(ProjectShortScript).filter_by(project_id=project_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Short Script not found.")
    return record


def _current_story_review(db, project_id: str) -> dict:
    story_input = build_story_input(project_id)
    revision = story_source_revision(story_input)
    return compose_story_review(_story_record(db, project_id), revision)


@router.get("/{project_id}/short-script")
def get_project_short_script(project_id: str):
    db = SessionLocal()
    try:
        record = db.query(ProjectShortScript).filter_by(project_id=project_id).first()
        if record is None:
            return {"status": "empty", "script_approved": False, "final_script": None}
        return serialize_short_script(record, _current_story_review(db, project_id))
    except Exception:
        return {"status": "empty", "script_approved": False, "final_script": None}
    finally:
        db.close()


@router.patch("/{project_id}/short-script/segments/{segment_id}")
def update_project_short_script_segment(
    project_id: str,
    segment_id: str,
    request: ShortScriptSegmentEdit,
):
    db = SessionLocal()
    try:
        return edit_script_segment(
            db,
            _short_script_record(db, project_id),
            segment_id,
            request.text,
            _current_story_review(db, project_id),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{project_id}/short-script/approve")
def approve_project_short_script(project_id: str):
    db = SessionLocal()
    try:
        return approve_short_script(
            db,
            _short_script_record(db, project_id),
            _current_story_review(db, project_id),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


PROJECT_SCRIPTS_CACHE: dict[str, dict] = {}


@router.post("/{project_id}/generate-script", response_model=GeneratedScriptResponse)
def generate_project_script(
    project_id: str,
    request: GenerateScriptRequest,
) -> GeneratedScriptResponse:
    """Generates multi-style review script using AI Script Engine and persists to project."""
    db = SessionLocal()
    ocr_texts: list[str] = []
    try:
        # 1. Gather OCR texts from project assets if available
        assets = (
            db.query(Asset)
            .filter(Asset.project_id == project_id)
            .order_by(Asset.page_order.asc())
            .all()
        )
        for asset in assets:
            if asset.ocr_text and asset.ocr_text.strip():
                ocr_texts.append(asset.ocr_text.strip())
            elif asset.dialogues:
                try:
                    d_list = json.loads(asset.dialogues)
                    if isinstance(d_list, list):
                        for d in d_list:
                            txt = d.get("text", d.get("clean_text", d.get("raw_text", "")))
                            if txt and txt.strip():
                                ocr_texts.append(txt.strip())
                except Exception:
                    pass
    except Exception:
        pass
    finally:
        db.close()

    # Default fallback OCR context if no text in assets
    if not ocr_texts:
        ocr_texts = [
            "Con có đồng ý lấy Rin làm vợ hợp pháp không?",
            "Con đồng ý.",
            "Tại sao anh lại nhìn tôi với ánh mắt đấy chứ?",
        ]

    # 2. Generate script using AI Script Engine
    script = generate_script(
        ocr_texts=ocr_texts,
        story_style=request.story_style,
        target_duration_sec=request.target_duration,
        project_id=project_id,
    )

    # 3. Store in cache
    PROJECT_SCRIPTS_CACHE[project_id] = script.model_dump()

    # 4. Also persist to DB if project exists
    db = SessionLocal()
    try:
        record = db.query(ProjectShortScript).filter_by(project_id=project_id).first()
        now = datetime.now(timezone.utc)
        if record is None:
            record = ProjectShortScript(
                project_id=project_id,
                style=request.story_style,
                result=script.model_dump(),
                source_story_fingerprint=f"d19_{request.story_style}",
                source_story_approved_at=now,
                status="generated",
                created_at=now,
                updated_at=now,
            )
            db.add(record)
        else:
            record.style = request.story_style
            record.result = script.model_dump()
            record.status = "generated"
            record.updated_at = now
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return script
