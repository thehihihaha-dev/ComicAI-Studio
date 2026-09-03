from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from app.models.panel_ground_truth_review import PanelGroundTruthReview

ROOT = Path(__file__).resolve().parents[3]
DAY12 = ROOT / "benchmarks/day12"
INPUT_AUDIT = DAY12 / "panel-extraction-input-audit-12.2.json"
UNSEEN_FREEZE = DAY12 / "panel-unseen-prediction-freeze-12.4.json"
UNSEEN_PAGES = (3, 4, 5, 7, 18, 38)
LEGACY_PAGES = (1, 2, 15, 17)
QUEUE_SIZE = 6


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_path(relative: str) -> Path:
    path = ROOT / relative
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError as error:
        raise RuntimeError("Panel GT source path escapes repository") from error
    return path


def selected_manifest() -> list[dict[str, Any]]:
    """Return the locked unseen cohort without reading prediction content."""
    audit = json.loads(INPUT_AUDIT.read_text(encoding="utf-8"))["inputs"]
    sources = {int(page["page_order"]): page for page in audit}
    if set(sources) - set(LEGACY_PAGES) != set(UNSEEN_PAGES):
        raise RuntimeError("Panel GT unseen selection is not the frozen complement")
    result = []
    for page_order in UNSEEN_PAGES:
        source = sources[page_order]
        path = _source_path(source["resolved_path"])
        if not path.is_file() or _sha256(path) != source["source_hash"]:
            raise RuntimeError(f"Frozen source unavailable for Page {page_order}")
        with Image.open(path) as image:
            dimensions = [image.width, image.height]
        if dimensions != source["image_dimensions"]:
            raise RuntimeError(f"Frozen dimensions changed for Page {page_order}")
        result.append({"page_order": page_order, "selection_role": "UNSEEN_GENERALIZATION_12_4",
                       "benchmark_asset_id": source["asset_id"], "source_hash": source["source_hash"],
                       "source_path": source["resolved_path"], "image_dimensions": dimensions})
    return result


def _prediction_freeze_valid() -> bool:
    if not UNSEEN_FREEZE.is_file():
        return False
    payload = json.loads(UNSEEN_FREEZE.read_text(encoding="utf-8"))
    return (payload.get("status") == "FROZEN_BEFORE_HUMAN_GT"
            and payload.get("selected_pages") == list(UNSEEN_PAGES)
            and payload.get("human_gt_imported_or_queried") is False
            and payload.get("gt_runtime_features") == [])


def load_queue(db: Session) -> list[PanelGroundTruthReview]:
    if not _prediction_freeze_valid():
        raise RuntimeError("12.4 prediction freeze is missing or invalid")
    manifest = selected_manifest()
    expected = {item["page_order"] for item in manifest}
    existing = db.query(PanelGroundTruthReview).all()
    unexpected = [row.page_order for row in existing if row.page_order not in expected | set(LEGACY_PAGES)]
    if unexpected:
        raise RuntimeError(f"Panel GT table contains out-of-scope pages: {unexpected}")
    by_page = {row.page_order: row for row in existing if row.page_order in expected}
    for item in manifest:
        row = by_page.get(item["page_order"])
        if row is None:
            width, height = item["image_dimensions"]
            db.add(PanelGroundTruthReview(
                review_id=f"panel-gt-12.4:{item['benchmark_asset_id']}",
                benchmark_asset_id=item["benchmark_asset_id"], page_order=item["page_order"],
                selection_role=item["selection_role"], source_image_hash=item["source_hash"],
                source_path=item["source_path"], image_width=width, image_height=height,
                human_panels=[], state="PENDING",
            ))
        elif (row.benchmark_asset_id != item["benchmark_asset_id"]
              or row.source_image_hash != item["source_hash"] or row.source_path != item["source_path"]
              or [row.image_width, row.image_height] != item["image_dimensions"]):
            raise RuntimeError(f"Persisted Panel GT identity changed for Page {item['page_order']}")
    db.commit()
    return db.query(PanelGroundTruthReview).filter(
        PanelGroundTruthReview.page_order.in_(UNSEEN_PAGES)
    ).order_by(PanelGroundTruthReview.page_order).all()


