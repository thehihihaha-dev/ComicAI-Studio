import unittest
from unittest.mock import patch

from app.services.dialogue_corrector import (
    apply_dialogue_decisions,
    apply_verified_ground_truth,
    calculate_correction_score,
    has_risky_text_change,
    recover_uncertain_dialogues,
    validate_corrected_dialogues,
)


class DialogueValidationTests(unittest.TestCase):
    def setUp(self):
        self.original = [
            {
                "order": 1,
                "region_id": 7,
                "raw_text": "NGUYỆN YẾU",
                "block_ids": [0],
            }
        ]
        self.corrected = [
            {
                "order": 1,
                "region_id": 7,
                "raw_text": "NGUYỆN YẾU",
                "clean_text": "NGUYỆN YÊU",
                "confidence": 0.95,
                "needs_review": False,
            }
        ]

    def test_accepts_structurally_valid_correction(self):
        result = validate_corrected_dialogues(self.original, self.corrected)
        self.assertTrue(result["is_valid"])

    def test_rejects_changed_raw_text(self):
        self.corrected[0]["raw_text"] = "CHANGED"
        result = validate_corrected_dialogues(self.original, self.corrected)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["raw_text_mismatches"], [7])

    def test_rejects_duplicate_region(self):
        self.corrected.append(dict(self.corrected[0]))
        result = validate_corrected_dialogues(self.original, self.corrected)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["duplicate_region_ids"], [7])

    def test_rejects_invalid_confidence(self):
        self.corrected[0]["confidence"] = 1.5
        result = validate_corrected_dialogues(self.original, self.corrected)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["invalid_confidence_region_ids"], [7])


class DialogueDecisionTests(unittest.TestCase):
    def test_ground_truth_wins_after_pipeline_rerun(self):
        result = apply_verified_ground_truth(
            [
                {
                    "region_id": 2,
                    "clean_text": "NGUYỆN YẾU",
                    "decision": "auto_recovered",
                    "needs_review": True,
                }
            ],
            {2: "NGUYỆN YÊU"},
        )

        self.assertEqual(result[0]["clean_text"], "NGUYỆN YÊU")
        self.assertEqual(result[0]["verified_text"], "NGUYỆN YÊU")
        self.assertEqual(result[0]["decision"], "verified")
        self.assertFalse(result[0]["needs_review"])

    def test_risky_change_detects_single_word_change_in_short_text(self):
        self.assertTrue(has_risky_text_change("NGUYỆN YẾU", "NGUYỆN YÊU"))

    def test_safe_unchanged_dialogue_is_auto_accepted(self):
        scored = calculate_correction_score(
            [
                {
                    "order": 1,
                    "region_id": 1,
                    "raw_text": "XIN CHÀO",
                    "block_ids": [0],
                }
            ],
            [
                {
                    "order": 1,
                    "region_id": 1,
                    "raw_text": "XIN CHÀO",
                    "clean_text": "XIN CHÀO",
                    "confidence": 0.99,
                    "needs_review": False,
                }
            ],
            [{"confidence": 0.99}],
        )
        decided = apply_dialogue_decisions(scored)
        self.assertEqual(decided[0]["decision"], "auto_accepted")

    @patch("app.services.dialogue_corrector.recover_dialogue")
    def test_recovery_promotes_recovered_text_to_clean_text(self, recover):
        recover.return_value = {
            "region_id": 1,
            "recovered_text": "CHO DÙ",
            "confidence": 0.96,
            "still_uncertain": False,
            "reason": "Confirmed from image",
        }
        result = recover_uncertain_dialogues(
            "page.jpg",
            [
                {
                    "order": 1,
                    "region_id": 1,
                    "raw_text": "CHỜ DÙ",
                    "clean_text": "CHỜ DÙ",
                    "decision": "needs_recovery",
                }
            ],
        )
        self.assertEqual(result[0]["clean_text"], "CHO DÙ")
        self.assertEqual(result[0]["initial_clean_text"], "CHỜ DÙ")
        self.assertEqual(result[0]["decision"], "auto_recovered")

    @patch("app.services.dialogue_corrector.recover_dialogue")
    def test_recovery_rejects_wrong_region_id(self, recover):
        recover.return_value = {
            "region_id": 999,
            "recovered_text": "INVENTED",
            "confidence": 1.0,
            "still_uncertain": False,
        }
        result = recover_uncertain_dialogues(
            "page.jpg",
            [
                {
                    "region_id": 1,
                    "clean_text": "ORIGINAL",
                    "decision": "needs_recovery",
                }
            ],
        )
        self.assertEqual(result[0]["decision"], "needs_review")
        self.assertEqual(result[0]["recovery_confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
