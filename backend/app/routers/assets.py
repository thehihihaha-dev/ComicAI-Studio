from app.services.dialogue_builder import build_dialogues
from app.services.dialogue_structure_recovery import enforce_recovered_region_review
from app.models.dialogue_ground_truth import DialogueGroundTruth
from app.services.dialogue_corrector import (
    correct_dialogues,
    validate_corrected_dialogues,
    calculate_correction_score,
    apply_dialogue_decisions,
    apply_verified_ground_truth,
    recover_uncertain_dialogues,
    process_dialogue_batches,
)
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    BackgroundTasks,
    Body,
    Response,
)
from io import BytesIO
from PIL import Image
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from app.services.ocr_service import (
    extract_text_from_image,
    extract_ocr_blocks,
)
import json
from app.services.vision_analyzer import analyze_comic_page


from app.database import SessionLocal
from app.models.asset import Asset
from app.models.project import Project  # Ensure projects table is in Base metadata.
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
        "vision_status": asset.vision_status,

        "vision_regions": (
            json.loads(asset.vision_regions)
            if asset.vision_regions
            else []
        ),

        "reading_order": (
            json.loads(asset.reading_order)
            if asset.reading_order
            else []
        ),
        "dialogue_status": asset.dialogue_status,

        "dialogues": (
            json.loads(asset.dialogues)
            if asset.dialogues
            else []
        ),
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
def run_layout_analysis(asset_id: str):
    db = SessionLocal()

    try:
        asset = (
            db.query(Asset)
            .filter(Asset.id == asset_id)
            .first()
        )

        if not asset or not asset.ocr_blocks:
            return

        try:
            ocr_blocks = json.loads(asset.ocr_blocks)

            result = analyze_comic_page(
                image_path=asset.file_path,
                ocr_blocks=ocr_blocks,
            )

            if not result["validation"]["is_valid"]:
                print(
                    f"\n=== VISION VALIDATION FAILED: {asset.filename} ==="
                )

                print(
                    json.dumps(
                        result["validation"],
                        ensure_ascii=False,
                        indent=2,
                    )
                )

                print("\n=== VISION RESULT ===")

                print(
                    json.dumps(
                        result.get("vision_result", {}),
                        ensure_ascii=False,
                        indent=2,
                    )
                )

                asset.vision_status = "failed"
                db.commit()
                return

            vision_result = result["vision_result"]
            page_type = result["validation"].get(
                "page_type"
            )

            asset.vision_regions = json.dumps(
                vision_result["regions"],
                ensure_ascii=False,
            )

            asset.reading_order = json.dumps(
                vision_result["reading_order"],
                ensure_ascii=False,
            )
            asset.ocr_blocks = json.dumps(
                result.get("ocr_blocks", ocr_blocks),
                ensure_ascii=False,
            )

            asset.vision_status = (
                "no_dialogue"
                if page_type == "no_dialogue"
                else "completed"
            )

            if page_type == "no_dialogue":
                asset.dialogues = json.dumps([])
                asset.dialogue_status = "completed"
            else:
                asset.dialogues = None
                asset.dialogue_status = "pending"
            db.commit()

        except Exception as error:
            print(
                f"Layout analysis failed "
                f"for {asset_id}: {error}"
            )

            asset.vision_status = "failed"
            db.commit()

    finally:
        db.close()
