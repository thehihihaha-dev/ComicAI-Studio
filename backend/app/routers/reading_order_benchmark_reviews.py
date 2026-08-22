from typing import Literal
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from app.database import SessionLocal
from app.models.project import Project
from app.services.reading_order_benchmark_review import image_bytes, save_review, serialize_queue

router = APIRouter(prefix="/projects/{project_id}/reading-order-benchmark-review", tags=["Reading Order Benchmark Review"])

class Group(BaseModel):
    group_id: str
    region_ids: list[int]
class ReviewAction(BaseModel):
    sequence: list[int]
    groups: list[Group]
    dispositions: dict[str, Literal["ORDERED", "ORPHAN", "AMBIGUOUS", "EXCLUDED"]] = {}

def require_project(db, project_id):
    if db.get(Project, project_id) is None: raise HTTPException(404, "Project not found")

@router.get("")
def queue(project_id: str):
    db=SessionLocal()
    try: require_project(db,project_id); return serialize_queue(db,project_id)
    finally: db.close()

@router.get("/{review_id:path}/image")
def image(project_id: str, review_id: str):
    db=SessionLocal()
    try: require_project(db,project_id); return Response(image_bytes(db,project_id,review_id),media_type="image/jpeg")
    finally: db.close()

@router.post("/{review_id:path}")
def save(project_id: str, review_id: str, action: ReviewAction):
    db=SessionLocal()
    try: require_project(db,project_id); return save_review(db,project_id,review_id,action.sequence,[x.model_dump() for x in action.groups],action.dispositions)
    finally: db.close()
