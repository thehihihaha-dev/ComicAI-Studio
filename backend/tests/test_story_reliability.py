import unittest
from unittest.mock import patch

from app.services.story_reliability import (
    _recovery_prompt,
    build_recovery_slots,
    build_story_coverage,
    merge_story_recovery,
    recover_story_coverage,
    validate_fixed_slot_recovery,
    validate_recovery_result,
)


def story_input():
    return {
        "contract_version": "story_input.v1",
        "project_id": "project-1",
        "status": "ready",
        "pages": [
            {
                "asset_id": "asset-1",
                "page_order": 1,
                "dialogues": [
                    {"region_id": 1, "text_role": "dialogue", "evidence_text": "RIN"},
                    {"region_id": 2, "text_role": "dialogue", "evidence_text": "A fact"},
                    {"region_id": 3, "text_role": "narration", "evidence_text": "More context"},
                    {"region_id": 4, "text_role": "translator_note", "evidence_text": "Note"},
                    {"region_id": 5, "text_role": "game_ui", "evidence_text": "UI"},
                ],
            }
        ],
    }


def grounded():
    source = {"asset_id": "asset-1", "page_order": 1, "region_ids": [2]}
    return {
        "characters": [
            {
                "id": "character-1",
                "name": "RIN",
                "sources": [
                    {"asset_id": "asset-1", "page_order": 1, "region_ids": [1]}
                ],
            }
        ],
        "events": [
            {
                "id": "event-1",
                "claims": [{"id": "claim-1", "sources": [source]}],
            }
        ],
    }


def recovered_event(event_id="recovery-event-1"):
    return {
        "id": event_id,
        "summary": "Recovered narration.",
        "importance": 0.5,
        "emotion": "neutral",
        "story_role": "main_story",
        "claims": [
            {
                "id": f"{event_id}-claim-1",
                "text": "Recovered narration.",
                "claim_type": "fact",
                "sources": [
                    {"asset_id": "asset-1", "page_order": 1, "region_ids": [3]}
                ],
            }
        ],
    }


class StoryCoverageTests(unittest.TestCase):
    def test_eligible_covered_excluded_and_unresolved_regions(self):
        result = build_story_coverage(story_input(), grounded())

        self.assertEqual(result["eligible_regions"], 4)
        self.assertEqual(result["important_regions"], 3)
        self.assertEqual(result["covered_regions"], 1)
        self.assertEqual(result["non_story_relevant_regions"], 1)
        self.assertEqual(result["unresolved_regions"], 1)
        self.assertEqual(result["optional_context_regions"], 1)
        self.assertEqual(result["coverage_score"], 0.6667)
        self.assertEqual(
            result["important_uncovered_regions"][0]["region_id"], 3
        )

    def test_translator_note_is_not_eligible(self):
        result = build_story_coverage(story_input(), grounded())
        listed_ids = {
            item["region_id"]
            for key in ("important_uncovered_regions", "optional_context")
            for item in result[key]
        }
        self.assertNotIn(4, listed_ids)

    def test_explicit_non_story_marking_resolves_region(self):
        marker = [
            {
                "asset_id": "asset-1",
                "page_order": 1,
                "region_id": 3,
                "reason": "Repetition",
            }
        ]
        result = build_story_coverage(story_input(), grounded(), marker)
        self.assertEqual(result["unresolved_regions"], 0)
        self.assertEqual(result["coverage_score"], 1.0)