def run_dialogue_analysis(asset_id: str):
    db = SessionLocal()

    try:
        asset = (
            db.query(Asset)
            .filter(Asset.id == asset_id)
            .first()
        )

        if not asset:
            return

        try:
            if (
                not asset.ocr_blocks
                or not asset.vision_regions
                or not asset.reading_order
            ):
                asset.dialogue_status = "failed"
                db.commit()
                return

            ocr_blocks = json.loads(asset.ocr_blocks)
            regions = json.loads(asset.vision_regions)
            reading_order = json.loads(asset.reading_order)

            # 1. Ghép dialogue theo reading order
            raw_dialogues = build_dialogues(
                ocr_blocks,
                regions,
                reading_order,
            )

            ground_truth_rows = (
                db.query(DialogueGroundTruth)
                .filter(DialogueGroundTruth.asset_id == asset.id)
                .all()
            )
            verified_text_by_region = {
                row.region_id: row.verified_text
                for row in ground_truth_rows
            }

            # 2–4. Correct/recover normal evidence separately from OCR-empty recovery.
            final_dialogues = process_dialogue_batches(
                asset.file_path,
                raw_dialogues,
                ocr_blocks,
                regions,
                verified_text_by_region,
            )
            final_dialogues = apply_verified_ground_truth(
                final_dialogues,
                verified_text_by_region,
            )
            final_dialogues = enforce_recovered_region_review(
                final_dialogues,
                regions,
            )

            # 5. Kiểm tra có câu nào cần review
            needs_review = any(
                dialogue.get("decision") == "needs_review"
                for dialogue in final_dialogues
            )

            # 6. Lưu kết quả
            asset.dialogues = json.dumps(
                final_dialogues,
                ensure_ascii=False,
            )

            asset.dialogue_status = (
                "needs_review"
                if needs_review
                else "completed"
            )

            db.commit()

        except Exception as error:
            print(
                f"Dialogue analysis failed "
                f"for {asset_id}: {error}"
            )

            db.rollback()
            asset = db.get(Asset, asset_id)
            if asset is None:
                return
            asset.dialogue_status = "failed"
            db.commit()

    finally:
        db.close()
@router.post("/{asset_id}/analyze-layout")
def analyze_asset_layout(
    asset_id: str,
    background_tasks: BackgroundTasks,
):
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

        if not asset.ocr_blocks:
            raise HTTPException(
                status_code=400,
                detail="Asset has no OCR blocks",
            )

        asset.vision_status = "processing"
        asset.dialogues = None
        asset.dialogue_status = "pending"
        db.commit()

        background_tasks.add_task(
            run_layout_analysis,
            asset_id,
        )

        return {
            "asset_id": asset.id,
            "filename": asset.filename,
            "vision_status": "processing",
            "message": "Layout analysis started",
        }

    finally:
        db.close()
def process_project_in_background(project_id: str):
    db = SessionLocal()

    try:
        assets = (
            db.query(Asset)
            .filter(
                Asset.project_id == project_id,
                Asset.status == ASSET_STATUS_PROCESSING,
            )
            .order_by(Asset.page_order.asc())
            .all()
        )

        for asset in assets:
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

            except Exception as error:
                print(
                    f"OCR failed for {asset.filename}: {error}"
                )

                asset.status = ASSET_STATUS_FAILED

            db.commit()

    finally:
        db.close()
@router.post("/{asset_id}/build-dialogues")
def build_asset_dialogues(
    asset_id: str,
    background_tasks: BackgroundTasks,
):
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

        if asset.vision_status != "completed":
            raise HTTPException(
                status_code=400,
                detail="Layout analysis is not completed",
            )

        if (
            not asset.ocr_blocks
            or not asset.vision_regions
            or not asset.reading_order
        ):
            raise HTTPException(
                status_code=400,
                detail="Asset is missing analysis data",
            )

        asset.dialogue_status = "processing"
        db.commit()

        background_tasks.add_task(
            run_dialogue_analysis,
            asset_id,
        )

        return {
            "asset_id": asset.id,
            "filename": asset.filename,
            "dialogue_status": "processing",
            "message": "Dialogue analysis started",
        }

    finally:
        db.close()
@router.post("/project/{project_id}/process")
def process_project_assets(
    project_id: str,
    background_tasks: BackgroundTasks,
):
    db = SessionLocal()

    try:
        assets = (
            db.query(Asset)
            .filter(
                Asset.project_id == project_id,
                Asset.status == ASSET_STATUS_READY,
                Asset.ocr_text.is_(None),
            )
            .order_by(Asset.page_order.asc())
            .all()
        )

        if not assets:
            return {
                "project_id": project_id,
                "queued": 0,
                "message": "No assets ready for processing",
            }

        for asset in assets:
            asset.status = ASSET_STATUS_PROCESSING

        db.commit()

        background_tasks.add_task(
            process_project_in_background,
            project_id,
        )

        return {
            "project_id": project_id,
            "queued": len(assets),
            "status": "processing",
            "message": "OCR processing started",
        }

    finally:
        db.close()