def _compatible(row: PanelGroundTruthReview) -> bool:
    path = _source_path(row.source_path)
    return path.is_file() and _sha256(path) == row.source_image_hash


def _cohort_row(db: Session, review_id: str) -> PanelGroundTruthReview:
    row = db.get(PanelGroundTruthReview, review_id)
    if (row is None or row.page_order not in UNSEEN_PAGES
            or row.selection_role != "UNSEEN_GENERALIZATION_12_4"):
        raise HTTPException(404, "Panel GT unseen page not found")
    return row


def serialize_queue(db: Session) -> dict[str, Any]:
    items = []
    for row in load_queue(db):
        compatible = _compatible(row)
        state = row.state if compatible else "SOURCE_UNAVAILABLE"
        items.append({"review_id": row.review_id, "page_order": row.page_order,
                      "source_hash": row.source_image_hash, "state": state,
                      "revision": row.revision, "source_compatible": compatible,
                      "image_dimensions": {"width": row.image_width, "height": row.image_height},
                      "human_panels": row.human_panels or [],
                      "image_url": f"http://127.0.0.1:8000/panel-ground-truth/{row.review_id}/image" if compatible else None})
    counts = Counter(item["state"] for item in items)
    return {"checkpoint": "12.4", "cohort": "12.4-unseen", "total": len(items),
            "verified": counts["VERIFIED"],
            "pending": counts["PENDING"], "source_unavailable": counts["SOURCE_UNAVAILABLE"],
            "predictions_hidden": True, "panel_structure_only": True,
            "items": items, "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0}}


def image_bytes(db: Session, review_id: str) -> bytes:
    row = _cohort_row(db, review_id)
    if not _compatible(row):
        raise HTTPException(409, "SOURCE_UNAVAILABLE")
    return _source_path(row.source_path).read_bytes()


def _validated_panels(panels: list[dict[str, Any]], width: int, height: int) -> list[dict[str, Any]]:
    if not panels:
        raise HTTPException(422, "Vẽ ít nhất một ô truyện trước khi lưu")
    result, ids = [], set()
    for panel in panels:
        panel_id, bbox = str(panel.get("panel_id", "")).strip(), panel.get("bbox")
        if not panel_id or panel_id in ids:
            raise HTTPException(422, "Mỗi khung phải có mã nội bộ duy nhất")
        if (not isinstance(bbox, list) or len(bbox) != 4
                or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in bbox)):
            raise HTTPException(422, "Khung không hợp lệ")
        x1, y1, x2, y2 = [round(float(value), 3) for value in bbox]
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height) or (x2-x1)*(y2-y1) < 16:
            raise HTTPException(422, "Khung nằm ngoài ảnh hoặc quá nhỏ")
        ids.add(panel_id)
        result.append({"panel_id": panel_id, "bbox": [x1, y1, x2, y2],
                       "ambiguous": bool(panel.get("ambiguous", False))})
    return sorted(result, key=lambda panel: (panel["bbox"][1], panel["bbox"][0], panel["panel_id"]))


def save_review(db: Session, review_id: str, panels: list[dict[str, Any]]) -> dict[str, Any]:
    row = _cohort_row(db, review_id)
    if not _compatible(row):
        raise HTTPException(409, "SOURCE_UNAVAILABLE")
    clean = _validated_panels(panels, row.image_width, row.image_height)
    changed = row.state != "VERIFIED" or row.human_panels != clean
    row.human_panels, row.state = clean, "VERIFIED"
    if changed:
        now = datetime.now(timezone.utc)
        row.revision += 1; row.updated_at = now; row.verified_at = now
    db.add(row); db.commit()
    return {"review_id": row.review_id, "state": row.state, "revision": row.revision,
            "panel_count": len(clean)}
