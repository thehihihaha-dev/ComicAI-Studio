import unittest

from app.services.story_reliability import (
    build_story_coverage,
    merge_story_recovery,
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
        self.assertEqual(result["issues"][0]["code"], "missing_non_story_reason")


if __name__ == "__main__":
    unittest.main()
