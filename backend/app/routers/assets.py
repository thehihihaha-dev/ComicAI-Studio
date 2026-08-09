from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from app.services.ocr_service import (
    extract_text_from_image,
    extract_ocr_blocks,
)
import json


from app.database import SessionLocal
from app.models.asset import Asset
from sqlalchemy import func
from app.services.asset_processor import (
    natural_sort_key,
    is_valid_image_filename,
    is_valid_image_file,
    ASSET_STATUS_READY,
    ASSET_STATUS_PROCESSING,
    ASSET_STATUS_FAILED,
    ASSET_STATUS_EXCLUDED,
)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter(
    prefix="/assets",
    tags=["Assets"],
)
@router.get("/")
def get_assets():
    return {"message": "Assets API is working"}
@router.get("/project/{project_id}")
def get_project_assets(
    project_id: str,
    page: int = 1,
    limit: int = 50,
):
    db = SessionLocal()
    total = (
    db.query(Asset)
    .filter(Asset.project_id == project_id)
    .count()
    )
    total_pages = max(1, (total + limit - 1) // limit)

    assets = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .order_by(Asset.page_order.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    result = [
    {
        "id": asset.id,
        "project_id": asset.project_id,
        "filename": asset.filename,
        "file_type": asset.file_type,
        "file_path": asset.file_path,
        "page_order": asset.page_order,
        "created_at": asset.created_at,
        "status": asset.status,
        "ocr_text": asset.ocr_text,
        "ocr_blocks": json.loads(asset.ocr_blocks) if asset.ocr_blocks else [],
        "url": f"http://127.0.0.1:8000/{asset.file_path}",
    }
    for asset in assets
]

    db.close()

    return {
    "items": result,
    "total": total,
    "page": page,
    "limit": limit,
    "total_pages": total_pages,
}
@router.post("/{asset_id}/ocr")
def process_single_asset(asset_id: str):
    db = SessionLocal()

    try:
        asset = (
            db.query(Asset)
            .filter(Asset.id == asset_id)
            .first()
        )

        if not asset:
            raise HTTPException(
                status_code=404,
                detail="Asset not found",
            )

        asset.status = ASSET_STATUS_PROCESSING
        db.commit()

        try:
            blocks = extract_ocr_blocks(asset.file_path)

            asset.ocr_blocks = json.dumps(
                blocks,
                ensure_ascii=False,
            )

            asset.ocr_text = "\n".join(
                block["text"]
                for block in blocks
                if block["text"].strip()
            )

            asset.status = ASSET_STATUS_READY
            db.commit()

            return {
                "asset_id": asset.id,
                "filename": asset.filename,
                "status": asset.status,
                "ocr_text": asset.ocr_text,
                "ocr_blocks": blocks,
            }

        except Exception as error:
            asset.status = ASSET_STATUS_FAILED
            db.commit()

            raise HTTPException(
                status_code=500,
                detail=str(error),
            )

    finally:
        db.close()
@router.post("/project/{project_id}/process")
def process_project_assets(project_id: str):
    db = SessionLocal()

    try:
        assets = (
            db.query(Asset)
            .filter(
                Asset.project_id == project_id,
                Asset.status == ASSET_STATUS_READY,
            )
            .order_by(Asset.page_order.asc())
            .all()
        )

        if not assets:
            return {
                "project_id": project_id,
                "processed": 0,
                "message": "No assets ready for processing",
            }

        processed_count = 0
        failed_count = 0

        for asset in assets:
            asset.status = ASSET_STATUS_PROCESSING
            db.commit()

            try:
                blocks = extract_ocr_blocks(asset.file_path)

                asset.ocr_blocks = json.dumps(
                    blocks,
                    ensure_ascii=False,
                )

                asset.ocr_text = "\n".join(
                    block["text"]
                    for block in blocks
                    if block["text"].strip()
                )
                asset.status = ASSET_STATUS_READY
                processed_count += 1

            except Exception as error:
                print(f"OCR failed for {asset.filename}: {error}")
                asset.status = ASSET_STATUS_FAILED
                failed_count += 1

            db.commit()

        return {
            "project_id": project_id,
            "processed": processed_count,
            "failed": failed_count,
        }

    finally:
        db.close()
@router.post("/upload")
async def upload_assets(
    project_id: str = Form(...),
    files: list[UploadFile] = File(...),
):
    saved_files = []
    db = SessionLocal()
    max_page_order = (
    db.query(func.max(Asset.page_order))
    .filter(Asset.project_id == project_id)
    .scalar()
    or 0
)
    files.sort(key=lambda file: natural_sort_key(file.filename))

    for index, file in enumerate(files, start=1):
        if not is_valid_image_filename(file.filename):
            continue

        stored_filename = f"{uuid4()}_{file.filename}"
        file_path = UPLOAD_DIR / stored_filename

        new_asset = Asset(
            id=str(uuid4()),
            project_id=project_id,
            filename=file.filename,
            file_type="image",
            file_path=str(file_path),
            page_order=max_page_order + index,
            created_at=datetime.now(timezone.utc),
)
        
        content = await file.read()
        file_path.write_bytes(content)

        if not is_valid_image_file(file_path):
            file_path.unlink(missing_ok=True)
            continue

        db.add(new_asset)
        saved_files.append(file.filename)

    db.commit()
    # Sort lại toàn bộ assets của project theo filename
    all_assets = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .all()
    )

    all_assets.sort(
        key=lambda asset: natural_sort_key(asset.filename)
    )

    for order, asset in enumerate(all_assets, start=1):
        asset.page_order = order

    db.commit()
    db.close()
    return {
        "count": len(saved_files),
        "files": saved_files,
        "project_id": project_id,
    }
@router.delete("/batch/")
def delete_assets_batch(asset_ids: list[str]):
    db = SessionLocal()

    assets = (
        db.query(Asset)
        .filter(Asset.id.in_(asset_ids))
        .all()
    )

    deleted_count = 0

    for asset in assets:
        file_path = Path(asset.file_path)

        if file_path.exists():
            file_path.unlink()

        db.delete(asset)
        deleted_count += 1

    db.commit()
    db.close()

    return {
        "message": "Assets deleted successfully",
        "deleted_count": deleted_count,
    }
@router.delete("/{asset_id}")
def delete_asset(asset_id: str):
    db = SessionLocal()

    asset = db.query(Asset).filter(Asset.id == asset_id).first()

    if not asset:
        db.close()
        return {"message": "Asset not found"}

    file_path = Path(asset.file_path)

    if file_path.exists():
        file_path.unlink()

    db.delete(asset)
    db.commit()
    db.close()

    return {"message": "Asset deleted successfully"}
