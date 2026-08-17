import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.asset import Asset
from app.models.dialogue_ground_truth import DialogueGroundTruth
from app.models.project import Project
from app.routers.assets import get_review_queue, verify_dialogue


class DialogueVerificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        with self.session_factory() as db:
            db.add(
                Project(
                    id="project-1",
                    name="Test",
                    content_type="short",
                    status="ready",
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.add(
                Asset(
                    id="asset-1",
                    project_id="project-1",
                    filename="page.jpg",
                    file_type="image",
                    file_path="uploads/page.jpg",
                    page_order=1,
                    created_at=datetime.now(timezone.utc),
                    dialogues=json.dumps(
                        [
                            {
                                "region_id": 1,
                                "raw_text": "SAFE",
                                "clean_text": "SAFE",
                                "decision": "auto_recovered",
                            },
                            {
                                "region_id": 3,
                                "raw_text": "NGUYỆN YẾU",
                                "clean_text": "NGUYỆN YÊU",
                                "decision": "needs_review",
                                "correction_score": 0.7,
                            }
                        ]
                    ),
                    dialogue_status="needs_review",
                )
            )
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def test_reverification_updates_one_ground_truth_row(self):
        with patch(
            "app.routers.assets.SessionLocal",
            self.session_factory,
        ):
            first = verify_dialogue("asset-1", 3, "NGUYỆN YÊU")
            second = verify_dialogue("asset-1", 3, "NGUYỆN YÊU!")

        self.assertEqual(first["decision"], "verified")
        self.assertEqual(second["verified_text"], "NGUYỆN YÊU!")

        with self.session_factory() as db:
            rows = db.query(DialogueGroundTruth).all()
            asset = db.get(Asset, "asset-1")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].verified_text, "NGUYỆN YÊU!")
        dialogues = json.loads(asset.dialogues)
        self.assertEqual(dialogues[0]["clean_text"], "SAFE")
        self.assertEqual(dialogues[0]["decision"], "auto_recovered")
        self.assertEqual(dialogues[1]["clean_text"], "NGUYỆN YÊU!")
        self.assertTrue(dialogues[1]["human_verified"])
        self.assertFalse(dialogues[1]["needs_review"])
        self.assertEqual(asset.dialogue_status, "completed")

    def test_review_item_disappears_only_after_successful_verification(self):
        with patch("app.routers.assets.SessionLocal", self.session_factory):
            before = get_review_queue("project-1")
            verify_dialogue("asset-1", 3, "NGUYỆN YÊU")
            after = get_review_queue("project-1")

        self.assertEqual(before["review_count"], 1)
        self.assertEqual(after["review_count"], 0)

    def test_dialogue_region_bbox_uses_only_region_blocks(self):
        from app.routers.assets import dialogue_region_bbox

        bbox = dialogue_region_bbox(
            {"id": 8, "block_ids": [1]},
            [
                {"box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
                {"box": [[20, 30], [50, 30], [50, 60], [20, 60]]},
            ],
        )
        self.assertEqual(bbox, [20, 30, 50, 60])


if __name__ == "__main__":
    unittest.main()
