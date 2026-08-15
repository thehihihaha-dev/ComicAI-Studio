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
    def test_story_analysis_delegates_to_service(self, build_input, analyze):
        build_input.return_value = READY_INPUT
        analyze.return_value = {"reliability_version": "story_reliability.v1"}
        result = analyze_project_story("project-1")
        self.assertEqual(result["reliability_version"], "story_reliability.v1")
        analyze.assert_called_once_with(READY_INPUT)

    @patch("app.routers.projects.build_story_input")
    def test_blocked_story_returns_conflict(self, build_input):
        build_input.return_value = {"status": "blocked"}
        with self.assertRaises(HTTPException) as context:
            analyze_project_story("project-1")
        self.assertEqual(context.exception.status_code, 409)

    @patch("app.routers.projects.generate_short_script")
    @patch("app.routers.projects.run_reliable_story_analysis")
    @patch("app.routers.projects.build_story_input")
    def test_script_adapter_uses_reliability_result(
        self, build_input, analyze, generate
    ):
        build_input.return_value = READY_INPUT
        analyze.return_value = {"grounded_result": {}}
        generate.return_value = {"script_version": "short_script.v1"}
        result = create_project_short_script(
            "project-1", ShortScriptCreate(style="dramatic")
        )
        self.assertEqual(result["script_version"], "short_script.v1")
        generate.assert_called_once_with(analyze.return_value, "dramatic")


if __name__ == "__main__":
    unittest.main()
