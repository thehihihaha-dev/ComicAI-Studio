import unittest
from unittest.mock import patch

from app.services.short_script_engine import (
    build_content_plan,
    build_script_input,
    generate_short_script,
    render_deterministic_fallback,
    validate_short_script,
)


def grounded_events():
    return [
        {
            "id": "event-1",
            "story_role": "main_story",
            "script_ready": True,
            "unsupported_claims": [],
            "claims": [{"id": "claim-1", "text": "Một nhân vật kết hôn trong game."}],
        },
        {
            "id": "event-unsafe",
            "script_ready": False,
            "unsupported_claims": [{"id": "bad"}],
            "claims": [],
        },
    ]


def valid_script():
    return {
        "segments": [
            {
                "id": f"segment_{index}",
                "type": segment_type,
                "text": f"Nội dung {segment_type}.",
                "source_event_ids": ["event-1"],
                "source_claim_ids": ["claim-1"],
                "factual_claims_used": ["claim-1"],
            }
            for index, segment_type in enumerate(
                ("hook", "setup", "development", "payoff", "ending"), start=1
            )
        ]
    }


def reliability_result():
    return {
        "project_id": "project-1",
        "coverage": {"unresolved_regions": 2},
        "grounded_result": {
            "main_progression": ["event-1", "event-unsafe"],
            "events": grounded_events(),
        },
    }


def style_selection(style="emotional"):
    return {
        "beats": [
            {"beat_id": f"beat_{index}", "style_phrase_id": f"{style}_{role}"}
            for index, role in enumerate(
                ("hook", "setup", "development", "payoff", "ending"), start=1
            )
        ]
    }


class ScriptInputTests(unittest.TestCase):
    def test_filters_unsafe_events_and_unresolved_evidence(self):
        result = build_script_input(reliability_result())
        self.assertEqual([event["id"] for event in result["safe_events"]], ["event-1"])
        self.assertEqual(result["main_progression"], ["event-1"])
        self.assertEqual(result["unresolved_evidence_count"], 2)

    def test_supporting_context_cannot_be_the_whole_script(self):
        data = reliability_result()
        data["grounded_result"]["events"][0]["story_role"] = "supporting_context"
        with self.assertRaisesRegex(ValueError, "main_story"):
            build_script_input(data)


class ContentPlanTests(unittest.TestCase):
    def test_plan_is_deterministic_and_follows_progression(self):
        data = reliability_result()
        data["grounded_result"]["events"].insert(
            1,
            {
                "id": "event-2",
                "story_role": "main_story",
                "script_ready": True,
                "unsupported_claims": [],
                "claims": [{"id": "claim-2", "text": "Sự kiện thứ hai."}],
            },
        )
        data["grounded_result"]["main_progression"] = ["event-2", "event-1"]
        plan = build_content_plan(build_script_input(data))
        self.assertEqual(plan[0]["claim_ids"], ["claim-2"])
        self.assertEqual(plan[1]["claim_ids"], ["claim-1"])
        self.assertEqual([beat["role"] for beat in plan], list((
            "hook", "setup", "development", "payoff", "ending"
        )))

    def test_supporting_context_is_added_only_to_setup(self):
        data = reliability_result()
        data["grounded_result"]["events"].append(
            {
                "id": "context-1",
                "story_role": "supporting_context",
                "script_ready": True,
                "unsupported_claims": [],
                "claims": [{"id": "context-claim", "text": "Bối cảnh thế giới."}],
            }
        )
        plan = build_content_plan(build_script_input(data))
        self.assertIn("context-claim", plan[1]["claim_ids"])
        self.assertNotIn("context-claim", plan[0]["claim_ids"])
        self.assertNotIn("context-claim", plan[2]["claim_ids"])

    def test_fallback_preserves_claim_references_and_removes_quotes(self):
        data = reliability_result()
        data["grounded_result"]["events"][0]["claims"][0]["text"] = (
            'Một nhân vật nói “đã kết hôn trong game”.'
        )
        script_input = build_script_input(data)
        plan = build_content_plan(script_input)
        fallback = render_deterministic_fallback(plan, "funny")
        segment = fallback["segments"][0]
        self.assertNotIn("“", segment["text"])
        self.assertNotIn("”", segment["text"])
        self.assertEqual(segment["source_claim_ids"], ["claim-1"])
        self.assertEqual(segment["factual_claims_used"], ["claim-1"])
        validate_short_script(fallback, script_input["safe_events"], "funny")

    def test_all_main_claims_are_included_in_plan(self):
        data = reliability_result()
        data["grounded_result"]["events"][0]["claims"] = [
            {"id": f"claim-{index}", "text": f"Fact {index}."}
            for index in range(1, 7)
        ]
        plan = build_content_plan(build_script_input(data))
        included = {
            claim_id for beat in plan for claim_id in beat["claim_ids"]
        }
        self.assertEqual(included, {f"claim-{index}" for index in range(1, 7)})


