import unittest
from unittest.mock import patch

from app.services.model_runtime import (
    PRODUCTION_STORY_MODEL,
    resolve_story_model,
    story_model_override,
)
from app.services.ollama_vision import DEFAULT_VISION_MODEL
from app.services.story_analyzer import analyze_story


READY_INPUT = {
    "contract_version": "story_input.v1",
    "project_id": "project-1",
    "status": "ready",
    "pages": [],
}


class StoryModelConfigTests(unittest.TestCase):
    def test_falls_back_to_production_default(self):
        self.assertEqual(resolve_story_model({}), PRODUCTION_STORY_MODEL)

    def test_resolves_environment_configuration(self):
        self.assertEqual(
            resolve_story_model({"STORY_MODEL": "qwen3:4b-instruct"}),
            "qwen3:4b-instruct",
        )

    def test_rejects_invalid_model_configuration(self):
        for invalid in ("", "https://remote/model", "model name", ":latest"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                resolve_story_model({"STORY_MODEL": invalid})

    def test_story_override_does_not_change_vision_model(self):
        with story_model_override("qwen3:4b-instruct"):
            self.assertEqual(resolve_story_model(), "qwen3:4b-instruct")
            self.assertEqual(DEFAULT_VISION_MODEL, "qwen3-vl:8b-instruct")

    @patch("app.services.story_analyzer.call_text_model")
    def test_analyzer_routes_only_story_call(self, call_text_model):
        call_text_model.return_value = {
            "characters": [], "events": [], "main_progression": []
        }
        with story_model_override("qwen3:4b-instruct"):
            analyze_story(READY_INPUT, max_retries=0)
        self.assertEqual(
            call_text_model.call_args.kwargs["model"], "qwen3:4b-instruct"
        )


if __name__ == "__main__":
    unittest.main()
