import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from reader_benchmark_lib import (  # noqa: E402
    SCHEMA_VERSION, assert_unchanged, error_rate, match_regions, normalize_text,
    validate_artifact, evaluation_normalize_text, edit_operations,
    confidence_analysis_bucket, classify_errors,
)


class ReaderBenchmarkTests(unittest.TestCase):
    def test_normalization_is_unicode_and_whitespace_only(self):
        self.assertEqual(normalize_text("  A\n  e\u0301  "), "A é")
        self.assertNotEqual(normalize_text("ĐI"), normalize_text("đi"))

    def test_cer_and_wer(self):
        self.assertAlmostEqual(error_rate("abc", "axc"), 1 / 3)
        self.assertAlmostEqual(error_rate("xin chào bạn", "xin chào", words=True), 1 / 3)
        self.assertEqual(error_rate("", ""), 0.0)
        self.assertIsNone(error_rate("", "x"))

    def test_geometry_one_to_one(self):
        result = match_regions([{"id": "t", "bbox": [0, 0, 10, 10]}],
                               [{"id": "c", "bbox": [1, 1, 9, 9]}])
        self.assertEqual(result["matched_trusted_regions"], 1)
        self.assertEqual(len(result["one_to_one_matches"]), 1)

    def test_one_candidate_covering_two_regions_is_merge(self):
        trusted = [{"id": "a", "bbox": [0, 0, 10, 10]},
                   {"id": "b", "bbox": [10, 0, 20, 10]}]
        result = match_regions(trusted, [{"id": "wide", "bbox": [0, 0, 20, 10]}])
        self.assertEqual(result["merged_region_errors"],
                         [{"candidate_id": "wide", "trusted_ids": ["a", "b"]}])
        self.assertEqual(result["one_to_one_matches"], [])

    def test_multiple_candidates_covering_one_region_is_split(self):
        candidates = [{"id": "left", "bbox": [0, 0, 5, 10]},
                      {"id": "right", "bbox": [5, 0, 10, 10]}]
        result = match_regions([{"id": "whole", "bbox": [0, 0, 10, 10]}], candidates)
        self.assertEqual(result["over_split_errors"],
                         [{"trusted_id": "whole", "candidate_ids": ["left", "right"]}])

    def test_artifact_schema_and_immutable_guard(self):
        artifact = {"schema_version": SCHEMA_VERSION, "checkpoint": "11.3",
                    "artifact_kind": "control", "status": "completed"}
        validate_artifact(artifact, "control")
        with self.assertRaises(ValueError):
            validate_artifact({**artifact, "checkpoint": "11.2"}, "control")
        assert_unchanged({"ocr": [1]}, {"ocr": [1]})
        with self.assertRaises(RuntimeError):
            assert_unchanged({"ocr": [1]}, {"ocr": [2]})

    def test_11_4_normalized_metrics_and_edit_operations(self):
        self.assertEqual(evaluation_normalize_text(" TÔI\nĐI "), "tôi đi")
        self.assertEqual(edit_operations("abc", "axcd"),
                         {"insertions": 1, "deletions": 0, "substitutions": 1})

    def test_11_4_error_taxonomy_and_confidence_buckets(self):
        self.assertIn("DIACRITIC_ERROR", classify_errors("Tôi", "Toi"))
        self.assertIn("PUNCTUATION_ERROR", classify_errors("Đi!", "Đi"))
        self.assertIn("LANGUAGE_CONFUSION", classify_errors("Tôi", "新"))
        self.assertEqual(classify_errors("abc", ""), ["MISSING_REGION"])
        self.assertEqual(confidence_analysis_bucket(0.95), "0.95-1.00")


if __name__ == "__main__":
    unittest.main()
