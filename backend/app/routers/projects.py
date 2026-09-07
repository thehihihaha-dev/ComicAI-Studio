from uuid import uuid4
from datetime import datetime, timezone
from typing import Any

from pathlib import Path
import re
import logging

from fastapi import APIRouter, HTTPException, File, UploadFile

logger = logging.getLogger(__name__)

from app.schemas.projects import (
    AutoAlignChapterRequest,
    GenerateScriptRequest,
    IngestChapterRequest,
    ProjectCreate,
    ProjectRenderRequest,
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
        normalize_style,
    )
    from src.services.chapter_service import (
        ChapterMetadata,
        CHAPTER_METADATA_CACHE,
        ingest_chapter,
    )
    from src.services.smart_selector import (
        SelectedPanel,
        select_keyframe_panels,
        convert_to_visual_clips,
    )
    from src.services.unified_tts import (
        UnifiedTTSManager,
        UNIFIED_VOICE_ID,
    )
    from src.services.audio_ducking import (
        generate_ducking_keyframes,
        build_ffmpeg_ducking_filter,
    )
    from src.services.video_renderer import (
        VideoRenderer,
    )
    from src.api.timeline_schema import (
        AudioClip,
        RenderResponse,
        TimelineContract,
        VisualClip,
    )
except ModuleNotFoundError:
    from backend.src.services.script_generator import (
        GeneratedScriptResponse,
        generate_script,
        normalize_style,
    )
    from backend.src.services.chapter_service import (
        ChapterMetadata,
        CHAPTER_METADATA_CACHE,
        ingest_chapter,
    )
    from backend.src.services.smart_selector import (
        SelectedPanel,
        select_keyframe_panels,
        convert_to_visual_clips,
    )
    from backend.src.services.unified_tts import (
        UnifiedTTSManager,
        UNIFIED_VOICE_ID,
    )
    from backend.src.services.audio_ducking import (
        generate_ducking_keyframes,
        build_ffmpeg_ducking_filter,
    )
    from backend.src.services.video_renderer import (
        VideoRenderer,
    )
    from backend.src.api.timeline_schema import (
        AudioClip,
        RenderResponse,
        TimelineContract,
        VisualClip,
    )
from app.database import SessionLocal
from app.models.asset import Asset
from app.models.dialogue_ground_truth import DialogueGroundTruth
from app.models.project import Project
from app.models.project_story_analysis import ProjectStoryAnalysis
from app.models.project_short_script import ProjectShortScript
from sqlalchemy import func, select
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
            .filter(Asset.project_id == Project.id)
            .order_by(Asset.page_order.asc())
            .limit(1)
            .scalar_subquery()
        )

        projects = (
            db.query(
                Project.id,
                Project.name,
                Project.content_type,
                Project.status,
                Project.created_at,
                thumbnail_path.label("thumbnail_path"),
            )
            .order_by(Project.created_at.desc())
            .all()
        )

        result = []
        for p in projects:
            thumb = p.thumbnail_path
            if thumb and not thumb.startswith("http"):
                clean = thumb.replace("\\", "/").replace("backend/", "").lstrip("/")
                thumb = f"http://127.0.0.1:8000/{clean}"
            result.append({
                "id": p.id,
                "name": p.name,
                "content_type": p.content_type,
                "status": p.status,
                "created_at": p.created_at,
                "thumbnail_url": thumb,
            })

        return {
            "projects": result,
            "total": len(result),
        }
    except Exception:
        return {
            "projects": [DEFAULT_PROJECT_RECORD],
            "total": 1,
        }
    finally:
        db.close()
