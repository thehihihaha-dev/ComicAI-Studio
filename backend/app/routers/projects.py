from uuid import uuid4
from datetime import datetime, timezone

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.projects import ProjectCreate, ShortScriptCreate
from app.database import SessionLocal
from app.models.asset import Asset
from app.models.dialogue_ground_truth import DialogueGroundTruth
from app.models.project import Project
from sqlalchemy import select
from app.services.short_script_engine import generate_short_script
from app.services.story_input_builder import build_story_input
from app.services.story_reliability import run_reliable_story_analysis
projects = []
router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


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

        projects = [
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

        return {
            "message": "ComicAI Studio Project API",
            "projects": projects,
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
    db = SessionLocal()
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
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

    project = db.query(Project).filter(Project.id == project_id).first()

    db.close()

    return project


@router.get("/{project_id}/story-input")
def get_project_story_input(project_id: str):
    return build_story_input(project_id)


@router.post("/{project_id}/story-analysis")
def analyze_project_story(project_id: str):
    story_input = build_story_input(project_id)
    if story_input.get("status") != "ready":
        raise HTTPException(
            status_code=409,
            detail="Project pages are not ready for story analysis.",
        )
    try:
        return run_reliable_story_analysis(story_input)
    except (RuntimeError, TimeoutError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/{project_id}/short-script")
def create_project_short_script(project_id: str, request: ShortScriptCreate):
    story_input = build_story_input(project_id)
    if story_input.get("status") != "ready":
        raise HTTPException(
            status_code=409,
            detail="Project pages are not ready for script generation.",
        )
    try:
        reliability = run_reliable_story_analysis(story_input)
        return generate_short_script(reliability, request.style)
    except (RuntimeError, TimeoutError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