class ScriptValidationTests(unittest.TestCase):
    def test_valid_structured_script(self):
        result = validate_short_script(valid_script(), grounded_events(), "emotional")
        self.assertEqual(len(result["segments"]), 5)

    def test_invalid_event_reference(self):
        script = valid_script()
        script["segments"][0]["source_event_ids"] = ["invented"]
        with self.assertRaisesRegex(ValueError, "unsafe or unknown"):
            validate_short_script(script, grounded_events(), "emotional")

    def test_unsupported_event_reference(self):
        script = valid_script()
        script["segments"][0]["source_event_ids"] = ["event-unsafe"]
        with self.assertRaisesRegex(ValueError, "unsafe or unknown"):
            validate_short_script(script, grounded_events(), "emotional")

    def test_duplicate_segment_ids(self):
        script = valid_script()
        script["segments"][1]["id"] = "segment_1"
        with self.assertRaisesRegex(ValueError, "Duplicate segment"):
            validate_short_script(script, grounded_events(), "funny")

    def test_invalid_segment_type(self):
        script = valid_script()
        script["segments"][2]["type"] = "middle"
        with self.assertRaisesRegex(ValueError, "development"):
            validate_short_script(script, grounded_events(), "dramatic")

    def test_empty_source_event_ids(self):
        script = valid_script()
        script["segments"][0]["source_event_ids"] = []
        with self.assertRaisesRegex(ValueError, "needs source_event_ids"):
            validate_short_script(script, grounded_events(), "funny")

    def test_invalid_source_claim_id(self):
        script = valid_script()
        script["segments"][0]["source_claim_ids"] = ["invented-claim"]
        script["segments"][0]["factual_claims_used"] = ["invented-claim"]
        with self.assertRaisesRegex(ValueError, "not belonging"):
            validate_short_script(script, grounded_events(), "funny")

    def test_claim_not_belonging_to_referenced_event(self):
        events = grounded_events() + [
            {
                "id": "event-2",
                "script_ready": True,
                "unsupported_claims": [],
                "claims": [{"id": "claim-2", "text": "Another fact."}],
            }
        ]
        script = valid_script()
        script["segments"][0]["source_claim_ids"] = ["claim-2"]
        script["segments"][0]["factual_claims_used"] = ["claim-2"]
        with self.assertRaisesRegex(ValueError, "not belonging"):
            validate_short_script(script, events, "dramatic")

    def test_factual_claim_anchor_must_match_source_claims(self):
        script = valid_script()
        script["segments"][0]["factual_claims_used"] = ["other"]
        with self.assertRaisesRegex(ValueError, "must match"):
            validate_short_script(script, grounded_events(), "emotional")

    def test_name_must_appear_in_cited_claim(self):
        events = grounded_events()
        events[0]["claims"].append(
            {"id": "claim-name", "text": "RIN is mentioned."}
        )
        script = valid_script()
        script["segments"][0]["text"] = "RIN thực hiện hành động này."
        with self.assertRaisesRegex(ValueError, "names absent"):
            validate_short_script(script, events, "funny")

    def test_style_enum(self):
        with self.assertRaisesRegex(ValueError, "Style must be"):
            validate_short_script(valid_script(), grounded_events(), "horror")


class ScriptGenerationTests(unittest.TestCase):
    @patch("app.services.short_script_engine.call_text_model")
    def test_valid_bounded_model_selection(self, call_model):
        call_model.return_value = style_selection("emotional")
        result = generate_short_script(reliability_result(), "emotional")
        self.assertEqual(result["renderer_mode"], "bounded_model_style")
        self.assertIsNotNone(result["model_candidate"])
        self.assertEqual(call_model.call_count, 1)

    @patch("app.services.short_script_engine.call_text_model")
    def test_empty_model_output_uses_fallback_without_retry(self, call_model):
        call_model.return_value = {}
        result = generate_short_script(reliability_result(), "emotional")
        self.assertEqual(result["renderer_mode"], "deterministic_fallback")
        self.assertIsNone(result["model_candidate"])
        self.assertEqual(result["segments"], result["deterministic_fallback"]["segments"])
        self.assertEqual(call_model.call_count, 1)

    @patch("app.services.short_script_engine.call_text_model")
    def test_invalid_model_phrase_uses_fallback_without_retry(self, call_model):
        invalid = style_selection("dramatic")
        call_model.return_value = invalid
        result = generate_short_script(reliability_result(), "funny")
        self.assertEqual(result["renderer_mode"], "deterministic_fallback")
        self.assertIn("Invalid style phrase", result["model_error"])
        self.assertEqual(call_model.call_count, 1)


if __name__ == "__main__":
    unittest.main()
