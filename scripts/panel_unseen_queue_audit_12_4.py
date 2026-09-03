"""Audit the post-freeze, empty 12.4 Human queue without reading predictions."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.models.panel_ground_truth_review import PanelGroundTruthReview  # noqa: E402
from app.services.panel_conflict_resolver import semantic_hash  # noqa: E402

DAY12 = ROOT / "benchmarks/day12"
FREEZE = DAY12 / "panel-unseen-prediction-freeze-12.4.json"
OUTPUT = DAY12 / "panel-unseen-human-queue-initialization-12.4.json"
UNSEEN = (3, 4, 5, 7, 18, 38)
LEGACY = (1, 2, 15, 17)
LEGACY_SHA = "5ac1383fdbd611bd203fa1e1b35d8fb0eb4e4e082f62e04907adc493c5635fd3"


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if freeze.get("status") != "FROZEN_BEFORE_HUMAN_GT":
        raise SystemExit("Prediction freeze invalid")
    db = SessionLocal()
    try:
        legacy = db.query(PanelGroundTruthReview).filter(
            PanelGroundTruthReview.page_order.in_(LEGACY)).order_by(PanelGroundTruthReview.page_order).all()
        legacy_material = [{"id": row.review_id, "state": row.state, "revision": row.revision,
                            "panels": row.human_panels, "hash": row.source_image_hash} for row in legacy]
        unseen = db.query(PanelGroundTruthReview).filter(
            PanelGroundTruthReview.page_order.in_(UNSEEN)).order_by(PanelGroundTruthReview.page_order).all()
        if semantic_hash(legacy_material) != LEGACY_SHA:
            raise SystemExit("Legacy Human GT changed")
        if (tuple(row.page_order for row in unseen) != UNSEEN or any(row.state != "PENDING" for row in unseen)
                or any(row.human_panels for row in unseen) or any(row.revision != 0 for row in unseen)):
            raise SystemExit("Unseen Human queue is not empty 0 VERIFIED / 6 PENDING")
        payload = {
            "schema_version": "panel-unseen-human-queue-initialization.v1", "checkpoint": "12.4",
            "prediction_freeze_file_sha256": file_sha(FREEZE),
            "prediction_fingerprint": freeze["semantic_sha256"],
            "prediction_frozen_before_queue": all(row.created_at.timestamp() >= FREEZE.stat().st_mtime for row in unseen),
            "pages": [{"page_order": row.page_order, "review_id": row.review_id,
                       "source_hash": row.source_image_hash, "state": row.state,
                       "revision": row.revision, "human_panel_count": 0} for row in unseen],
            "verified": 0, "pending": 6, "legacy_gt_snapshot_sha256": LEGACY_SHA,
            "predictions_hidden": True, "gt_runtime_features": [],
            "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0},
        }
        if not payload["prediction_frozen_before_queue"]:
            raise SystemExit("Human queue predates prediction freeze")
        payload["semantic_sha256"] = semantic_hash(payload)
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"pages": list(UNSEEN), "verified": 0, "pending": 6,
                          "prediction_fingerprint": freeze["semantic_sha256"]}))
    finally:
        db.close()


if __name__ == "__main__":
    main()
