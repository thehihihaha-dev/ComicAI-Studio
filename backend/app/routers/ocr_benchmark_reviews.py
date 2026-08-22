from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.database import SessionLocal
from app.models.project import Project
from app.services.ocr_benchmark_review import crop_response, serialize_queue, update_review


router = APIRouter(prefix="/projects/{project_id}/ocr-benchmark-review", tags=["OCR Benchmark Review"])


class ReviewAction(BaseModel):
    state: Literal["VERIFIED", "SKIPPED", "UNREADABLE"]
    transcription: str | None = None


def require_project(db, project_id: str) -> None:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("")
def get_ocr_benchmark_queue(project_id: str):
    db = SessionLocal()
    try:
        require_project(db, project_id)
        return serialize_queue(db, project_id)
    finally:
        db.close()


@router.get("/{sample_id}/crop")
def get_ocr_benchmark_crop(project_id: str, sample_id: str):
    db = SessionLocal()
    try:
        require_project(db, project_id)
        return Response(content=crop_response(db, project_id, sample_id), media_type="image/png")
    finally:
        db.close()


@router.post("/{sample_id}")
def save_ocr_benchmark_review(project_id: str, sample_id: str, action: ReviewAction):
    db = SessionLocal()
    try:
        require_project(db, project_id)
        return update_review(db, project_id, sample_id, action.state, action.transcription)
    finally:
        db.close()
