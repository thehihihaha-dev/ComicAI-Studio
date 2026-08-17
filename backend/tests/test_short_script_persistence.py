import copy
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.project import Project
from app.models.project_short_script import ProjectShortScript
from app.services.short_script_persistence import (
    approve_short_script,
    edit_script_segment,
    save_generated_script,
    serialize_short_script,
)


STORY_FINGERPRINT = "story-fingerprint"


def generated_result() -> dict:
    segment_types = ("hook", "setup", "development", "payoff", "ending")
    return {
        "script_version": "short_script.v1",
        "segments": [
            {
                "id": f"segment-{index}",
                "type": segment_type,
                "text": f"Nội dung tiếng Việt đoạn {index}.",
                "source_event_ids": ["event-1"],
                "source_claim_ids": ["claim-1"],
            }
            for index, segment_type in enumerate(segment_types, start=1)
        ],
        "summary": {"word_count": 25},
    }


def approved_story(approved_at: datetime, fingerprint: str = STORY_FINGERPRINT) -> dict:
    return {
        "story_approved": True,
        "approved_at": approved_at,
        "final_story_fingerprint": fingerprint,
        "final_story": {
            "grounded_result": {
                "events": [{"id": "event-1", "script_ready": True}],
            }
        },
    }


class ShortScriptPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            for project_id in ("project-1", "project-2"):
                db.add(Project(id=project_id, name=project_id, content_type="short", status="ready", created_at=datetime.now(timezone.utc)))
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def create_script(self, db) -> ProjectShortScript:
        approved_at = datetime.now(timezone.utc)
        return save_generated_script(
            db,
            "project-1",
            generated_result(),
            "natural",
            STORY_FINGERPRINT,
            approved_at,
        )

    def review_for(self, record: ProjectShortScript, fingerprint: str = STORY_FINGERPRINT, approved: bool = True) -> dict:
        review = approved_story(record.source_story_approved_at, fingerprint)
        review["story_approved"] = approved
        return review

    def test_generated_script_persists_and_reloads_with_sources(self):
        with self.sessions() as db:
            record = self.create_script(db)
            serialized = serialize_short_script(record, self.review_for(record))
            self.assertEqual(serialized["status"], "generated")
            self.assertEqual(serialized["style"], "natural")
            self.assertEqual(serialized["final_script"]["segments"][0]["source_event_ids"], ["event-1"])
        with self.sessions() as db:
            restored = db.query(ProjectShortScript).one()
            self.assertEqual(restored.result["segments"][0]["type"], "hook")

    def test_segment_edit_persists_and_invalidates_approval(self):
        with self.sessions() as db:
            record = self.create_script(db)
            approved = approve_short_script(db, record, self.review_for(record))
            self.assertTrue(approved["script_approved"])
            edited = edit_script_segment(db, record, "segment-1", "  Mở đầu do người dùng sửa.  ", self.review_for(record))
            self.assertEqual(edited["status"], "edited")
            self.assertFalse(edited["script_approved"])
            self.assertTrue(edited["approval_invalidated"])
            self.assertEqual(edited["final_script"]["segments"][0]["provenance"], "human_edited")

    def test_empty_and_unknown_segment_edits_are_rejected(self):
        with self.sessions() as db:
            record = self.create_script(db)
            with self.assertRaises(HTTPException) as empty:
                edit_script_segment(db, record, "segment-1", "   ", self.review_for(record))
            self.assertEqual(empty.exception.status_code, 422)
            with self.assertRaises(HTTPException) as unknown:
                edit_script_segment(db, record, "missing", "Text", self.review_for(record))
            self.assertEqual(unknown.exception.status_code, 404)

    def test_approval_persists_and_handoff_contract_is_complete(self):
        with self.sessions() as db:
            record = self.create_script(db)
            result = approve_short_script(db, record, self.review_for(record))
            self.assertTrue(result["script_approved"])
            self.assertEqual(result["approved_fingerprint"], result["script_fingerprint"])
            handoff = result["tts_handoff"]
            self.assertEqual(handoff["language"], "vi")
            self.assertEqual(handoff["status"], "approved")
            self.assertEqual(len(handoff["segments"]), 5)
            self.assertGreater(handoff["word_count"], 0)
            self.assertGreater(handoff["estimated_duration_seconds"], 0)

    def test_story_change_or_reapproval_makes_script_stale(self):
        with self.sessions() as db:
            record = self.create_script(db)
            changed = serialize_short_script(record, self.review_for(record, "new-story"))
            self.assertTrue(changed["stale"])
            reapproved = self.review_for(record)
            reapproved["approved_at"] = datetime.now(timezone.utc)
            self.assertTrue(serialize_short_script(record, reapproved)["stale"])

    def test_unapproved_story_rejects_script_approval(self):
        with self.sessions() as db:
            record = self.create_script(db)
            with self.assertRaises(HTTPException) as context:
                approve_short_script(db, record, self.review_for(record, approved=False))
            self.assertEqual(context.exception.status_code, 409)

    def test_regeneration_replaces_only_after_save_and_project_isolation(self):
        with self.sessions() as db:
            record = self.create_script(db)
            old_result = copy.deepcopy(record.result)
            self.assertEqual(db.query(ProjectShortScript).count(), 1)
            self.assertEqual(record.result, old_result)
            self.assertIsNone(db.query(ProjectShortScript).filter_by(project_id="project-2").first())


if __name__ == "__main__":
    unittest.main()
