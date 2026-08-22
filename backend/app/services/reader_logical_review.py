from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from io import BytesIO
from typing import Any
from fastapi import HTTPException
from PIL import Image
from sqlalchemy.orm import Session
from app.models.asset import Asset
from app.models.reader_correctness_review import ReaderCorrectnessReview
from app.models.reader_logical_review import ReaderLogicalReview
ROOT=Path(__file__).resolve().parents[3];MANIFEST=ROOT/"benchmarks/day11/reader-logical-region-sample-11.11.json"
def asset_path(a):
 p=Path(a.file_path);return p if p.is_absolute() else ROOT/"backend"/p
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def compatible(row,asset):return bool(asset and asset_path(asset).is_file() and digest(asset_path(asset))==row.source_image_hash)
def load(db:Session,project_id:str):
 data=json.loads(MANIFEST.read_text());rows=[]
 for item in data["pages"]:
  rid=f"reader-logical:{item['asset_id']}:{item['representation_hash'][:12]}";row=db.get(ReaderLogicalReview,rid)
  if not row:
   row=ReaderLogicalReview(review_id=rid,project_id=project_id,asset_id=item["asset_id"],page_order=item["page_order"],source_image_hash=item["source_hash"],representation_version=item["representation_version"],representation_hash=item["representation_hash"],logical_regions=item["logical_regions"],state="PENDING");db.add(row)
  rows.append((row,item))
 db.commit();return rows,data
def serialize(db:Session,project_id:str)->dict[str,Any]:
 pairs,data=load(db,project_id);items=[];legacy_incompatible=prior_incompatible=False;ocr_verified=ocr_unreadable=0
 for row,item in pairs:
  asset=db.get(Asset,row.asset_id);old=db.query(ReaderCorrectnessReview).filter_by(asset_id=row.asset_id).first();ok=compatible(row,asset);dims=None
  if ok:
   with Image.open(asset_path(asset)) as im:dims={"width":im.width,"height":im.height}
  if old:
   legacy_incompatible|=old.reading_state=="VERIFIED"
   ocr_verified+=sum(v.get("state")=="VERIFIED" for v in (old.ocr_reviews or {}).values());ocr_unreadable+=sum(v.get("state")=="UNREADABLE" for v in (old.ocr_reviews or {}).values())
  old_incompatible=bool(row.state=="VERIFIED" and row.human_ordered_region_ids is None);prior_incompatible|=old_incompatible;click_state=("PENDING" if old_incompatible else row.state) if ok else "SOURCE_UNAVAILABLE"
  items.append({"review_id":row.review_id,"asset_id":row.asset_id,"page_order":row.page_order,"state":click_state,"representation_version":row.representation_version,"human_representation_version":"click-dialogue-order.v2","representation_hash":row.representation_hash,"logical_regions":row.logical_regions,"ordered_region_ids":row.human_ordered_region_ids or [],"excluded_region_ids":row.human_excluded_region_ids or [],"human_transcriptions":row.human_transcriptions or {},"prediction":{"panel_order":item["predicted_panel_order"],"region_orders":item["predicted_region_orders"],"sequence":item["predicted_sequence"]},"image_dimensions":dims,"image_url":f"http://127.0.0.1:8000/projects/{project_id}/reader-logical-review/{row.review_id}/image" if ok else None})
 completed=sum(x["state"]=="VERIFIED" for x in items);logical_texts=sum(len(x["human_transcriptions"]) for x in items)
 return {"total_pages":len(items),"completed_pages":completed,"remaining_pages":len(items)-completed,"representation_confirmation_required":False,"legacy_fragment_gt_incompatible":legacy_incompatible,"prior_hierarchical_gt_incompatible":prior_incompatible,"ocr_samples_preserved":data["ocr_samples_preserved"],"completed_ocr_gt_regions":ocr_verified+ocr_unreadable,"remaining_ocr_gt_regions":max(0,data["ocr_samples_preserved"]-(ocr_verified+ocr_unreadable)),"logical_text_corrections":logical_texts,"items":items,"model_calls":{"vlm":0,"ollama":0}}
def image_bytes(db,project_id,review_id):
 row=db.get(ReaderLogicalReview,review_id);asset=db.get(Asset,row.asset_id) if row else None
 if not row or row.project_id!=project_id:raise HTTPException(404,"Review not found")
 if not compatible(row,asset):raise HTTPException(409,"SOURCE_UNAVAILABLE")
 return asset_path(asset).read_bytes()
def crop_bytes(db:Session,project_id:str,review_id:str,logical_region_id:str)->bytes:
 row=db.get(ReaderLogicalReview,review_id);asset=db.get(Asset,row.asset_id) if row else None
 if not row or row.project_id!=project_id:raise HTTPException(404,"Review not found")
 if not compatible(row,asset):raise HTTPException(409,"SOURCE_HASH_MISMATCH")
 region=next((r for r in row.logical_regions if r["logical_region_id"]==logical_region_id),None)
 if not region:raise HTTPException(404,"Logical region not found")
 x1,y1,x2,y2=region["bbox"]
 with Image.open(asset_path(asset)) as im:
  pad=24;box=(max(0,int(x1)-pad),max(0,int(y1)-pad),min(im.width,int(x2)+pad),min(im.height,int(y2)+pad));out=BytesIO();im.convert("RGB").crop(box).save(out,format="PNG");return out.getvalue()
def save_order(db:Session,project_id:str,review_id:str,ordered:list[str],excluded:list[str],verified:bool):
 row=db.get(ReaderLogicalReview,review_id);asset=db.get(Asset,row.asset_id) if row else None
 if not row or row.project_id!=project_id:raise HTTPException(404,"Review not found")
 if not compatible(row,asset):raise HTTPException(409,"SOURCE_HASH_MISMATCH")
 expected={r["logical_region_id"] for r in row.logical_regions}
 if len(ordered)!=len(set(ordered)) or len(excluded)!=len(set(excluded)) or set(ordered)&set(excluded) or not(set(ordered)|set(excluded))<=expected:raise HTTPException(422,"Invalid ordered/excluded logical regions")
 if verified and set(ordered)|set(excluded)!=expected:raise HTTPException(422,"Every logical region must be ordered or explicitly excluded")
 row.human_ordered_region_ids,row.human_excluded_region_ids=ordered,excluded;row.state="VERIFIED" if verified else "PENDING";row.revision+=1;row.updated_at=datetime.now(timezone.utc);db.add(row);db.commit();return {"state":row.state,"revision":row.revision,"ordered_region_ids":ordered,"excluded_region_ids":excluded}
def save_transcription(db:Session,project_id:str,review_id:str,logical_region_id:str,text:str):
 row=db.get(ReaderLogicalReview,review_id);asset=db.get(Asset,row.asset_id) if row else None
 if not row or row.project_id!=project_id:raise HTTPException(404,"Review not found")
 if not compatible(row,asset):raise HTTPException(409,"SOURCE_HASH_MISMATCH")
 if logical_region_id not in {r["logical_region_id"] for r in row.logical_regions}:raise HTTPException(404,"Logical region not found")
 clean=text.strip()
 if not clean:raise HTTPException(422,"Human transcription cannot be empty")
 values=dict(row.human_transcriptions or {});values[logical_region_id]=text;row.human_transcriptions=values;row.revision+=1;row.updated_at=datetime.now(timezone.utc);db.add(row);db.commit();return {"logical_region_id":logical_region_id,"human_text":text,"revision":row.revision}
