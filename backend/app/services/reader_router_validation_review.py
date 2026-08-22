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
from app.models.project import Project  # noqa: F401 - load FK metadata for standalone tooling
from app.models.reader_router_validation_review import ReaderRouterValidationReview

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "benchmarks" / "day11" / "reader-router-validation-manifest-11.13.json"


def _path(asset: Asset) -> Path:
    value = Path(asset.file_path)
    return value if value.is_absolute() else ROOT / "backend" / value


def _compatible(row: ReaderRouterValidationReview, asset: Asset | None) -> bool:
    path = _path(asset) if asset else Path("__missing__")
    return bool(asset and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row.source_image_hash)


def load_queue(db: Session, project_id: str) -> list[ReaderRouterValidationReview]:
    if not MANIFEST.is_file():
        raise HTTPException(503, "Checkpoint 11.13 validation manifest is unavailable")
    manifest = json.loads(MANIFEST.read_text())
    if not manifest.get("source_hash_separation_passed"):
        raise HTTPException(503, "Checkpoint 11.13 calibration separation failed")
    for item in manifest["samples"]:
        row = db.get(ReaderRouterValidationReview, item["sample_id"])
        if row:
            immutable = (row.asset_id, row.logical_region_id, row.source_image_hash, row.representation_hash, row.bbox)
            expected = (item["asset_id"], item["logical_region_id"], item["source_hash"], item["representation_hash"], item["bbox"])
            if immutable != expected:
                raise HTTPException(409, "Frozen 11.13 sample identity mismatch")
            continue
        asset = db.get(Asset, item["asset_id"])
        if not asset or asset.project_id != project_id:
            continue
        candidate = ReaderRouterValidationReview(
            sample_id=item["sample_id"], project_id=project_id, asset_id=item["asset_id"],
            page_order=item["page_order"], logical_region_id=item["logical_region_id"], bbox=item["bbox"],
            source_image_hash=item["source_hash"], representation_hash=item["representation_hash"],
            state="PENDING", provenance="human",
        )
        if not _compatible(candidate, asset):
            candidate.state = "SOURCE_UNAVAILABLE"
        db.add(candidate)
    db.commit()
    return db.query(ReaderRouterValidationReview).filter_by(project_id=project_id).order_by(
        ReaderRouterValidationReview.page_order, ReaderRouterValidationReview.sample_id).all()


def serialize_queue(db: Session, project_id: str) -> dict[str, Any]:
    rows = load_queue(db, project_id)
    items = []
    for row in rows:
        compatible = _compatible(row, db.get(Asset, row.asset_id))
        state = row.state if compatible else "SOURCE_UNAVAILABLE"
        # Predictions, confidence, fragment count and frozen-R2 state are deliberately absent.
        items.append({
            "sample_id": row.sample_id, "page_order": row.page_order, "state": state,
            "source_compatible": compatible, "revision": row.revision,
            "human_transcription": row.human_transcription if state == "VERIFIED" else None,
            "crop_url": f"http://127.0.0.1:8000/projects/{project_id}/reader-router-validation-review/{row.sample_id}/crop" if compatible else None,
        })
    counts = Counter(item["state"] for item in items)
    return {
        "checkpoint": "11.13", "total": len(items), "verified": counts["VERIFIED"],
        "unreadable": counts["UNREADABLE"], "pending": counts["PENDING"],
        "source_unavailable": counts["SOURCE_UNAVAILABLE"], "items": items,
        "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0},
    }


def crop_bytes(db: Session, project_id: str, sample_id: str) -> bytes:
    row = db.get(ReaderRouterValidationReview, sample_id)
    asset = db.get(Asset, row.asset_id) if row else None
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Validation sample not found")
    if not _compatible(row, asset):
        raise HTTPException(409, "SOURCE_UNAVAILABLE")
    with Image.open(_path(asset)) as image:
        x1, y1, x2, y2 = row.bbox
        padding = 32
        box = (max(0, int(x1) - padding), max(0, int(y1) - padding), min(image.width, int(x2) + padding), min(image.height, int(y2) + padding))
        if box[2] <= box[0] or box[3] <= box[1]:
            raise HTTPException(409, "INVALID_CROP")
        output = BytesIO()
        image.convert("RGB").crop(box).save(output, format="PNG")
        return output.getvalue()


def save_review(db: Session, project_id: str, sample_id: str, state: str, transcription: str | None) -> dict[str, Any]:
    if state not in {"VERIFIED", "UNREADABLE"}:
        raise HTTPException(422, "Unsupported Human review action")
    row = db.get(ReaderRouterValidationReview, sample_id)
    asset = db.get(Asset, row.asset_id) if row else None
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Validation sample not found")
    if not _compatible(row, asset):
        raise HTTPException(409, "SOURCE_UNAVAILABLE")
    text = transcription if isinstance(transcription, str) else None
    if state == "VERIFIED" and not (text and text.strip()):
        raise HTTPException(422, "Human transcription cannot be empty")
    next_text = text if state == "VERIFIED" else None
    if row.state != state or row.human_transcription != next_text:
        row.state = state
        row.human_transcription = next_text
        row.provenance = "human"
        row.revision += 1
        row.updated_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()
    return {"sample_id": row.sample_id, "state": row.state, "revision": row.revision}
