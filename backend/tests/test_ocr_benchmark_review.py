import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.asset import Asset
from app.models.dialogue_ground_truth import DialogueGroundTruth
from app.models.ocr_benchmark_review import OcrBenchmarkReview
from app.models.project import Project
from app.services.ocr_benchmark_review import (
    crop_response, load_queue, serialize_queue, update_review, verified_samples,
)


class OcrBenchmarkReviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine); self.Session = sessionmaker(bind=self.engine)
        self.temp = tempfile.TemporaryDirectory(); root = Path(self.temp.name)
        self.image = root / "source.png"; Image.new("RGB", (100, 80), "white").save(self.image)
        image_hash = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.queue = root / "queue.json"
        self.queue.write_text(json.dumps({"requires_human_transcription": [
            {"sample_id": "sample-1", "project_id": None, "asset_id": "asset-1", "page_order": 1,
             "region_id": 3, "bbox": [10, 10, 60, 50], "text_role": "dialogue", "image_sha256": image_hash},
            {"sample_id": "missing", "project_id": "project-1", "asset_id": "asset-1", "page_order": 1,
             "region_id": 4, "bbox": None, "text_role": "dialogue", "image_sha256": image_hash},
        ]}))
        db = self.Session(); db.add(Project(id="project-1", name="P", content_type="short", status="ready", created_at=datetime.now(timezone.utc)))
        db.add(Project(id="project-2", name="P2", content_type="short", status="ready", created_at=datetime.now(timezone.utc)))
        db.add(Asset(id="asset-1", project_id="project-1", filename="source.png", file_type="image/png",
                     file_path=str(self.image), page_order=1, created_at=datetime.now(timezone.utc), status="ready",
                     vision_status="completed", dialogue_status="completed")); db.commit(); db.close()
        self.queue_patch = patch("app.services.ocr_benchmark_review.QUEUE_PATH", self.queue); self.queue_patch.start()

    def tearDown(self):
        self.queue_patch.stop(); self.temp.cleanup(); self.engine.dispose()

    def test_queue_load_source_unavailable_and_no_predictions(self):
        db = self.Session(); payload = serialize_queue(db, "project-1")
        self.assertEqual(payload["total"], 2); self.assertEqual(payload["items"][0]["state"], "PENDING")
        self.assertEqual(payload["items"][1]["state"], "SOURCE_UNAVAILABLE")
        forbidden = {"raw_text", "ai_text", "easyocr", "paddleocr", "recovered_text"}
        self.assertFalse(forbidden.intersection(payload["items"][0])); db.close()

    def test_valid_save_idempotency_edit_and_reload(self):
        db = self.Session(); load_queue(db, "project-1")
        first = update_review(db, "project-1", "sample-1", "VERIFIED", "  Tôi!\n")
        second = update_review(db, "project-1", "sample-1", "VERIFIED", "  Tôi!\n")
        self.assertEqual(first["revision"], second["revision"]); db.close()
        db = self.Session(); rows = db.query(DialogueGroundTruth).all(); self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].verified_text, "  Tôi!\n"); self.assertEqual(rows[0].raw_text, ""); self.assertIsNone(rows[0].ai_text)
        edited = update_review(db, "project-1", "sample-1", "VERIFIED", "Tôi!")
        self.assertEqual(edited["revision"], first["revision"] + 1)
        self.assertEqual(edited["benchmark_cache_revision"], first["benchmark_cache_revision"] + 1); db.close()

    def test_empty_skip_unreadable_and_project_isolation(self):
        db = self.Session(); load_queue(db, "project-1")
        with self.assertRaises(HTTPException): update_review(db, "project-1", "sample-1", "VERIFIED", "  ")
        self.assertEqual(update_review(db, "project-1", "sample-1", "SKIPPED", None)["state"], "SKIPPED")
        self.assertEqual(update_review(db, "project-1", "sample-1", "UNREADABLE", None)["state"], "UNREADABLE")
        self.assertEqual(db.query(DialogueGroundTruth).count(), 0)
        with self.assertRaises(HTTPException): crop_response(db, "project-2", "sample-1")
        db.close()

    def test_hash_mismatch_excludes_verified_benchmark(self):
        db = self.Session(); load_queue(db, "project-1"); update_review(db, "project-1", "sample-1", "VERIFIED", "Human")
        self.assertEqual(len(verified_samples(db)), 1)
        Image.new("RGB", (100, 80), "black").save(self.image)
        self.assertEqual(verified_samples(db), [])
        with self.assertRaises(HTTPException): update_review(db, "project-1", "sample-1", "VERIFIED", "Changed")
        db.close()

    def test_existing_gt_is_not_duplicated_into_queue(self):
        db = self.Session(); db.add(DialogueGroundTruth(asset_id="asset-1", region_id=3, raw_text="", ai_text=None, verified_text="Human")); db.commit()
        rows = load_queue(db, "project-1")
        self.assertEqual([row.sample_id for row in rows], ["missing"]); db.close()

    @patch("app.services.ollama_vision.call_vision_model")
    @patch("app.services.ocr_service.extract_ocr_blocks")
    def test_queue_and_actions_make_no_ocr_or_model_calls(self, ocr, vision):
        db = self.Session(); serialize_queue(db, "project-1")
        update_review(db, "project-1", "sample-1", "SKIPPED", None)
        ocr.assert_not_called(); vision.assert_not_called(); db.close()


if __name__ == "__main__": unittest.main()
