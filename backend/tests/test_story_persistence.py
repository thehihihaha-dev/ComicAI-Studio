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
from app.models.project import Project
from app.models.project_story_analysis import ProjectStoryAnalysis
from app.routers.assets import get_dialogue_region
from app.routers.projects import analyze_project_story, get_project_story_analysis
from app.services.story_persistence import (
    save_story_result,
    serialize_story_record,
    story_result_status,
    story_source_revision,
)


def story_result(unresolved: int) -> dict:
    return {
        "reliability_version": "story_reliability.v1",
        "coverage": {
            "unresolved_regions": unresolved,
            "important_uncovered_regions": [],
        },
        "grounded_result": {
            "events": [
                {
                    "id": "event-1",
                    "story_role": "main_story",
                    "script_ready": True,
                }
            ],
            "main_progression": ["event-1"],
        },
    }


class StoryPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        with self.session_factory() as db:
            for project_id in ("project-1", "project-2"):
                db.add(
                    Project(
                        id=project_id,
                        name=project_id,
                        content_type="short",
                        status="ready",
                        created_at=datetime.now(timezone.utc),
                    )
                )
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def test_source_revision_is_stable_and_changes_with_source(self):
        first = {
            "contract_version": "story_input.v1",
            "project_id": "project-1",
            "status": "ready",
            "pages": [{"asset_id": "a", "page_order": 1, "dialogues": []}],
        }
        reordered_keys = json.loads(json.dumps(first, sort_keys=True))
        self.assertEqual(story_source_revision(first), story_source_revision(reordered_keys))
        reordered_keys["pages"][0]["page_order"] = 2
        self.assertNotEqual(story_source_revision(first), story_source_revision(reordered_keys))

    def test_partial_and_ready_results_persist(self):
        with self.session_factory() as db:
            partial = save_story_result(db, "project-1", story_result(2), "revision-1")
            self.assertEqual(partial.status, "partial")
            ready = save_story_result(db, "project-1", story_result(0), "revision-1")
            self.assertEqual(ready.status, "ready")
            self.assertEqual(db.query(ProjectStoryAnalysis).count(), 1)

    def test_stale_status_and_project_isolation(self):
        with self.session_factory() as db:
            record = save_story_result(db, "project-1", story_result(1), "old")
            response = serialize_story_record(record, "new")
            self.assertEqual(response["status"], "stale")
            self.assertTrue(response["stale"])
            self.assertIsNone(
                db.query(ProjectStoryAnalysis)
                .filter(ProjectStoryAnalysis.project_id == "project-2")
                .first()
            )

    def test_failed_analysis_preserves_previous_result(self):
        with self.session_factory() as db:
            record = save_story_result(db, "project-1", story_result(1), "revision-1")
            record.review_state = {"event_edits": {"event-1": {"text": "Human edit"}}, "resolutions": {}}
            record.review_source_revision = "revision-1"
            record.review_status = "in_progress"
            db.commit()
        ready_input = {"status": "ready", "project_id": "project-1", "pages": []}
        with (
            patch("app.routers.projects.SessionLocal", self.session_factory),
            patch("app.routers.projects.build_story_input", return_value=ready_input),
            patch(
                "app.routers.projects.run_reliable_story_analysis",
                side_effect=RuntimeError("model unavailable"),
            ),
        ):
            with self.assertRaises(HTTPException):
                analyze_project_story("project-1")
        with self.session_factory() as db:
            record = db.query(ProjectStoryAnalysis).one()
            self.assertEqual(record.result["coverage"]["unresolved_regions"], 1)
            self.assertEqual(record.review_state["event_edits"]["event-1"]["text"], "Human edit")

    def test_successful_reanalysis_invalidates_approval_even_when_revision_matches(self):
        with self.session_factory() as db:
            record = save_story_result(db, "project-1", story_result(0), "revision-1")
            record.approved_at = datetime.now(timezone.utc)
            record.approval_source_revision = "revision-1"
            record.approval_story_fingerprint = "approved-fingerprint"
            db.commit()
            save_story_result(db, "project-1", story_result(0), "revision-1")
            self.assertTrue(record.approval_story_fingerprint.startswith("invalidated:"))

    def test_get_returns_persisted_result(self):
        story_input = {"status": "ready", "project_id": "project-1", "pages": []}
        revision = story_source_revision(story_input)
        with self.session_factory() as db:
            save_story_result(db, "project-1", story_result(1), revision)
        with (
            patch("app.routers.projects.SessionLocal", self.session_factory),
            patch("app.routers.projects.build_story_input", return_value=story_input),
        ):
            response = get_project_story_analysis("project-1")
        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["result"]["grounded_result"]["events"][0]["id"], "event-1")

    def test_status_contract(self):
        self.assertEqual(story_result_status(story_result(1)), "partial")
        self.assertEqual(story_result_status(story_result(0)), "ready")


class RegionLookupTests(unittest.TestCase):
    def test_bbox_lookup_returns_image_dimensions(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        session_factory = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "page.png"
            Image.new("RGB", (200, 100)).save(image_path)
            with session_factory() as db:
                db.add(Project(id="p", name="p", content_type="short", status="ready", created_at=datetime.now(timezone.utc)))
                db.add(
                    Asset(
                        id="a",
                        project_id="p",
                        filename="page.png",
                        file_type="image",
                        file_path=str(image_path),
                        page_order=1,
                        created_at=datetime.now(timezone.utc),
                        ocr_blocks=json.dumps([{"box": [[10, 20], [80, 20], [80, 60], [10, 60]]}]),
                        vision_regions=json.dumps([{"id": 7, "type": "dialogue", "block_ids": [0]}]),
                    )
                )
                db.commit()
            with patch("app.routers.assets.SessionLocal", session_factory):
                result = get_dialogue_region("a", 7)
            self.assertEqual(result["bbox"], [10, 20, 80, 60])
            self.assertEqual(result["image_size"], {"width": 200, "height": 100})
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
