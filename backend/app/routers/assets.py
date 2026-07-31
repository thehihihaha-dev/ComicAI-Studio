from fastapi import APIRouter, UploadFile, File, Form
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.asset import Asset
from sqlalchemy import func
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

    for index, file in enumerate(files, start=1):
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

        db.add(new_asset)
        saved_files.append(file.filename)

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
