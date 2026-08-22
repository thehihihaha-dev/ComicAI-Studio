from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.dialogue_ground_truth import DialogueGroundTruth
from app.models.ocr_benchmark_review import OcrBenchmarkReview


ROOT = Path(__file__).resolve().parents[3]
QUEUE_PATH = ROOT / "benchmarks" / "day11" / "reader-benchmark-manifest-11.4.json"
VALID_STATES = {"PENDING", "VERIFIED", "SKIPPED", "UNREADABLE", "SOURCE_UNAVAILABLE"}


def _asset_path(asset: Asset) -> Path:
    path = Path(asset.file_path)
    return path if path.is_absolute() else ROOT / "backend" / path


def _image_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _crop_bytes(path: Path, bbox: list[int], *, padding: int = 0) -> bytes:
    with Image.open(path) as image:
        box = (max(0, bbox[0] - padding), max(0, bbox[1] - padding),
               min(image.width, bbox[2] + padding), min(image.height, bbox[3] + padding))
        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError("Invalid crop bbox")
        output = BytesIO()
        image.convert("RGB").crop(box).save(output, format="PNG")
        return output.getvalue()


def _crop_hash(path: Path, bbox: list[int]) -> str:
    return hashlib.sha256(_crop_bytes(path, bbox)).hexdigest()


def load_queue(db: Session, project_id: str) -> list[OcrBenchmarkReview]:
    if not QUEUE_PATH.is_file():
        raise HTTPException(status_code=503, detail="OCR benchmark queue artifact is unavailable")
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8")).get("requires_human_transcription", [])
    for item in queue:
        sample_id = str(item["sample_id"])
        existing = db.get(OcrBenchmarkReview, sample_id)
        if existing is not None:
            continue
        asset = db.get(Asset, item["asset_id"])
        if asset is None or asset.project_id != project_id:
            continue
        if db.query(DialogueGroundTruth).filter_by(asset_id=asset.id, region_id=item.get("region_id")).first():
            continue
        bbox = item.get("bbox")
        path = _asset_path(asset)
        source_ok = path.is_file() and _image_hash(path) == item.get("image_sha256") and bbox is not None
        crop_hash = _crop_hash(path, bbox) if source_ok else None
        db.add(OcrBenchmarkReview(
            sample_id=sample_id, project_id=project_id, asset_id=asset.id,
            region_id=item.get("region_id"), page_order=item["page_order"], bbox=bbox,
            text_role=item.get("text_role", "unknown"), source_image_hash=item.get("image_sha256", ""),
            crop_hash=crop_hash, state="PENDING" if source_ok else "SOURCE_UNAVAILABLE",
            source_compatible=source_ok, provenance="human",
        ))
    db.commit()
    return (db.query(OcrBenchmarkReview).filter_by(project_id=project_id)
            .order_by(OcrBenchmarkReview.page_order, OcrBenchmarkReview.region_id).all())


def source_is_compatible(review: OcrBenchmarkReview, asset: Asset) -> bool:
    path = _asset_path(asset)
    if not path.is_file() or review.bbox is None:
        return False
    return (_image_hash(path) == review.source_image_hash and
            _crop_hash(path, review.bbox) == review.crop_hash)


def serialize_queue(db: Session, project_id: str) -> dict[str, Any]:
    rows = load_queue(db, project_id)
    items = []
    for row in rows:
        asset = db.get(Asset, row.asset_id)
        compatible = asset is not None and asset.project_id == project_id and source_is_compatible(row, asset)
        truth = db.query(DialogueGroundTruth).filter_by(asset_id=row.asset_id, region_id=row.region_id).first()
        items.append({
            "sample_id": row.sample_id, "asset_id": row.asset_id, "page_order": row.page_order,
            "region_id": row.region_id, "bbox": row.bbox, "text_role": row.text_role,
            "state": row.state if compatible else "SOURCE_UNAVAILABLE",
            "source_compatible": compatible, "revision": row.revision,
            "verified_text": truth.verified_text if row.state == "VERIFIED" and truth else None,
            "crop_url": f"http://127.0.0.1:8000/projects/{project_id}/ocr-benchmark-review/{row.sample_id}/crop" if compatible else None,
        })
    counts = Counter(item["state"] for item in items)
    return {"project_id": project_id, "total": len(items), "verified": counts["VERIFIED"],
            "pending": counts["PENDING"], "items": items}


