from __future__ import annotations

import hashlib, json
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.project import Project  # noqa:F401
from app.models.reader_correctness_review import ReaderCorrectnessReview

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "benchmarks/day11/reader-v2-correctness-review-sample-11.11.json"


def asset_path(asset: Asset) -> Path:
    path = Path(asset.file_path)
    return path if path.is_absolute() else ROOT / "backend" / path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compatible(row: ReaderCorrectnessReview, asset: Asset | None) -> bool:
    return bool(asset and asset.project_id == row.project_id and asset_path(asset).is_file()
                and digest(asset_path(asset)) == row.source_image_hash)


def load_queue(db: Session, project_id: str) -> list[ReaderCorrectnessReview]:
    if not MANIFEST.is_file():
        raise HTTPException(503, "Checkpoint 11.11 review manifest is unavailable")
    manifest = json.loads(MANIFEST.read_text())
    for item in manifest["pages"]:
        review_id = f"reader-correctness:{item['asset_id']}"
        if db.get(ReaderCorrectnessReview, review_id):
            continue
        asset = db.get(Asset, item["asset_id"])
        if not asset or asset.project_id != project_id:
            continue
        path = asset_path(asset); source_ok = path.is_file() and digest(path) == item["source_hash"]
        regions = item["regions"]
        db.add(ReaderCorrectnessReview(
            review_id=review_id, project_id=project_id, asset_id=asset.id,
            page_order=item["page_order"], source_image_hash=item["source_hash"],
            selection_reasons=item["selection_reasons"], predicted_regions=regions,
            predicted_sequence=item["predicted_sequence"], predicted_groups=item["predicted_groups"],
            predicted_ambiguity=item["predicted_ambiguity"],
            ocr_reviews={str(r["region_id"]): {"state": "PENDING", "transcription": None} for r in regions},
            reading_state="PENDING" if source_ok else "SOURCE_UNAVAILABLE", source_compatible=source_ok,
        ))
    db.commit()
    return (db.query(ReaderCorrectnessReview).filter_by(project_id=project_id)
            .order_by(ReaderCorrectnessReview.page_order, ReaderCorrectnessReview.asset_id).all())


def serialize_queue(db: Session, project_id: str) -> dict[str, Any]:
    items=[]; ocr_counts=Counter(); reading_counts=Counter(); selection=Counter()
    for row in load_queue(db, project_id):
        asset=db.get(Asset,row.asset_id); source_ok=compatible(row,asset)
        reading_state=row.reading_state if source_ok else "SOURCE_UNAVAILABLE"; reading_counts[reading_state]+=1
        reviews=row.ocr_reviews or {}; regions=[]
        for region in row.predicted_regions:
            saved=reviews.get(str(region["region_id"]),{"state":"PENDING","transcription":None})
            state=saved.get("state","PENDING") if source_ok else "SOURCE_UNAVAILABLE"; ocr_counts[state]+=1
            public={k:v for k,v in region.items() if k not in {"predicted_text"}}
            public.update({"ocr_state":state,"human_transcription":saved.get("transcription")})
            if state in {"VERIFIED","UNREADABLE"}: public["predicted_text"]=region.get("predicted_text")
            regions.append(public)
        for reason in row.selection_reasons: selection[reason]+=1
        dims=None
        if source_ok:
            with Image.open(asset_path(asset)) as image:dims={"width":image.width,"height":image.height}
        items.append({"review_id":row.review_id,"asset_id":row.asset_id,"page_order":row.page_order,
                      "selection_reasons":row.selection_reasons,"reading_state":reading_state,
                      "source_compatible":source_ok,"revision":row.revision,"regions":regions,
                      "predicted_sequence":row.predicted_sequence,"predicted_groups":row.predicted_groups,
                      "predicted_ambiguity":row.predicted_ambiguity,"human_sequence":row.human_sequence,
                      "human_groups":row.human_groups,"human_dispositions":row.human_dispositions,
                      "image_dimensions":dims,"image_url":f"http://127.0.0.1:8000/projects/{project_id}/reader-correctness-review/{row.review_id}/image" if source_ok else None})
    return {"project_id":project_id,"total_pages":len(items),"reading_counts":dict(reading_counts),
            "total_ocr_regions":sum(ocr_counts.values()),"ocr_counts":dict(ocr_counts),
            "selection_breakdown":dict(selection),"items":items,"model_calls":{"vlm":0,"ollama":0}}


