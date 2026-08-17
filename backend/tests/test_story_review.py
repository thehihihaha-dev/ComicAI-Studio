import copy
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.project import Project
from app.models.project_story_analysis import ProjectStoryAnalysis
from app.services.story_review import (
    approve_final_story,
    compose_story_review,
    edit_story_event,
    resolve_unresolved,
)


REVISION = "revision-1"


def ai_result() -> dict:
    return {
        "project_id": "project-1",
        "reliability_version": "story_reliability.v1",
        "coverage": {
            "unresolved_regions": 2,
            "important_uncovered_regions": [
                {"asset_id": "asset-1", "page_order": 1, "region_id": 2, "evidence_text": "Kazu!", "text_role": "dialogue"},
                {"asset_id": "asset-2", "page_order": 2, "region_id": 3, "evidence_text": "Năm thứ hai", "text_role": "dialogue"},
            ],
        },
        "grounded_result": {
            "events": [{
                "id": "event-1",
                "summary": "Rin được giới thiệu.",
                "story_role": "main_story",
                "script_ready": True,
                "unsupported_claims": [],
                "claims": [{
                    "id": "claim-1",
                    "text": "Rin được giới thiệu.",
                    "sources": [{"asset_id": "asset-1", "page_order": 1, "region_ids": [1]}],
                }],
            }],
            "main_progression": ["event-1"],
        },
    }


