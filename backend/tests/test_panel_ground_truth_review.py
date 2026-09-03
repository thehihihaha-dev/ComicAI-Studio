import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.panel_ground_truth_review import PanelGroundTruthReview
from app.services.panel_ground_truth_review import (
    image_bytes,
    load_queue,
    save_review,
    selected_manifest,
    serialize_queue,
)


class PanelGroundTruthReviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_deterministic_six_page_manifest_and_hashes(self):
        first, second = selected_manifest(), selected_manifest()
        self.assertEqual(first, second)
        self.assertEqual([item["page_order"] for item in first], [3, 4, 5, 7, 18, 38])
        self.assertEqual(len({item["source_hash"] for item in first}), 6)
        self.assertTrue(all(len(item["source_hash"]) == 64 for item in first))

    def test_queue_hides_predictions_and_starts_pending(self):
        db = self.Session(); payload = serialize_queue(db)
        self.assertEqual((payload["total"], payload["verified"], payload["pending"]), (6, 0, 6))
        self.assertEqual((payload["checkpoint"], payload["cohort"]), ("12.4", "12.4-unseen"))
        self.assertTrue(payload["predictions_hidden"])
        forbidden = {"predicted_panels", "selected_panels", "candidates", "detected_panel_count",
                     "ambiguous_panel_count", "unresolved", "confidence", "evidence", "selection_role",
                     "iou", "rejection_reasons", "expected_panel_count"}
        self.assertTrue(all(forbidden.isdisjoint(item) for item in payload["items"]))
        self.assertTrue(all(item["human_panels"] == [] for item in payload["items"])); db.close()

    def test_save_edit_delete_ambiguity_and_reload(self):
        db = self.Session(); rows = load_queue(db); target = rows[0]
        first = [{"panel_id": "human-1", "bbox": [1, 2, 100, 120], "ambiguous": True},
                 {"panel_id": "human-2", "bbox": [120, 10, 220, 130], "ambiguous": False}]
        saved = save_review(db, target.review_id, first); self.assertEqual(saved["panel_count"], 2)
        edited = [{"panel_id": "human-1", "bbox": [5, 6, 110, 125], "ambiguous": False}]
        save_review(db, target.review_id, edited); db.expire_all()
        reloaded = db.get(PanelGroundTruthReview, target.review_id)
        self.assertEqual(reloaded.state, "VERIFIED")
        self.assertEqual(reloaded.human_panels, [{"panel_id": "human-1", "bbox": [5.0, 6.0, 110.0, 125.0], "ambiguous": False}])
        self.assertEqual(serialize_queue(db)["verified"], 1); db.close()

    def test_completing_one_page_does_not_change_another(self):
        db = self.Session(); rows = load_queue(db); untouched = rows[1]
        snapshot = (untouched.state, untouched.human_panels, untouched.revision, untouched.updated_at)
        save_review(db, rows[0].review_id, [{"panel_id": "p", "bbox": [1, 1, 50, 50], "ambiguous": False}])
        db.expire_all(); untouched = db.get(PanelGroundTruthReview, untouched.review_id)
        self.assertEqual((untouched.state, untouched.human_panels, untouched.revision, untouched.updated_at), snapshot); db.close()

    def test_legacy_rows_are_preserved_and_excluded_from_unseen_queue(self):
        db = self.Session()
        legacy = PanelGroundTruthReview(
            review_id="panel-gt-12.2:legacy", benchmark_asset_id="legacy-asset", page_order=1,
            selection_role="CONTROL_A", source_image_hash="a" * 64, source_path="legacy.jpg",
            image_width=900, image_height=1280,
            human_panels=[{"panel_id": "old", "bbox": [1, 1, 50, 50], "ambiguous": False}],
            state="VERIFIED", revision=3,
        )
        db.add(legacy); db.commit()
        snapshot = (legacy.human_panels, legacy.state, legacy.revision)
        payload = serialize_queue(db); db.refresh(legacy)
        self.assertEqual([item["page_order"] for item in payload["items"]], [3, 4, 5, 7, 18, 38])
        self.assertEqual((legacy.human_panels, legacy.state, legacy.revision), snapshot)
        db.close()

    def test_queue_fails_closed_without_prediction_freeze(self):
        db = self.Session()
        with patch("app.services.panel_ground_truth_review._prediction_freeze_valid", return_value=False):
            with self.assertRaises(RuntimeError):
                load_queue(db)
        db.close()

    def test_invalid_boxes_and_empty_completion_rejected(self):
        db = self.Session(); row = load_queue(db)[0]
        invalid = ([], [{"panel_id": "x", "bbox": [-1, 0, 5, 5], "ambiguous": False}],
                   [{"panel_id": "x", "bbox": [1, 1, row.image_width + 1, 5], "ambiguous": False}],
                   [{"panel_id": "x", "bbox": [5, 5, 1, 1], "ambiguous": False}])
        for panels in invalid:
            with self.assertRaises(HTTPException): save_review(db, row.review_id, panels)
        db.close()

    def test_source_mismatch_blocks_image_and_save(self):
        db = self.Session(); row = load_queue(db)[0]
        with patch("app.services.panel_ground_truth_review._compatible", return_value=False):
            with self.assertRaises(HTTPException): image_bytes(db, row.review_id)
            with self.assertRaises(HTTPException): save_review(db, row.review_id, [{"panel_id": "p", "bbox": [1, 1, 50, 50]}])
        db.close()

    def test_zero_model_calls(self):
        db = self.Session(); payload = serialize_queue(db)
        self.assertEqual(payload["model_calls"], {"ocr": 0, "vlm": 0, "ollama": 0}); db.close()


if __name__ == "__main__":
    unittest.main()
