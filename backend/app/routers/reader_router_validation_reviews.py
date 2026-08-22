from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.database import SessionLocal
from app.models.project import Project
from app.services.reader_router_validation_review import crop_bytes, save_review, serialize_queue

router = APIRouter(prefix="/projects/{project_id}/reader-router-validation-review", tags=["Reader Router Validation Review"])


class ReviewAction(BaseModel):
    state: Literal["VERIFIED", "UNREADABLE"]
    transcription: str | None = None


def _project(db, project_id: str) -> None:
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")


@router.get("")
def queue(project_id: str):
    db = SessionLocal()
    try:
        _project(db, project_id)
        return serialize_queue(db, project_id)
    finally:
        db.close()


@router.get("/{sample_id:path}/crop")
def crop(project_id: str, sample_id: str):
    db = SessionLocal()
    try:
        _project(db, project_id)
        return Response(crop_bytes(db, project_id, sample_id), media_type="image/png")
    finally:
        db.close()


@router.post("/{sample_id:path}")
def save(project_id: str, sample_id: str, action: ReviewAction):
    db = SessionLocal()
    try:
        _project(db, project_id)
        return save_review(db, project_id, sample_id, action.state, action.transcription)
    finally:
        db.close()
