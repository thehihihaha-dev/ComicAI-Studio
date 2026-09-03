from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.database import SessionLocal
from app.services.panel_ground_truth_review import image_bytes, save_review, serialize_queue

router = APIRouter(prefix="/panel-ground-truth", tags=["Panel Ground Truth"])


class HumanPanel(BaseModel):
    panel_id: str
    bbox: list[float]
    ambiguous: bool = False


class SaveAction(BaseModel):
    panels: list[HumanPanel]


@router.get("")
def queue():
    db = SessionLocal()
    try:
        return serialize_queue(db)
    finally:
        db.close()


@router.get("/{review_id:path}/image")
def image(review_id: str):
    db = SessionLocal()
    try:
        return Response(image_bytes(db, review_id), media_type="image/jpeg")
    finally:
        db.close()


@router.post("/{review_id:path}")
def save(review_id: str, action: SaveAction):
    db = SessionLocal()
    try:
        return save_review(db, review_id, [panel.model_dump() for panel in action.panels])
    finally:
        db.close()
