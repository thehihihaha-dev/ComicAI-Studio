import unittest
from unittest.mock import patch

from app.services.story_analyzer import (
    analyze_story,
    validate_story_result_structure,
)


def ready_story_input():
    return {
        "contract_version": "story_input.v1",
        "project_id": "project-1",
        "status": "ready",
        "pages": [
            {
                "asset_id": "asset-1",
                "page_order": 1,
                "page_type": "dialogue",
                "dialogues": [
                    {
                        "region_id": 3,
                        "order": 1,
                        "final_text": "Kazu kết hôn trong game.",
                        "text_source": "verified",
                        "decision": "verified",
                    }
                ],
            }
        ],
        "issues": [],
        "summary": {},
    }


def valid_model_result():
    return {
        "characters": [
            {
                "id": "character_1",
                "name": "Kazu",
                "sources": [
                    {
                        "asset_id": "asset-1",
                        "page_order": 1,
                        "region_ids": [3],
                    }
                ],
            }
        ],
        "events": [
            {
                "id": "event_1",
                "summary": "Kazu kết hôn trong game.",
                "importance": 0.9,
                "emotion": "romantic",
                "story_role": "main_story",
                "claims": [
                    {
                        "id": "event_1_claim_1",
                        "text": "Kazu kết hôn trong game.",
                        "claim_type": "fact",
                        "sources": [
                            {
                                "asset_id": "asset-1",
                                "page_order": 1,
                                "region_ids": [3],
                            }
                        ],
                    }
                ],
            }
        ],
        "main_progression": ["event_1"],
    }


class StoryAnalyzerTests(unittest.TestCase):
    @patch("app.services.story_analyzer.call_text_model")
    def test_retries_empty_model_output(self, call_model):
        empty = {"characters": [], "events": [], "main_progression": []}
        call_model.side_effect = [empty, valid_model_result()]

        result = analyze_story(ready_story_input(), max_retries=1)

        self.assertEqual(result["analysis_attempts"], 2)
        self.assertEqual(call_model.call_count, 2)

    @patch("app.services.story_analyzer.call_text_model")
    def test_retry_limit_preserves_failure(self, call_model):
        call_model.return_value = {
            "characters": [],
            "events": [],
            "main_progression": [],
        }

        with self.assertRaisesRegex(RuntimeError, "after 2 attempts"):
            analyze_story(ready_story_input(), max_retries=1)

        self.assertEqual(call_model.call_count, 2)

    @patch("app.services.story_analyzer.call_text_model")
    def test_retries_model_timeout(self, call_model):
        call_model.side_effect = [TimeoutError("timed out"), valid_model_result()]

        result = analyze_story(ready_story_input(), max_retries=1)

        self.assertEqual(result["analysis_attempts"], 2)
        self.assertEqual(call_model.call_count, 2)

    @patch("app.services.story_analyzer.call_text_model")
    def test_repairs_structural_output_with_compact_call(self, call_model):
        call_model.side_effect = [{"events": []}, valid_model_result()]
        result = analyze_story(ready_story_input(), max_retries=1)
        self.assertEqual(result["analysis_attempts"], 1)
        self.assertEqual(result["repair_attempts"], 1)
        self.assertEqual(call_model.call_count, 2)
        self.assertIn("VALIDATION ERROR", call_model.call_args.kwargs["prompt"])

    @patch("app.services.story_analyzer.call_text_model")
    def test_full_retry_after_repair_cannot_recover(self, call_model):
        call_model.side_effect = [
            {"events": []},
            {"characters": [], "events": "invalid", "main_progression": []},
            valid_model_result(),
        ]
        result = analyze_story(ready_story_input(), max_retries=1)
        self.assertEqual(result["analysis_attempts"], 2)
        self.assertEqual(result["repair_attempts"], 1)
        self.assertEqual(call_model.call_count, 3)

    @patch("app.services.story_analyzer.call_text_model")
    def test_analyzes_structured_story_input(self, call_model):
        call_model.return_value = valid_model_result()

        result = analyze_story(ready_story_input())

        self.assertEqual(result["analyzer_version"], "story_analyzer.v1")
        self.assertEqual(result["project_id"], "project-1")
        self.assertEqual(result["events"][0]["id"], "event_1")
        prompt = call_model.call_args.kwargs["prompt"]
        self.assertIn('"asset_id": "asset-1"', prompt)
        self.assertIn('"region_id": 3', prompt)
        self.assertIn("atomic claims", prompt)
        self.assertIn("BOTH region IDs", prompt)
        self.assertIn("Never use excluded_text", prompt)
        self.assertIn("neutral wording", prompt)

    def test_requires_event_story_role(self):
        result = valid_model_result()
        del result["events"][0]["story_role"]

        with self.assertRaisesRegex(ValueError, "story_role"):
            validate_story_result_structure(result)

    @patch("app.services.story_analyzer.call_text_model")
    def test_blocked_story_input_never_calls_model(self, call_model):
        story_input = ready_story_input()
        story_input["status"] = "blocked"

        with self.assertRaisesRegex(ValueError, "not ready"):
            analyze_story(story_input)

        call_model.assert_not_called()

    def test_rejects_claim_without_sources(self):
        result = valid_model_result()
        result["events"][0]["claims"][0]["sources"] = []

        with self.assertRaisesRegex(ValueError, "at least one source"):
            validate_story_result_structure(result)

    def test_requires_atomic_claims(self):
        result = valid_model_result()
        result["events"][0]["claims"] = []

        with self.assertRaisesRegex(ValueError, "at least one claim"):
            validate_story_result_structure(result)

    def test_attribution_without_subject_is_preserved_for_grounding(self):
        result = valid_model_result()
        claim = result["events"][0]["claims"][0]
        claim["claim_type"] = "speaker_attribution"

        normalized = validate_story_result_structure(result)
        self.assertNotIn("subject", normalized["events"][0]["claims"][0])

    def test_rejects_invalid_importance(self):
        result = valid_model_result()
        result["events"][0]["importance"] = 1.5

        with self.assertRaisesRegex(ValueError, "importance"):
            validate_story_result_structure(result)

    def test_rejects_duplicate_event_ids(self):
        result = valid_model_result()
        result["events"].append(dict(result["events"][0]))

        with self.assertRaisesRegex(ValueError, "Duplicate event id"):
            validate_story_result_structure(result)


if __name__ == "__main__":
    unittest.main()