def crop_response(db: Session, project_id: str, sample_id: str) -> bytes:
    review = db.get(OcrBenchmarkReview, sample_id)
    if review is None or review.project_id != project_id:
        raise HTTPException(status_code=404, detail="Benchmark sample not found")
    asset = db.get(Asset, review.asset_id)
    if asset is None or asset.project_id != project_id or not source_is_compatible(review, asset):
        raise HTTPException(status_code=409, detail="SOURCE_UNAVAILABLE")
    return _crop_bytes(_asset_path(asset), review.bbox, padding=32)


def update_review(db: Session, project_id: str, sample_id: str, state: str, text: str | None) -> dict[str, Any]:
    if state not in VALID_STATES - {"PENDING", "SOURCE_UNAVAILABLE"}:
        raise HTTPException(status_code=422, detail="Unsupported review action")
    review = db.get(OcrBenchmarkReview, sample_id)
    if review is None or review.project_id != project_id:
        raise HTTPException(status_code=404, detail="Benchmark sample not found")
    asset = db.get(Asset, review.asset_id)
    if asset is None or asset.project_id != project_id or not source_is_compatible(review, asset):
        review.source_compatible = False
        db.commit()
        raise HTTPException(status_code=409, detail="SOURCE_UNAVAILABLE")
    clean = text.strip() if isinstance(text, str) else ""
    if state == "VERIFIED" and not clean:
        raise HTTPException(status_code=422, detail="Human transcription cannot be empty")
    truth = db.query(DialogueGroundTruth).filter_by(asset_id=asset.id, region_id=review.region_id).first()
    changed = review.state != state or (state == "VERIFIED" and (truth is None or truth.verified_text != text))
    if state == "VERIFIED":
        if truth is None:
            truth = DialogueGroundTruth(asset_id=asset.id, region_id=review.region_id,
                                        raw_text="", ai_text=None, verified_text=text)
        else:
            truth.verified_text = text
        db.add(truth)
    review.state = state
    review.provenance = "human"
    if changed:
        if state == "VERIFIED":
            review.verified_at = datetime.now(timezone.utc)
        review.revision += 1
        review.benchmark_cache_revision += 1
        review.updated_at = datetime.now(timezone.utc)
    db.add(review); db.commit()
    return {"sample_id": sample_id, "state": state, "revision": review.revision,
            "benchmark_cache_revision": review.benchmark_cache_revision,
            "verified_text": truth.verified_text if state == "VERIFIED" and truth else None}


def verified_samples(db: Session, project_id: str | None = None) -> list[dict[str, Any]]:
    query = db.query(OcrBenchmarkReview).filter_by(state="VERIFIED", provenance="human", source_compatible=True)
    if project_id is not None:
        query = query.filter_by(project_id=project_id)
    samples = []
    for review in query.order_by(OcrBenchmarkReview.project_id, OcrBenchmarkReview.page_order, OcrBenchmarkReview.region_id):
        asset = db.get(Asset, review.asset_id)
        truth = db.query(DialogueGroundTruth).filter_by(asset_id=review.asset_id, region_id=review.region_id).first()
        if asset is None or truth is None or not source_is_compatible(review, asset):
            continue
        samples.append({"sample_id": review.sample_id, "project_id": review.project_id,
                        "asset_id": review.asset_id, "page_order": review.page_order,
                        "region_id": review.region_id, "bbox": review.bbox,
                        "source_image_hash": review.source_image_hash, "crop_hash": review.crop_hash,
                        "ground_truth": truth.verified_text, "ground_truth_source": "human",
                        "image_sha256": review.source_image_hash, "language": "unknown",
                        "text_role": review.text_role, "difficulty_tags": ["human_verified"],
                        "revision": review.revision, "benchmark_cache_revision": review.benchmark_cache_revision,
                        "source_path": str(_asset_path(asset))})
    return samples