def image_bytes(db: Session, project_id: str, review_id: str) -> bytes:
    row=db.get(ReaderCorrectnessReview,review_id); asset=db.get(Asset,row.asset_id) if row else None
    if not row or row.project_id!=project_id: raise HTTPException(404,"Review page not found")
    if not compatible(row,asset): raise HTTPException(409,"SOURCE_UNAVAILABLE")
    return asset_path(asset).read_bytes()


def crop_bytes(db: Session, project_id: str, review_id: str, region_id: int) -> bytes:
    row=db.get(ReaderCorrectnessReview,review_id); asset=db.get(Asset,row.asset_id) if row else None
    if not row or row.project_id!=project_id: raise HTTPException(404,"Review page not found")
    if not compatible(row,asset): raise HTTPException(409,"SOURCE_UNAVAILABLE")
    region=next((r for r in row.predicted_regions if r["region_id"]==region_id),None)
    if not region: raise HTTPException(404,"Region not found")
    x1,y1,x2,y2=region["crop_bbox"]
    with Image.open(asset_path(asset)) as image:
        pad=24; box=(max(0,x1-pad),max(0,y1-pad),min(image.width,x2+pad),min(image.height,y2+pad))
        output=BytesIO(); image.convert("RGB").crop(box).save(output,format="PNG"); return output.getvalue()


def save_reading(db:Session,project_id:str,review_id:str,sequence:list[int],groups:list[dict],dispositions:dict[str,str])->dict:
    row=db.get(ReaderCorrectnessReview,review_id); asset=db.get(Asset,row.asset_id) if row else None
    if not row or row.project_id!=project_id: raise HTTPException(404,"Review page not found")
    if not compatible(row,asset): raise HTTPException(409,"SOURCE_UNAVAILABLE")
    expected={r["region_id"] for r in row.predicted_regions}; grouped=[x for g in groups for x in g.get("region_ids",[])]
    if len(sequence)!=len(set(sequence)) or set(sequence)!=expected: raise HTTPException(422,"Sequence must contain every region exactly once")
    if len(grouped)!=len(set(grouped)) or set(grouped)!=expected: raise HTTPException(422,"Groups must contain every region exactly once")
    row.human_sequence,row.human_groups,row.human_dispositions=sequence,groups,dispositions;row.reading_state="VERIFIED"
    row.revision+=1;row.updated_at=datetime.now(timezone.utc);db.add(row);db.commit();return {"state":"VERIFIED","revision":row.revision}


def save_ocr(db:Session,project_id:str,review_id:str,region_id:int,state:str,transcription:str|None)->dict:
    if state not in {"VERIFIED","UNREADABLE"}: raise HTTPException(422,"Unsupported OCR state")
    row=db.get(ReaderCorrectnessReview,review_id); asset=db.get(Asset,row.asset_id) if row else None
    if not row or row.project_id!=project_id: raise HTTPException(404,"Review page not found")
    if not compatible(row,asset): raise HTTPException(409,"SOURCE_UNAVAILABLE")
    if region_id not in {r["region_id"] for r in row.predicted_regions}: raise HTTPException(404,"Region not found")
    clean=transcription.strip() if isinstance(transcription,str) else ""
    if state=="VERIFIED" and not clean: raise HTTPException(422,"Human transcription cannot be empty")
    reviews=dict(row.ocr_reviews or {});reviews[str(region_id)]={"state":state,"transcription":transcription if state=="VERIFIED" else None}
    row.ocr_reviews=reviews;row.revision+=1;row.updated_at=datetime.now(timezone.utc);db.add(row);db.commit()
    return {"state":state,"revision":row.revision}
