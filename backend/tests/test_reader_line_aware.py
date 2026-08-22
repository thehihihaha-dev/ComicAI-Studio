import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from reader_line_aware import cache_identity, choose_decision, delta_class, order_lines, padded_box, reconstruct  # noqa: E402


class ReaderLineAwareTests(unittest.TestCase):
    def test_padding_and_bounds(self):
        self.assertEqual(padded_box([1, 2, 11, 12], .2, (12, 13)), [0, 0, 12, 13])
        self.assertEqual(padded_box([2, 2, 8, 8], 0, (10, 10)), [2, 2, 8, 8])

    def test_line_order_is_top_to_bottom_then_left_to_right(self):
        lines = [{"id": "c", "bbox": [20, 20, 30, 30], "text": "C"},
                 {"id": "b", "bbox": [20, 0, 30, 10], "text": "B"},
                 {"id": "a", "bbox": [0, 0, 10, 10], "text": "A"}]
        self.assertEqual([x["id"] for x in order_lines(lines)], ["a", "b", "c"])
        self.assertEqual(reconstruct(lines), "A B C")

    def test_cache_identity_is_stable_and_mode_sensitive(self):
        one = cache_identity("hash", [1, 2, 3, 4], .02, "1", "mode-b", "rgb")
        self.assertEqual(one, cache_identity("hash", [1, 2, 3, 4], .02, "1", "mode-b", "rgb"))
        self.assertNotEqual(one, cache_identity("hash", [1, 2, 3, 4], .05, "1", "mode-b", "rgb"))
        self.assertNotEqual(one, cache_identity("hash", [1, 2, 3, 4], .02, "1", "mode-c", "rgb"))

    def test_per_sample_regression_classification(self):
        self.assertEqual(delta_class(.5, .4), "IMPROVED")
        self.assertEqual(delta_class(.5, .5), "UNCHANGED")
        self.assertEqual(delta_class(.5, .6), "REGRESSED")

    def test_decision_requires_line_mode_to_improve_over_logical_crop(self):
        deltas = {"IMPROVED": 18, "UNCHANGED": 2}
        self.assertEqual(choose_decision(.82, .11, .126, deltas, deltas),
                         "B. LOGICAL-REGION CROP HELPS, LINE-AWARE DOES NOT")
        self.assertEqual(choose_decision(.82, .20, .10, deltas, deltas),
                         "A. LINE-AWARE RECONSTRUCTION CLEARLY HELPS")


if __name__ == "__main__": unittest.main()