class StoryReviewTests(unittest.TestCase):
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
            db.add(ProjectStoryAnalysis(
                id="story-1",
                project_id="project-1",
                result=ai_result(),
                status="partial",
                source_revision=REVISION,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def record(self, db):
        return db.query(ProjectStoryAnalysis).filter_by(project_id="project-1").one()

    def test_edit_event_persists_human_provenance_without_mutating_ai_result(self):
        with self.sessions() as db:
            original = copy.deepcopy(self.record(db).result)
            response = edit_story_event(db, self.record(db), "event-1", "  Rin giới thiệu bản thân.  ", REVISION, REVISION)
            event = response["final_story"]["grounded_result"]["events"][0]
            self.assertEqual(event["summary"], "Rin giới thiệu bản thân.")
            self.assertEqual(event["provenance"], "human_edited")
            self.assertEqual(self.record(db).result, original)
        with self.sessions() as db:
            restored = compose_story_review(self.record(db), REVISION)
            self.assertEqual(restored["final_story"]["grounded_result"]["events"][0]["provenance"], "human_edited")

    def test_empty_and_unknown_event_edits_are_rejected(self):
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as empty:
                edit_story_event(db, self.record(db), "event-1", "   ", REVISION, REVISION)
            self.assertEqual(empty.exception.status_code, 422)
            with self.assertRaises(HTTPException) as unknown:
                edit_story_event(db, self.record(db), "missing", "Text", REVISION, REVISION)
            self.assertEqual(unknown.exception.status_code, 404)

    def test_add_unresolved_creates_deterministic_human_event(self):
        with self.sessions() as db:
            response = resolve_unresolved(db, self.record(db), "asset-1", 2, "added_to_story", REVISION, REVISION, "Kazu gọi bạn mình.")
            human = next(event for event in response["final_story"]["grounded_result"]["events"] if event["provenance"] == "human_added")
            self.assertTrue(human["id"].startswith("human-event-"))
            self.assertEqual(human["claims"][0]["sources"][0]["region_ids"], [2])
            self.assertEqual(response["unresolved_remaining"], 1)

    def test_dismiss_uses_human_provenance_and_decrements_once(self):
        with self.sessions() as db:
            response = resolve_unresolved(db, self.record(db), "asset-1", 2, "non_story_relevant", REVISION, REVISION)
            resolution = self.record(db).review_state["resolutions"]["asset-1:2"]
            self.assertEqual(resolution["source"], "human")
            self.assertEqual(resolution["action"], "non_story_relevant")
            self.assertEqual(response["unresolved_remaining"], 1)
            with self.assertRaises(HTTPException) as duplicate:
                resolve_unresolved(db, self.record(db), "asset-1", 2, "non_story_relevant", REVISION, REVISION)
            self.assertEqual(duplicate.exception.status_code, 409)

    def test_unknown_evidence_and_revision_mismatch_are_rejected(self):
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as unknown:
                resolve_unresolved(db, self.record(db), "missing", 99, "non_story_relevant", REVISION, REVISION)
            self.assertEqual(unknown.exception.status_code, 404)
            with self.assertRaises(HTTPException) as mismatch:
                resolve_unresolved(db, self.record(db), "asset-1", 2, "non_story_relevant", "old", REVISION)
            self.assertEqual(mismatch.exception.status_code, 409)

    def test_review_complete_only_after_every_item_is_handled(self):
        with self.sessions() as db:
            first = resolve_unresolved(db, self.record(db), "asset-1", 2, "non_story_relevant", REVISION, REVISION)
            self.assertFalse(first["final_story_ready"])
            second = resolve_unresolved(db, self.record(db), "asset-2", 3, "added_to_story", REVISION, REVISION, "Mốc thời gian chuyển sang năm thứ hai.")
            self.assertTrue(second["review_complete"])
            self.assertTrue(second["final_story_ready"])
            self.assertEqual(second["unresolved_remaining"], 0)

    def test_approval_rejected_until_review_is_complete(self):
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as incomplete:
                approve_final_story(db, self.record(db), REVISION)
            self.assertEqual(incomplete.exception.status_code, 409)
            with self.assertRaises(HTTPException) as stale:
                approve_final_story(db, self.record(db), "revision-2")
            self.assertEqual(stale.exception.status_code, 409)

    def test_approval_persists_fingerprint_and_is_idempotent(self):
        with self.sessions() as db:
            resolve_unresolved(db, self.record(db), "asset-1", 2, "non_story_relevant", REVISION, REVISION)
            resolve_unresolved(db, self.record(db), "asset-2", 3, "non_story_relevant", REVISION, REVISION)
            approved = approve_final_story(db, self.record(db), REVISION)
            approved_at = approved["approved_at"]
            self.assertTrue(approved["story_approved"])
            self.assertEqual(approved["final_story_fingerprint"], approved["approved_story_fingerprint"])
            duplicate = approve_final_story(db, self.record(db), REVISION)
            self.assertEqual(duplicate["approved_at"], approved_at)
        with self.sessions() as db:
            restored = compose_story_review(self.record(db), REVISION)
            self.assertTrue(restored["story_approved"])

    def test_event_edit_invalidates_approval_and_reapproval_works(self):
        with self.sessions() as db:
            resolve_unresolved(db, self.record(db), "asset-1", 2, "non_story_relevant", REVISION, REVISION)
            resolve_unresolved(db, self.record(db), "asset-2", 3, "non_story_relevant", REVISION, REVISION)
            approve_final_story(db, self.record(db), REVISION)
            changed = edit_story_event(db, self.record(db), "event-1", "Nội dung đã đổi.", REVISION, REVISION)
            self.assertFalse(changed["story_approved"])
            self.assertTrue(changed["approval_invalidated"])
            self.assertTrue(approve_final_story(db, self.record(db), REVISION)["story_approved"])

    def test_human_added_event_edit_invalidates_approval(self):
        with self.sessions() as db:
            added = resolve_unresolved(db, self.record(db), "asset-1", 2, "added_to_story", REVISION, REVISION, "Kazu gọi bạn.")
            event_id = added["human_added_event_ids"][0]
            resolve_unresolved(db, self.record(db), "asset-2", 3, "non_story_relevant", REVISION, REVISION)
            approve_final_story(db, self.record(db), REVISION)
            changed = edit_story_event(db, self.record(db), event_id, "Kazu gọi Rin.", REVISION, REVISION)
            self.assertFalse(changed["story_approved"])
            human = next(event for event in changed["final_story"]["grounded_result"]["events"] if event["id"] == event_id)
            self.assertEqual(human["summary"], "Kazu gọi Rin.")

    def test_stale_review_never_unlocks_final_story(self):
        with self.sessions() as db:
            resolve_unresolved(db, self.record(db), "asset-1", 2, "non_story_relevant", REVISION, REVISION)
            resolve_unresolved(db, self.record(db), "asset-2", 3, "non_story_relevant", REVISION, REVISION)
            stale = compose_story_review(self.record(db), "revision-2")
            self.assertTrue(stale["stale"])
            self.assertFalse(stale["final_story_ready"])
            self.assertEqual(stale["unresolved_remaining"], 2)

    def test_project_isolation(self):
        with self.sessions() as db:
            edit_story_event(db, self.record(db), "event-1", "Bản sửa", REVISION, REVISION)
            self.assertIsNone(db.query(ProjectStoryAnalysis).filter_by(project_id="project-2").first())


if __name__ == "__main__":
    unittest.main()