class StoryRecoveryTests(unittest.TestCase):
    def _uncovered(self, region_id, text="TITLE"):
        return {
            "asset_id": "asset-1",
            "page_order": 1,
            "region_id": region_id,
            "text_role": "narration",
            "category": "primary",
            "evidence_text": text,
        }

    def test_recovery_merge_appends_without_overwriting_valid_event(self):
        original = {
            "project_id": "project-1",
            "characters": [],
            "events": [{"id": "event-1", "summary": "Original"}],
            "main_progression": ["event-1"],
        }
        merged = merge_story_recovery(
            original,
            {
                "events": [recovered_event()],
                "main_progression": ["recovery-event-1"],
            },
        )
        self.assertEqual(merged["events"][0]["summary"], "Original")
        self.assertEqual(len(merged["events"]), 2)
        self.assertEqual(
            merged["main_progression"], ["event-1", "recovery-event-1"]
        )

    def test_recovery_cannot_overwrite_existing_event(self):
        original = {
            "events": [{"id": "event-1"}],
            "characters": [],
            "main_progression": [],
        }
        with self.assertRaisesRegex(ValueError, "cannot overwrite"):
            merge_story_recovery(
                original,
                {"events": [recovered_event("event-1")]},
            )

    def test_missing_recovery_decision_remains_unresolved(self):
        uncovered = [
            {
                "asset_id": "asset-1",
                "page_order": 1,
                "region_id": 3,
            }
        ]
        result = validate_recovery_result({"decisions": []}, uncovered)
        self.assertEqual(result["unresolved"], uncovered)

    def test_missing_non_story_reason_remains_unresolved(self):
        uncovered = [
            {"asset_id": "asset-1", "page_order": 1, "region_id": 3}
        ]
        result = validate_recovery_result(
            {
                "decisions": [
                    {
                        **uncovered[0],
                        "disposition": "non_story_relevant",
                    }
                ]
            },
            uncovered,
        )
        self.assertEqual(result["unresolved"], uncovered)
        self.assertEqual(
            result["issues"][0]["code"], "missing_non_story_reason_code"
        )

    def test_valid_non_story_reason_code_resolves_region(self):
        uncovered = [self._uncovered(3, "TITLE")]
        result = validate_recovery_result(
            {
                "decisions": [
                    {
                        **uncovered[0],
                        "disposition": "non_story_relevant",
                        "reason_code": "standalone_label",
                    }
                ]
            },
            uncovered,
        )
        self.assertEqual(result["unresolved"], [])
        self.assertEqual(
            result["non_story_relevant"][0]["reason_code"],
            "standalone_label",
        )

    def test_unknown_non_story_reason_code_remains_unresolved(self):
        uncovered = [{"asset_id": "asset-1", "page_order": 1, "region_id": 3}]
        result = validate_recovery_result(
            {
                "decisions": [
                    {
                        **uncovered[0],
                        "disposition": "non_story_relevant",
                        "reason_code": "make_coverage_pass",
                    }
                ]
            },
            uncovered,
        )
        self.assertEqual(result["unresolved"], uncovered)
        self.assertEqual(
            result["issues"][0]["code"], "unknown_non_story_reason_code"
        )

    def test_valid_new_event_resolves_region(self):
        uncovered = [{"asset_id": "asset-1", "page_order": 1, "region_id": 3}]
        result = validate_recovery_result(
            {
                "decisions": [
                    {
                        **uncovered[0],
                        "disposition": "new_event",
                        "event": recovered_event(),
                    }
                ]
            },
            uncovered,
        )
        self.assertEqual(result["unresolved"], [])
        self.assertEqual(result["events"][0]["id"], "recovery-event-1")

    def test_missing_event_remains_unresolved(self):
        uncovered = [{"asset_id": "asset-1", "page_order": 1, "region_id": 3}]
        result = validate_recovery_result(
            {"decisions": [{**uncovered[0], "disposition": "new_event"}]},
            uncovered,
        )
        self.assertEqual(result["unresolved"], uncovered)
        self.assertEqual(result["issues"][0]["code"], "missing_recovery_event")

    def test_duplicate_region_decisions_are_both_rejected(self):
        uncovered = [{"asset_id": "asset-1", "page_order": 1, "region_id": 3}]
        decision = {
            **uncovered[0],
            "disposition": "non_story_relevant",
            "reason_code": "repeated_information",
        }
        result = validate_recovery_result(
            {"decisions": [decision, dict(decision)]}, uncovered
        )
        self.assertEqual(result["unresolved"], uncovered)
        self.assertEqual(result["issues"][0]["code"], "duplicate_region_decision")

    def test_unknown_asset_or_page_reference_is_rejected(self):
        uncovered = [{"asset_id": "asset-1", "page_order": 1, "region_id": 3}]
        result = validate_recovery_result(
            {
                "decisions": [
                    {
                        "asset_id": "asset-other",
                        "page_order": 9,
                        "region_id": 3,
                        "disposition": "non_story_relevant",
                        "reason_code": "standalone_label",
                    }
                ]
            },
            uncovered,
        )
        self.assertEqual(result["unresolved"], uncovered)
        self.assertEqual(result["issues"][0]["code"], "unknown_region")

    def test_sentence_like_text_is_rejected_as_standalone_label(self):
        uncovered = [self._uncovered(3, "LET US BE HAPPY TOGETHER!")]
        result = validate_recovery_result(
            {
                "decisions": [
                    {
                        **{key: uncovered[0][key] for key in ("asset_id", "page_order", "region_id")},
                        "disposition": "non_story_relevant",
                        "reason_code": "standalone_label",
                    }
                ]
            },
            uncovered,
        )
        self.assertEqual(result["unresolved"], uncovered)
        self.assertEqual(
            result["issues"][0]["code"], "incompatible_non_story_reason_code"
        )

    def test_short_label_is_compatible_with_standalone_label(self):
        uncovered = [self._uncovered(3, "KAZU-SAN")]
        result = validate_recovery_result(
            {
                "decisions": [
                    {
                        "asset_id": "asset-1", "page_order": 1, "region_id": 3,
                        "disposition": "non_story_relevant",
                        "reason_code": "standalone_label",
                    }
                ]
            },
            uncovered,
        )
        self.assertEqual(result["unresolved"], [])

    def test_repeated_information_requires_grounded_overlap(self):
        matching = [self._uncovered(3, "A fact")]
        valid = validate_recovery_result(
            {"decisions": [{"asset_id": "asset-1", "page_order": 1, "region_id": 3,
                              "disposition": "non_story_relevant",
                              "reason_code": "repeated_information"}]},
            matching,
            grounded_result={"events": [{"claims": [{"text": "A fact"}]}]},
        )
        incompatible = validate_recovery_result(
            {"decisions": [{"asset_id": "asset-1", "page_order": 1, "region_id": 3,
                              "disposition": "non_story_relevant",
                              "reason_code": "repeated_information"}]},
            [self._uncovered(3, "Completely different evidence")],
            grounded_result={"events": [{"claims": [{"text": "A fact"}]}]},
        )
        self.assertEqual(valid["unresolved"], [])
        self.assertEqual(len(incompatible["unresolved"]), 1)

    def test_redundant_context_requires_grounded_overlap(self):
        uncovered = [self._uncovered(3, "More existing context")]
        result = validate_recovery_result(
            {"decisions": [{"asset_id": "asset-1", "page_order": 1, "region_id": 3,
                              "disposition": "non_story_relevant",
                              "reason_code": "redundant_context"}]},
            uncovered,
            grounded_result={"events": [{"claims": [{"text": "Unrelated claim"}]}]},
        )
        self.assertEqual(result["unresolved"], uncovered)

    def test_valid_new_event_survives_grounding_check(self):
        uncovered = [self._uncovered(3, "More context")]
        result = validate_recovery_result(
            {"decisions": [{"asset_id": "asset-1", "page_order": 1, "region_id": 3,
                              "disposition": "new_event", "event": recovered_event()}]},
            uncovered,
            story_input=story_input(),
            grounded_result=grounded(),
        )
        self.assertEqual(result["unresolved"], [])

    def test_new_event_must_cite_the_decided_region(self):
        uncovered = [self._uncovered(6, "Different region")]
        result = validate_recovery_result(
            {"decisions": [{"asset_id": "asset-1", "page_order": 1, "region_id": 6,
                              "disposition": "new_event", "event": recovered_event()}]},
            uncovered,
            story_input=story_input(),
            grounded_result=grounded(),
        )
        self.assertEqual(result["unresolved"], uncovered)
        self.assertEqual(
            result["issues"][0]["code"], "recovery_event_does_not_cover_region"
        )

    @patch("app.services.story_reliability.call_text_model")
    def test_fixed_slot_recovery_uses_one_call(self, model):
        uncovered = [self._uncovered(3, "KAZU-SAN")]
        model.return_value = {
            "slots": [{"slot_id": "slot_1", "decision": "non_story_relevant",
                       "reason_code": "standalone_label"}]
        }
        result = recover_story_coverage(story_input(), grounded(), uncovered)
        self.assertEqual(result["slot_metrics"]["decision_completeness"], 1.0)
        self.assertEqual(result["recovery_path"], "single_fixed_slot_call")
        self.assertEqual(model.call_count, 1)

    @patch("app.services.story_reliability.call_text_model")
    def test_missing_fixed_slots_remain_unresolved_without_retry(self, model):
        uncovered = [self._uncovered(3), self._uncovered(6)]
        model.return_value = {"slots": []}
        result = recover_story_coverage(story_input(), grounded(), uncovered)
        self.assertEqual(len(result["unresolved"]), 2)
        self.assertEqual(result["slot_metrics"]["valid_slots"], 0)
        self.assertEqual(model.call_count, 1)

    def test_continuation_prompt_is_smaller_and_scoped(self):
        all_uncovered = [
            self._uncovered(1, "First region"),
            self._uncovered(2, "Second region"),
            self._uncovered(3, "More context"),
        ]
        missing = [all_uncovered[-1]]
        initial = _recovery_prompt(story_input(), grounded(), all_uncovered)
        continuation = _recovery_prompt(
            story_input(), grounded(), missing, continuation=True
        )
        self.assertLess(len(continuation), len(initial))
        self.assertIn('"region_id":3', continuation)



