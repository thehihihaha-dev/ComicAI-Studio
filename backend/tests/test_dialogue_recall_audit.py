import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dialogue_recall_audit.py"
SPEC = importlib.util.spec_from_file_location("dialogue_recall_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


class DialogueRecallAuditTests(unittest.TestCase):
    def page(self):
        return {
            "filename": "page.jpg",
            "reading_order": "PARTIALLY_CORRECT",
            "important_ocr_blocks": 4,
            "assigned_important_ocr_blocks": 3,
            "ignored_meaningful_blocks": 1,
            "expected_regions": [
                {"audit_id": "a", "classification": "DETECTED_COMPLETE", "text_quality": "COMPLETE", "detected_region_ids": [1]},
                {"audit_id": "b", "classification": "DETECTED_PARTIAL", "text_quality": "GARBLED", "detected_region_ids": [1]},
                {"audit_id": "c", "classification": "OCR_MISSING", "text_quality": "UNREADABLE", "detected_region_ids": []},
                {"audit_id": "d", "classification": "DETECTED_COMPLETE", "text_quality": "COMPLETE", "detected_region_ids": [2, 3]},
            ],
        }

    def test_expected_vs_detected_and_missing_classification(self):
        report = audit.audit_page(self.page())
        self.assertEqual(report["expected_dialogue_regions"], 4)
        self.assertEqual(report["detected_expected_regions"], 3)
        self.assertEqual(report["ocr_missing"], 1)
        self.assertEqual(report["partial_dialogues"], 1)

    def test_merge_and_split_detection(self):
        report = audit.audit_page(self.page())
        self.assertEqual(report["merge_errors"], 1)
        self.assertEqual(report["split_errors"], 1)

    def test_aggregate_recall_metrics(self):
        result = audit.aggregate_audit([self.page()])["aggregate"]
        self.assertEqual(result["bubble_recall"], 0.75)
        self.assertEqual(result["missing_dialogue_rate"], 0.25)
        self.assertEqual(result["ocr_block_coverage"], 0.75)
        self.assertEqual(result["reading_order_errors"], 1)


if __name__ == "__main__":
    unittest.main()