@router.post("/")
def create_project(project: ProjectCreate):
    proj_id = project.id or str(uuid4())
    db = SessionLocal()
    try:
        existing = db.query(Project).filter(Project.id == proj_id).first()
        if existing is not None:
            return {
                "id": existing.id,
                "name": existing.name,
                "content_type": existing.content_type,
                "status": existing.status,
                "created_at": existing.created_at.isoformat() if existing.created_at else None,
            }

        new_project = Project(
            id=proj_id,
            name=project.name,
            content_type=project.content_type,
            status="created",
            created_at=datetime.now(timezone.utc),
        )
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

        return {
            "id": new_project.id,
            "name": new_project.name,
            "content_type": new_project.content_type,
            "status": new_project.status,
            "created_at": new_project.created_at.isoformat() if new_project.created_at else None,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
            timeline_data = getattr(project, "timeline_data", None) or PROJECT_TIMELINES_CACHE.get(project_id)
            script_content = getattr(project, "script_content", None) or PROJECT_SCRIPTS_CACHE.get(project_id)
            return {
                "id": project.id,
                "name": project.name,
                "content_type": project.content_type,
                "status": project.status,
                "created_at": project.created_at.isoformat() if project.created_at else None,
                "timeline_data": timeline_data,
                "script_content": script_content,
            }
    except Exception:
        pass
    finally:
        db.close()

    if project_id in (DEFAULT_PROJECT_ID, "project_wedding_vows"):
        return {
            "id": project_id,
            "name": "Vợ trong game của tôi là Idol nổi tiếng ngoài đời",
            "content_type": "short",
            "status": "ready",
            "created_at": "2026-08-22T23:00:00Z",
            "timeline_data": PROJECT_TIMELINES_CACHE.get(project_id),
            "script_content": PROJECT_SCRIPTS_CACHE.get(project_id),
        }

    if project_id in PROJECT_TIMELINES_CACHE or project_id in PROJECT_SCRIPTS_CACHE:
        return {
            "id": project_id,
            "name": "Chapter Review",
            "content_type": "short",
            "status": "ready",
            "created_at": "2026-08-22T23:00:00Z",
            "timeline_data": PROJECT_TIMELINES_CACHE.get(project_id),
            "script_content": PROJECT_SCRIPTS_CACHE.get(project_id),
        }

    raise HTTPException(status_code=404, detail="Project not found")


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
PROJECT_TIMELINES_CACHE: dict[str, dict] = {}


def ensure_project_columns():
    """Ensure timeline_data and script_content columns exist on projects table."""
    try:
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS timeline_data JSONB;"))
                conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS script_content JSONB;"))
                conn.commit()
            elif engine.dialect.name == "sqlite":
                cursor = conn.connection.cursor()
                cursor.execute("PRAGMA table_info(projects)")
                cols = [row[1] for row in cursor.fetchall()]
                if "timeline_data" not in cols:
                    conn.execute(text("ALTER TABLE projects ADD COLUMN timeline_data JSON;"))
                if "script_content" not in cols:
                    conn.execute(text("ALTER TABLE projects ADD COLUMN script_content JSON;"))
                conn.commit()
    except Exception as e:
        logger.debug(f"ensure_project_columns notice: {e}")


ensure_project_columns()



@router.post("/{project_id}/generate-script", response_model=GeneratedScriptResponse)
async def generate_project_script(
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
    norm_style = normalize_style(request.story_style)
    script = generate_script(
        ocr_texts=ocr_texts,
        story_style=norm_style,
        target_duration_sec=request.target_duration,
        project_id=project_id,
    )

    # 3. Synthesize voice audio with Edge-TTS and stitch preview speech track
    try:
        tts_manager = UnifiedTTSManager(offline_fallback=True)
        out_dir = Path(__file__).resolve().parents[2] / "uploads" / "audio" / project_id
        out_dir.mkdir(parents=True, exist_ok=True)
        synthesized_segments = await tts_manager.synthesize_script(script, out_dir)

        # Stitch continuous preview audio for instant web playback
        preview_audio_path = out_dir / "preview_full.mp3"
        try:
            tts_manager.stitch_speech_track(synthesized_segments, preview_audio_path)
            script.preview_audio_url = f"/uploads/audio/{project_id}/preview_full.mp3"
        except Exception as stitch_err:
            logger.warning(f"stitch_speech_track warning: {stitch_err}")

        # Attach audio_url to each segment
        seg_map = {
            seg["segment_id"]: f"/uploads/audio/{project_id}/{Path(seg['file_path']).name}"
            for seg in synthesized_segments
        }
        for s in script.segments:
            if s.id in seg_map:
                s.audio_url = seg_map[s.id]
    except Exception as tts_err:
        logger.warning(f"TTS synthesis warning in generate-script: {tts_err}")

    # 4. Store in cache
    PROJECT_SCRIPTS_CACHE[project_id] = script.model_dump()

    # 4. Also persist to DB if project exists
    db = SessionLocal()
    try:
        record = db.query(ProjectShortScript).filter_by(project_id=project_id).first()
        now = datetime.now(timezone.utc)
        if record is None:
            record = ProjectShortScript(
                project_id=project_id,
                style=norm_style,
                result=script.model_dump(),
                source_story_fingerprint=f"d19_{norm_style}",
                source_story_approved_at=now,
                status="generated",
                created_at=now,
                updated_at=now,
            )
            db.add(record)
        else:
            record.style = norm_style
            record.result = script.model_dump()
            record.status = "generated"
            record.updated_at = now
        proj = db.query(Project).filter_by(id=project_id).first()
        if proj is not None:
            proj.script_content = script.model_dump()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return script


@router.get("/{project_id}/review-scenes")
async def get_project_review_scenes(
    project_id: str,
    story_style: str = "dramatic",
) -> list[dict[str, Any]]:
    """Returns AI review scenes in the strict TikTok storytelling schema: [ { scene_index, stage, visual_direction, voiceover, target_page_hint } ]."""
    cached = PROJECT_SCRIPTS_CACHE.get(project_id)
    if cached and "scenes" in cached and cached["scenes"]:
        return cached["scenes"]

    db = SessionLocal()
    ocr_texts: list[str] = []
    try:
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

    script = generate_script(
        ocr_texts=ocr_texts,
        story_style=normalize_style(story_style),
        project_id=project_id,
    )
    return script.to_scenes_json()


@router.post("/{project_id}/ingest-chapter")
async def ingest_chapter_endpoint(
    project_id: str,
    request: IngestChapterRequest | None = None,
):
    try:
        db = SessionLocal()
    except Exception:
        db = None

    try:
        saved_paths: list[Path] = []

        if request:
            if request.image_paths:
                saved_paths = [Path(p) for p in request.image_paths if Path(p).is_file()]
            elif request.chapter_dir:
                d = Path(request.chapter_dir)
                if d.is_dir():
                    supported = {".jpg", ".jpeg", ".png", ".webp"}
                    saved_paths = sorted([p for p in d.iterdir() if p.suffix.lower() in supported])

        # Fallback: check existing assets for project
        if not saved_paths and db is not None:
            try:
                assets = db.query(Asset).filter(Asset.project_id == project_id).order_by(Asset.page_order.asc()).all()
                for asset in assets:
                    p = Path(asset.file_path)
                    if not p.is_absolute():
                        p = Path(__file__).resolve().parents[2] / asset.file_path
                    if p.is_file():
                        saved_paths.append(p)
            except Exception:
                pass

        # Fallback 2: check uploads dir
        if not saved_paths:
            uploads_dir = Path(__file__).resolve().parents[2] / "uploads"
            sample_files = sorted(list(uploads_dir.glob(f"{DEFAULT_PROJECT_ID}*.jpg")))
            if sample_files:
                saved_paths = sample_files[:10]

        if not saved_paths:
            raise HTTPException(status_code=400, detail="No chapter image files found for ingestion")

        metadata = ingest_chapter(
            project_id=project_id,
            chapter_folder_or_files=saved_paths,
            db=db,
        )
        return metadata
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


@router.post("/{project_id}/upload-pages")
async def upload_project_pages(
    project_id: str,
    files: list[UploadFile] = File(...),
):
    """Uploads multiple chapter manga pages and saves them permanently to the project."""
    db = SessionLocal()
    try:
        # 1. Ensure project exists in DB
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj is None:
            proj = Project(
                id=project_id,
                name=f"Project {project_id[:8]}",
                content_type="short",
                status="ready",
                created_at=datetime.now(timezone.utc),
            )
            db.add(proj)
            db.commit()
            db.refresh(proj)

        # 2. Find current max page_order
        max_order = (
            db.query(func.max(Asset.page_order))
            .filter(Asset.project_id == project_id)
            .scalar()
            or 0
        )

        # 3. Create target directory
        project_upload_dir = Path(__file__).resolve().parents[2] / "uploads" / project_id
        project_upload_dir.mkdir(parents=True, exist_ok=True)

        from app.services.asset_processor import natural_sort_key
        sorted_files = sorted(files, key=lambda f: natural_sort_key(f.filename or ""))

        saved_assets: list[Asset] = []
        for idx, file in enumerate(sorted_files, start=1):
            order = max_order + idx
            ext = Path(file.filename or "").suffix.lower()
            if ext not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                ext = ".jpg"
            disk_filename = f"page_{order:02d}{ext}"
            file_dest = project_upload_dir / disk_filename

            content = await file.read()
            file_dest.write_bytes(content)

            rel_path = f"uploads/{project_id}/{disk_filename}"
            asset = Asset(
                id=str(uuid4()),
                project_id=project_id,
                filename=file.filename or disk_filename,
                file_type="image/jpeg" if ext in {".jpg", ".jpeg"} else f"image/{ext.lstrip('.')}",
                file_path=rel_path,
                page_order=order,
                created_at=datetime.now(timezone.utc),
                status="ready",
            )
            db.add(asset)
            saved_assets.append(asset)

        db.commit()

        # 4. Ingest chapter so metadata cache and panel extraction is fresh
        all_project_assets = (
            db.query(Asset)
            .filter(Asset.project_id == project_id)
            .order_by(Asset.page_order.asc())
            .all()
        )
        asset_file_paths = [
            Path(__file__).resolve().parents[2] / a.file_path
            for a in all_project_assets
            if (Path(__file__).resolve().parents[2] / a.file_path).is_file()
        ]
        try:
            ingest_chapter(project_id, asset_file_paths, db=db)
        except Exception as e:
            logger.warning(f"Chapter auto-ingestion warning: {e}")

        return {
            "project_id": project_id,
            "total_pages": len(all_project_assets),
            "uploaded_count": len(saved_assets),
            "pages": [
                {
                    "id": a.id,
                    "page_order": a.page_order,
                    "filename": a.filename,
                    "file_path": a.file_path,
                    "url": f"http://127.0.0.1:8000/{a.file_path}",
                    "status": a.status,
                }
                for a in all_project_assets
            ],
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{project_id}/auto-align-chapter")
async def auto_align_chapter_endpoint(
    project_id: str,
    request: AutoAlignChapterRequest | None = None,
):
    if request is None:
        request = AutoAlignChapterRequest()

    try:
        db = SessionLocal()
    except Exception:
        db = None

    try:
        chapter_dict = CHAPTER_METADATA_CACHE.get(project_id)
        if chapter_dict and chapter_dict.get("total_pages", 0) > 1:
            chapter_meta = ChapterMetadata(**chapter_dict)
        else:
            asset_paths: list[Path] = []
            if db is not None:
                try:
                    assets = db.query(Asset).filter(Asset.project_id == project_id).order_by(Asset.page_order.asc()).all()
                    for a in assets:
                        p = Path(a.file_path)
                        if not p.is_absolute():
                            p = Path(__file__).resolve().parents[2] / a.file_path
                        if p.is_file():
                            asset_paths.append(p)
                except Exception:
                    pass

            if not asset_paths:
                proj_upload_dir = Path(__file__).resolve().parents[2] / "uploads" / project_id
                if proj_upload_dir.is_dir():
                    from app.services.asset_processor import natural_sort_key
                    disk_files = [
                        f for f in proj_upload_dir.iterdir()
                        if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                    ]
                    disk_files.sort(key=lambda p: natural_sort_key(p.name))
                    if disk_files:
                        asset_paths = disk_files

            if len(asset_paths) <= 1 and project_id in (DEFAULT_PROJECT_ID, "project_wedding_vows"):
                uploads_dir = Path(__file__).resolve().parents[2] / "uploads"
                manga_files = list(uploads_dir.glob("*vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-*.jpg"))
                if not manga_files:
                    manga_files = [f for f in uploads_dir.glob("*.jpg") if not f.name.startswith("temp_") and not f.name.startswith("render_")]

                def extract_page_num(path: Path) -> int:
                    m = re.search(r'-(\d+)\.jpg$', path.name)
                    if m:
                        return int(m.group(1))
                    m2 = re.search(r'(\d+)', path.name)
                    return int(m2.group(1)) if m2 else 999

                manga_files.sort(key=extract_page_num)
                if manga_files:
                    asset_paths = manga_files[:15]

            if not asset_paths:
                raise HTTPException(status_code=400, detail="Dự án chưa có trang truyện. Vui lòng upload chapter trước khi tạo video.")
            chapter_meta = ingest_chapter(project_id, asset_paths, db=db)

        # 2. Get or reuse existing script, fallback to generation
        norm_style = normalize_style(request.story_style)
        client_script = request.existing_script or request.custom_script
        db_script = None
        if db is not None:
            try:
                proj_record = db.query(Project).filter(Project.id == project_id).first()
                if proj_record and proj_record.script_content:
                    db_script = proj_record.script_content
            except Exception:
                pass
        if not db_script:
            db_script = PROJECT_SCRIPTS_CACHE.get(project_id)

        if client_script:
            script = GeneratedScriptResponse(**client_script)
        elif db_script and isinstance(db_script, dict) and db_script.get("segments"):
            script = GeneratedScriptResponse(**db_script)
        else:
            script = generate_script(
                ocr_texts=chapter_meta.all_ocr_texts,
                story_style=norm_style,
                target_duration_sec=request.target_duration,
                project_id=project_id,
            )

        # 3. Synthesize voice audio track
        tts_manager = UnifiedTTSManager(offline_fallback=True)
        out_dir = Path(__file__).resolve().parents[2] / "uploads" / "audio" / project_id
        out_dir.mkdir(parents=True, exist_ok=True)
        synthesized_segments = await tts_manager.synthesize_script(script, out_dir)

        # Stitch continuous preview audio for instant web playback
        preview_audio_url: str | None = None
        preview_audio_path = out_dir / "preview_full.mp3"
        try:
            tts_manager.stitch_speech_track(synthesized_segments, preview_audio_path)
            preview_audio_url = f"/uploads/audio/{project_id}/preview_full.mp3"
        except Exception:
            pass

        # 4. Build audio clips and track intervals
        audio_clips: list[AudioClip] = []
        voice_intervals: list[tuple[float, float]] = []

        for seg in synthesized_segments:
            clip = AudioClip(
                clip_id=f"AUD_{seg['segment_id']}",
                dialogue_id=seg["segment_id"],
                speaker_label="NAMMINH",
                voice_id=UNIFIED_VOICE_ID,
                text=seg["text"],
                file_path=seg["file_path"],
                audio_url=f"/uploads/audio/{project_id}/{Path(seg['file_path']).name}",
                start_time=seg["start_time"],
                end_time=seg["end_time"],
                duration=seg["duration"],
                source="ai_review_script",
            )
            audio_clips.append(clip)
            voice_intervals.append((seg["start_time"], seg["end_time"]))

        # 5. Select keyframe panels with 1:1 audio clip synchronization
        selected_panels = select_keyframe_panels(
            chapter_data=chapter_meta,
            script=script,
            target_count=request.target_panel_count,
            audio_clips=audio_clips,
        )

        # 6. Audio Ducking
        total_audio_duration = audio_clips[-1].end_time if audio_clips else script.total_duration
        ducking_keyframes = generate_ducking_keyframes(
            voice_intervals=voice_intervals,
            total_duration=total_audio_duration,
        )
        ducking_filter = build_ffmpeg_ducking_filter(voice_intervals=voice_intervals)

        # 7. Visual Clips
        visual_clips = convert_to_visual_clips(selected_panels)
        if visual_clips and visual_clips[-1].end_time < total_audio_duration:
            visual_clips[-1].end_time = total_audio_duration
            visual_clips[-1].duration = round(total_audio_duration - visual_clips[-1].start_time, 3)

        raw_source_img = chapter_meta.pages[0].image_path if chapter_meta.pages else "chapter_01.jpg"
        source_img = str(raw_source_img).replace("\\", "/")
        if "uploads/" in source_img:
            source_img = source_img[source_img.index("uploads/"):]
        elif source_img.startswith("backend/"):
            source_img = source_img[len("backend/"):]

        timeline = TimelineContract(
            version="1.0.0",
            project_id=project_id,
            page_id=1,
            source_image_path=source_img,
            image_dimensions=(900, 1280),
            canvas_size=(1080, 1920),
            fps=30.0,
            total_duration=round(max(total_audio_duration, visual_clips[-1].end_time if visual_clips else 0.0), 3),
            visual_clips=visual_clips,
            audio_clips=audio_clips,
            metadata={
                "chapter_id": chapter_meta.chapter_id,
                "total_chapter_pages": chapter_meta.total_pages,
                "total_chapter_panels": chapter_meta.total_panels,
                "selected_panel_count": len(selected_panels),
                "story_style": norm_style,
                "preview_audio_url": preview_audio_url,
                "bgm_path": None,
                "script": script.model_dump(),
                "scenes": [s.model_dump() for s in script.scenes] if script.scenes else [],
                "ducking": {
                    "keyframes": ducking_keyframes,
                    "ffmpeg_filter": ducking_filter,
                    "voice_intervals": voice_intervals,
                },
            },
        )

        PROJECT_TIMELINES_CACHE[project_id] = timeline.model_dump()
        PROJECT_SCRIPTS_CACHE[project_id] = script.model_dump()

        if db is not None:
            try:
                proj_record = db.query(Project).filter(Project.id == project_id).first()
                if proj_record is not None:
                    proj_record.timeline_data = timeline.model_dump()
                    proj_record.script_content = script.model_dump()
                    db.commit()
            except Exception as save_err:
                logger.warning(f"Could not persist timeline to Project DB: {save_err}")
                db.rollback()

        return timeline
    finally:
        if db is not None:
            db.close()


@router.put("/{project_id}/timeline")
@router.post("/{project_id}/timeline")
async def save_project_timeline(
    project_id: str,
    payload: dict[str, Any],
):
    """Saves or updates timeline contract for a project."""
    PROJECT_TIMELINES_CACHE[project_id] = payload
    try:
        db = SessionLocal()
    except Exception:
        db = None

    if db is not None:
        try:
            proj_record = db.query(Project).filter(Project.id == project_id).first()
            if proj_record is not None:
                proj_record.timeline_data = payload
                db.commit()
                return {"status": "success", "message": "Timeline saved successfully"}
        except Exception as exc:
            db.rollback()
            return {"status": "warning", "message": str(exc)}
        finally:
            db.close()
    return {"status": "cached", "message": "Timeline saved in cache"}



@router.post(
    "/{project_id}/render",
    response_model=RenderResponse,
    summary="Render Final Broadcast 9:16 Video",
    description="Synthesizes final broadcast-ready 9:16 vertical MP4 video strictly adhering to TimelineContract.",
)
async def render_project_video(
    project_id: str,
    payload: ProjectRenderRequest | None = None,
) -> RenderResponse:
    """Render 9:16 MP4 video from project timeline or auto-align chapter."""
    req = payload or ProjectRenderRequest()
    timeline: TimelineContract

    if req.timeline:
        timeline = TimelineContract(**req.timeline)
    else:
        # Auto-align chapter to generate canonical timeline contract
        align_req = AutoAlignChapterRequest(
            story_style=req.story_style,
        )
        timeline = await auto_align_chapter_endpoint(project_id, align_req)

    root_dir = Path(__file__).resolve().parents[3]
    out_dir = root_dir / "artifacts" / "video" / "day20"
    out_dir.mkdir(parents=True, exist_ok=True)

    if req.output_filename:
        safe_fname = Path(req.output_filename).name
        if not safe_fname.endswith(".mp4"):
            safe_fname += ".mp4"
    else:
        safe_fname = f"render_{project_id}_{uuid4().hex[:8]}.mp4"

    output_path = out_dir / safe_fname
    renderer = VideoRenderer(
        canvas_size=timeline.canvas_size,
        fps=timeline.fps,
    )

    bgm_p: Path | None = None
    if req.bgm_path:
        bgm_p = Path(req.bgm_path)
    elif timeline.metadata.get("bgm_path"):
        bgm_p = Path(str(timeline.metadata["bgm_path"]))

    try:
        render_summary = renderer.render_chapter_video(
            timeline=timeline,
            output_path=output_path,
            bgm_path=bgm_p,
        )
        return RenderResponse(**render_summary)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Video rendering failed: {exc}",
        )