class FixedSlotRecoveryTests(unittest.TestCase):
    def region(self, region_id=3, text="More context"):
        return {"asset_id": "asset-1", "page_order": 1, "region_id": region_id,
                "text_role": "narration", "category": "primary",
                "evidence_text": text}

    def validate(self, response, regions=None, current=None):
        current = current or grounded()
        slots = build_recovery_slots(regions or [self.region()], current)
        return validate_fixed_slot_recovery(
            response, slots, story_input=story_input(), grounded_result=current
        ), slots

    def test_backend_creates_trusted_deterministic_slots(self):
        first = build_recovery_slots([self.region()], grounded())
        second = build_recovery_slots([self.region()], grounded())
        self.assertEqual(first, second)
        self.assertEqual(first[0]["slot_id"], "slot_1")
        self.assertEqual(first[0]["region_id"], 3)
        self.assertTrue(first[0]["event_id"].startswith("coverage_recovery_p1_r3_"))

    def test_event_id_collision_is_rejected(self):
        slots = build_recovery_slots([self.region()], grounded())
        current = {**grounded(), "events": [*grounded()["events"], {"id": slots[0]["event_id"]}]}
        with self.assertRaisesRegex(ValueError, "collision"):
            build_recovery_slots([self.region()], current)

    def test_model_cannot_supply_backend_owned_identity_or_sources(self):
        for field, value in (
            ("asset_id", "other"), ("page_order", 99), ("region_id", 99),
            ("event_id", "event-1"), ("sources", []),
        ):
            with self.subTest(field=field):
                result, _ = self.validate(
                    {"slots": [{"slot_id": "slot_1", "decision": "new_event",
                                "claims": [{"text": "More context"}], field: value}]}
                )
                self.assertEqual(result["slot_metrics"]["valid_slots"], 0)
                self.assertEqual(result["issues"][0]["code"], "model_supplied_backend_owned_field")

    def test_claim_cannot_redirect_source(self):
        result, _ = self.validate(
            {"slots": [{"slot_id": "slot_1", "decision": "new_event",
                        "claims": [{"text": "More context", "region_id": 99}]}]}
        )
        self.assertEqual(result["slot_metrics"]["valid_slots"], 0)

    def test_exact_known_slot_reconstructs_target_source(self):
        result, slots = self.validate(
            {"slots": [{"slot_id": "slot_1", "decision": "new_event",
                        "claims": [{"text": "More context"}]}]}
        )
        self.assertEqual(result["slot_metrics"]["valid_slots"], 1)
        event = result["events"][0]
        self.assertEqual(event["id"], slots[0]["event_id"])
        self.assertEqual(event["claims"][0]["sources"][0]["region_ids"], [3])

    def test_unknown_slot_is_rejected(self):
        result, _ = self.validate(
            {"slots": [{"slot_id": "invented", "decision": "non_story_relevant",
                        "reason_code": "standalone_label"}]}
        )
        self.assertEqual(result["slot_metrics"]["unknown_slots"], ["invented"])

    def test_duplicate_slot_rejected_but_valid_sibling_survives(self):
        regions = [self.region(3, "TITLE"), self.region(6, "KAZU")]
        response = {"slots": [
            {"slot_id": "slot_1", "decision": "non_story_relevant",
             "reason_code": "standalone_label"},
            {"slot_id": "slot_1", "decision": "non_story_relevant",
             "reason_code": "standalone_label"},
            {"slot_id": "slot_2", "decision": "non_story_relevant",
             "reason_code": "standalone_label"},
        ]}
        result, _ = self.validate(response, regions)
        self.assertEqual(result["slot_metrics"]["duplicate_slots"], ["slot_1"])
        self.assertEqual(result["slot_metrics"]["valid_slots"], 1)

    def test_missing_slot_remains_unresolved(self):
        result, _ = self.validate({"slots": []})
        self.assertEqual(result["slot_metrics"]["missing_slots"], ["slot_1"])
        self.assertEqual(len(result["unresolved"]), 1)

    def test_unsupported_claim_remains_unresolved(self):
        result, _ = self.validate(
            {"slots": [{"slot_id": "slot_1", "decision": "new_event",
                        "claims": [{"text": "Rin destroyed the entire world"}]}]}
        )
        self.assertEqual(result["slot_metrics"]["valid_slots"], 0)
        self.assertEqual(result["slot_metrics"]["semantic_rejections"], 1)

    def test_standalone_and_overlap_guards_are_preserved(self):
        sentence, _ = self.validate(
            {"slots": [{"slot_id": "slot_1", "decision": "non_story_relevant",
                        "reason_code": "standalone_label"}]},
            [self.region(3, "LET US BE HAPPY TOGETHER!")],
        )
        repeated, _ = self.validate(
            {"slots": [{"slot_id": "slot_1", "decision": "non_story_relevant",
                        "reason_code": "repeated_information"}]},
            [self.region(3, "Unrelated evidence")],
        )
        redundant, _ = self.validate(
            {"slots": [{"slot_id": "slot_1", "decision": "non_story_relevant",
                        "reason_code": "redundant_context"}]},
            [self.region(3, "Unrelated evidence")],
        )
        self.assertEqual(sentence["slot_metrics"]["valid_slots"], 0)
        self.assertEqual(repeated["slot_metrics"]["valid_slots"], 0)
        self.assertEqual(redundant["slot_metrics"]["valid_slots"], 0)


if __name__ == "__main__":
    unittest.main()