@router.get("/project/{project_id}/progress")
def get_processing_progress(project_id: str):
    db = SessionLocal()

    try:
        assets = (
            db.query(Asset)
            .filter(Asset.project_id == project_id)
            .all()
        )

        total = len(assets)

        processing = sum(
            1 for asset in assets
            if asset.status == ASSET_STATUS_PROCESSING
        )

        failed = sum(
            1 for asset in assets
            if asset.status == ASSET_STATUS_FAILED
        )

        completed = sum(
            1 for asset in assets
            if asset.ocr_text is not None
        )

        if processing > 0:
            status = "processing"
        elif failed > 0:
            status = "completed_with_errors"
        elif total > 0 and completed == total:
            status = "completed"
        else:
            status = "idle"

        percent = (
            round((completed / total) * 100)
            if total > 0
            else 0
        )

        return {
            "project_id": project_id,
            "status": status,
            "total": total,
            "completed": completed,
            "processing": processing,
            "failed": failed,
            "percent": percent,
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
@router.get("/project/{project_id}/review-queue")
def get_review_queue(project_id: str):
    db = SessionLocal()

    try:
        assets = (
            db.query(Asset)
            .filter(Asset.project_id == project_id)
            .all()
        )

        review_items = []

        for asset in assets:
            if not asset.dialogues:
                continue

            try:
                dialogues = json.loads(asset.dialogues)
            except (json.JSONDecodeError, TypeError):
                continue

            for dialogue in dialogues:
                if dialogue.get("decision") != "needs_review":
                    continue

                ocr_blocks = json.loads(asset.ocr_blocks or "[]")
                regions = json.loads(asset.vision_regions or "[]")
                region = next(
                    (
                        item
                        for item in regions
                        if item.get("id") == dialogue.get("region_id")
                    ),
                    None,
                )
                bbox = dialogue_region_bbox(region, ocr_blocks)

                review_items.append(
                    {
                        "asset_id": str(asset.id),
                        "filename": asset.filename,
                        "page_order": asset.page_order,
                        "region_id": dialogue.get("region_id"),
                        "raw_text": dialogue.get("raw_text"),
                        "clean_text": dialogue.get("clean_text"),
                        "recovered_text": dialogue.get(
                            "recovered_text"
                        ),
                        "correction_score": dialogue.get(
                            "correction_score"
                        ),
                        "recovery_confidence": dialogue.get(
                            "recovery_confidence"
                        ),
                        "reason": dialogue.get(
                            "recovery_reason",
                            dialogue.get("reason", ""),
                        ),
                        "reason_code": (
                            dialogue.get("reason_code")
                            if dialogue.get("reason_code")
                            == "recovered_visual_text_requires_review"
                            else dialogue.get(
                                "recovery_reason_code",
                                dialogue.get("reason_code", "needs_review"),
                            )
                        ),
                        "confidence": dialogue.get("confidence"),
                        "bbox": bbox,
                        "crop_url": (
                            f"http://127.0.0.1:8000/assets/{asset.id}"
                            f"/regions/{dialogue.get('region_id')}/crop"
                            if bbox
                            else None
                        ),
                        "image_url": (
                            f"http://127.0.0.1:8000/"
                            f"{asset.file_path}"
                        ),
                    }
                )

        review_items.sort(
            key=lambda item: (
                item["page_order"],
                item["region_id"],
            )
        )
        return {
            "project_id": project_id,
            "review_count": len(review_items),
            "items": review_items,
        }

    finally:
        db.close()


def dialogue_region_bbox(
    region: dict | None,
    ocr_blocks: list[dict],
) -> list[int] | None:
    if not region:
        return None
    points = [
        point
        for block_id in region.get("block_ids", [])
        if isinstance(block_id, int) and 0 <= block_id < len(ocr_blocks)
        for point in ocr_blocks[block_id].get("box", [])
        if isinstance(point, list) and len(point) == 2
    ]
    if not points:
        return None
    return [
        int(min(point[0] for point in points)),
        int(min(point[1] for point in points)),
        int(max(point[0] for point in points)),
        int(max(point[1] for point in points)),
    ]


@router.get("/{asset_id}/regions/{region_id}")
def get_dialogue_region(asset_id: str, region_id: int):
    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        regions = json.loads(asset.vision_regions or "[]")
        blocks = json.loads(asset.ocr_blocks or "[]")
        region = next((item for item in regions if item.get("id") == region_id), None)
        bbox = dialogue_region_bbox(region, blocks)
        if region is None or bbox is None:
            raise HTTPException(status_code=404, detail="Region evidence not found")
        with Image.open(asset.file_path) as image:
            image_size = {"width": image.width, "height": image.height}
        return {
            "asset_id": asset.id,
            "region_id": region_id,
            "bbox": bbox,
            "text_role": region.get("type", "unknown"),
            "image_size": image_size,
        }
    finally:
        db.close()


@router.get("/{asset_id}/regions/{region_id}/crop")
def get_dialogue_region_crop(asset_id: str, region_id: int):
    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        regions = json.loads(asset.vision_regions or "[]")
        blocks = json.loads(asset.ocr_blocks or "[]")
        region = next((item for item in regions if item.get("id") == region_id), None)
        bbox = dialogue_region_bbox(region, blocks)
        if bbox is None:
            raise HTTPException(status_code=404, detail="Region evidence not found")
        with Image.open(asset.file_path) as image:
            padding = 32
            crop = image.convert("RGB").crop(
                (
                    max(0, bbox[0] - padding),
                    max(0, bbox[1] - padding),
                    min(image.width, bbox[2] + padding),
                    min(image.height, bbox[3] + padding),
                )
            )
            output = BytesIO()
            crop.save(output, format="JPEG", quality=92)
        return Response(content=output.getvalue(), media_type="image/jpeg")
    finally:
        db.close()
@router.post("/{asset_id}/dialogues/{region_id}/verify")
def verify_dialogue(
    asset_id: str,
    region_id: int,
    verified_text: str = Body(..., embed=True),
):
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

        if not asset.dialogues:
            raise HTTPException(
                status_code=400,
                detail="Asset has no dialogues",
            )

        dialogues = json.loads(asset.dialogues)

        target = None

        for dialogue in dialogues:
            if dialogue.get("region_id") == region_id:
                target = dialogue
                break

        if target is None:
            raise HTTPException(
                status_code=404,
                detail="Dialogue region not found",
            )

        clean_verified_text = verified_text.strip()

        if not clean_verified_text:
            raise HTTPException(
                status_code=400,
                detail="Verified text cannot be empty",
            )

        target["pre_verification_text"] = target.get("clean_text", "")
        target["clean_text"] = clean_verified_text
        target["verified_text"] = clean_verified_text
        target["human_verified"] = True
        target["needs_review"] = False
        target["decision"] = "verified"

        asset.dialogues = json.dumps(
            dialogues,
            ensure_ascii=False,
        )

        still_needs_review = any(
            dialogue.get("decision") == "needs_review"
            for dialogue in dialogues
        )

        asset.dialogue_status = (
            "needs_review"
            if still_needs_review
            else "completed"
        )
        ground_truth = (
            db.query(DialogueGroundTruth)
            .filter(
                DialogueGroundTruth.asset_id == asset.id,
                DialogueGroundTruth.region_id == region_id,
            )
            .first()
        )

        ai_text = (
            target.get("recovered_text")
            or target.get("pre_verification_text")
        )

        if ground_truth is None:
            ground_truth = DialogueGroundTruth(
                asset_id=asset.id,
                region_id=region_id,
                raw_text=target.get("raw_text", ""),
                ai_text=ai_text,
                verified_text=clean_verified_text,
                correction_score=target.get("correction_score"),
                recovery_confidence=target.get("recovery_confidence"),
            )
        else:
            ground_truth.raw_text = target.get("raw_text", "")
            ground_truth.ai_text = ai_text
            ground_truth.verified_text = clean_verified_text
            ground_truth.correction_score = target.get("correction_score")
            ground_truth.recovery_confidence = target.get(
                "recovery_confidence"
            )

        db.add(ground_truth)
        db.commit()

        return {
            "asset_id": asset.id,
            "region_id": region_id,
            "verified_text": clean_verified_text,
            "decision": "verified",
            "dialogue_status": asset.dialogue_status,
        }

    finally:
        db.close()
