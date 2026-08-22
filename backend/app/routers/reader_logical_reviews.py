from fastapi import APIRouter,HTTPException,Response
from pydantic import BaseModel
from app.database import SessionLocal
from app.models.project import Project
from app.services.reader_logical_review import crop_bytes,image_bytes,save_order,save_transcription,serialize
router=APIRouter(prefix="/projects/{project_id}/reader-logical-review",tags=["Reader Logical Review"])
class OrderAction(BaseModel):ordered_region_ids:list[str];excluded_region_ids:list[str];verified:bool=False
class TextAction(BaseModel):text:str
def require(db,pid):
 if not db.get(Project,pid):raise HTTPException(404,"Project not found")
@router.get("")
def queue(project_id:str):
 db=SessionLocal()
 try:require(db,project_id);return serialize(db,project_id)
 finally:db.close()
@router.get("/{review_id:path}/image")
def image(project_id:str,review_id:str):
 db=SessionLocal()
 try:require(db,project_id);return Response(image_bytes(db,project_id,review_id),media_type="image/jpeg")
 finally:db.close()
@router.get("/{review_id:path}/logical-regions/{logical_region_id}/crop")
def crop(project_id:str,review_id:str,logical_region_id:str):
 db=SessionLocal()
 try:require(db,project_id);return Response(crop_bytes(db,project_id,review_id,logical_region_id),media_type="image/png")
 finally:db.close()
@router.post("/{review_id:path}/order")
def persist_order(project_id:str,review_id:str,action:OrderAction):
 db=SessionLocal()
 try:require(db,project_id);return save_order(db,project_id,review_id,action.ordered_region_ids,action.excluded_region_ids,action.verified)
 finally:db.close()
@router.post("/{review_id:path}/logical-regions/{logical_region_id}/transcription")
def persist_text(project_id:str,review_id:str,logical_region_id:str,action:TextAction):
 db=SessionLocal()
 try:require(db,project_id);return save_transcription(db,project_id,review_id,logical_region_id,action.text)
 finally:db.close()
