import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.routers.projects import (
    analyze_project_story,
    create_project_short_script,
    get_project_story_input,
)
from app.schemas.projects import ShortScriptCreate


READY_INPUT = {"status": "ready", "project_id": "project-1", "pages": []}


class StoryWorkspaceApiTests(unittest.TestCase):
    @patch("app.routers.projects.build_story_input")
    def test_story_input_adapter(self, build_input):
        build_input.return_value = READY_INPUT
        self.assertEqual(get_project_story_input("project-1"), READY_INPUT)

    @patch("app.routers.projects.run_reliable_story_analysis")
    @patch("app.routers.projects.build_story_input")
    @patch("app.routers.projects.save_story_result")
    @patch("app.routers.projects.SessionLocal")
    def test_story_analysis_delegates_to_service(
        self, session_local, save_result, build_input, analyze
    ):
        build_input.return_value = READY_INPUT
        analyze.return_value = {"reliability_version": "story_reliability.v1"}
        result = analyze_project_story("project-1")
        self.assertEqual(result["reliability_version"], "story_reliability.v1")
        analyze.assert_called_once_with(READY_INPUT)
        save_result.assert_called_once()
        session_local.return_value.close.assert_called_once()

    @patch("app.routers.projects.build_story_input")
    def test_blocked_story_returns_conflict(self, build_input):
        build_input.return_value = {"status": "blocked"}
        with self.assertRaises(HTTPException) as context:
            analyze_project_story("project-1")
        self.assertEqual(context.exception.status_code, 409)

    @patch("app.routers.projects.generate_short_script")
    @patch("app.routers.projects.serialize_short_script")
    @patch("app.routers.projects.save_generated_script")
    @patch("app.routers.projects.compose_story_review")
    @patch("app.routers.projects._story_record")
    @patch("app.routers.projects.SessionLocal")
    @patch("app.routers.projects.build_story_input")
    def test_script_adapter_uses_reliability_result(
        self, build_input, session_local, story_record, compose_review,
        save_script, serialize_script, generate
    ):
        build_input.return_value = READY_INPUT
        compose_review.return_value = {
            "final_story_ready": True,
            "story_approved": True,
            "final_story_fingerprint": "story-fingerprint",
            "approved_at": "2026-08-18T00:00:00+00:00",
            "final_story": {"grounded_result": {}},
        }
        generate.return_value = {"script_version": "short_script.v1"}
        serialize_script.return_value = {"persistence_version": "project_short_script.v1"}
        result = create_project_short_script(
            "project-1", ShortScriptCreate(style="dramatic")
        )
        self.assertEqual(result["persistence_version"], "project_short_script.v1")
        generate.assert_called_once_with(compose_review.return_value["final_story"], "dramatic")
        save_script.assert_called_once()
        session_local.return_value.close.assert_called_once()

    @patch("app.routers.projects.compose_story_review")
    @patch("app.routers.projects._story_record")
    @patch("app.routers.projects.SessionLocal")
    @patch("app.routers.projects.build_story_input")
    def test_script_is_blocked_when_backend_final_story_is_not_ready(
        self, build_input, session_local, story_record, compose_review
    ):
        build_input.return_value = READY_INPUT
        compose_review.return_value = {
            "final_story_ready": False,
            "story_approved": False,
            "final_story": {"grounded_result": {}},
        }
        with self.assertRaises(HTTPException) as context:
            create_project_short_script(
                "project-1", ShortScriptCreate(style="dramatic")
            )
        self.assertEqual(context.exception.status_code, 409)
        session_local.return_value.close.assert_called_once()

    @patch("app.routers.projects.save_generated_script")
    @patch("app.routers.projects.generate_short_script", side_effect=RuntimeError("model unavailable"))
    @patch("app.routers.projects.compose_story_review")
    @patch("app.routers.projects._story_record")
    @patch("app.routers.projects.SessionLocal")
    @patch("app.routers.projects.build_story_input")
    def test_failed_regeneration_never_overwrites_persisted_script(
        self, build_input, session_local, story_record, compose_review,
        generate, save_script
    ):
        build_input.return_value = READY_INPUT
        compose_review.return_value = {
            "final_story_ready": True,
            "story_approved": True,
            "final_story": {"grounded_result": {}},
            "final_story_fingerprint": "story-fingerprint",
            "approved_at": "2026-08-18T00:00:00+00:00",
        }
        with self.assertRaises(HTTPException) as context:
            create_project_short_script(
                "project-1", ShortScriptCreate(style="natural")
            )
        self.assertEqual(context.exception.status_code, 422)
        save_script.assert_not_called()


if __name__ == "__main__":
    unittest.main()
