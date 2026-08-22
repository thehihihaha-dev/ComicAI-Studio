from typing import Literal
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from app.database import SessionLocal
from app.models.project import Project
from app.services.reader_correctness_review import crop_bytes,image_bytes,save_ocr,save_reading,serialize_queue

router=APIRouter(prefix="/projects/{project_id}/reader-correctness-review",tags=["Reader Correctness Review"])
class Group(BaseModel):group_id:str;region_ids:list[int]
class ReadingAction(BaseModel):
    sequence:list[int];groups:list[Group];dispositions:dict[str,Literal["ORDERED","ORPHAN","AMBIGUOUS","EXCLUDED"]]={}
class OcrAction(BaseModel):state:Literal["VERIFIED","UNREADABLE"];transcription:str|None=None
def require_project(db,project_id):
    if db.get(Project,project_id) is None:raise HTTPException(404,"Project not found")
@router.get("")
def queue(project_id:str):
    db=SessionLocal()
    try:require_project(db,project_id);return serialize_queue(db,project_id)
    finally:db.close()
@router.get("/{review_id:path}/image")
def image(project_id:str,review_id:str):
    db=SessionLocal()
    try:require_project(db,project_id);return Response(image_bytes(db,project_id,review_id),media_type="image/jpeg")
    finally:db.close()
@router.get("/{review_id:path}/regions/{region_id}/crop")
def crop(project_id:str,review_id:str,region_id:int):
    db=SessionLocal()
    try:require_project(db,project_id);return Response(crop_bytes(db,project_id,review_id,region_id),media_type="image/png")
    finally:db.close()
@router.post("/{review_id:path}/reading")
def reading(project_id:str,review_id:str,action:ReadingAction):
    db=SessionLocal()
    try:require_project(db,project_id);return save_reading(db,project_id,review_id,action.sequence,[x.model_dump() for x in action.groups],action.dispositions)
    finally:db.close()
@router.post("/{review_id:path}/regions/{region_id}/ocr")
def ocr(project_id:str,review_id:str,region_id:int,action:OcrAction):
    db=SessionLocal()
    try:require_project(db,project_id);return save_ocr(db,project_id,review_id,region_id,action.state,action.transcription)
    finally:db.close()
