import unittest
from collections import Counter

from app.services.dialogue_structure_recovery import (
    recover_ocr_empty_candidate,
    split_merged_regions,
    valid_split,
)


def block(left, top, right, bottom):
    return {"text": "x", "box": [[left, top], [right, top], [right, bottom], [left, bottom]]}


class RegionSplitTests(unittest.TestCase):
    def test_obvious_distant_clusters_split_deterministically(self):
        result = {"regions": [{"id": 4, "block_ids": [0, 1, 2]}], "reading_order": [4]}
        blocks = [block(0, 0, 40, 20), block(5, 25, 45, 45), block(400, 0, 450, 20)]

        first = split_merged_regions(result, blocks)
        second = split_merged_regions(result, blocks)

        self.assertEqual(first, second)
        self.assertEqual([region["block_ids"] for region in first["regions"]], [[0, 1], [2]])
        self.assertEqual(first["reading_order"], [4, 5])
        self.assertEqual(first["regions"][1]["region_source"], "geometry_split")
        self.assertEqual(first["regions"][1]["split_from_region_ids"], [4])

    def test_nearby_blocks_remain_in_same_region(self):
        result = {"regions": [{"id": 1, "block_ids": [0, 1]}], "reading_order": [1]}
        recovered = split_merged_regions(result, [block(0, 0, 50, 20), block(5, 30, 55, 50)])
        self.assertEqual(len(recovered["regions"]), 1)
        self.assertEqual(recovered["regions"][0]["region_source"], "original_layout")

    def test_all_blocks_preserved_exactly_once_across_cross_region_reassignment(self):
        result = {
            "regions": [{"id": 1, "block_ids": [0]}, {"id": 2, "block_ids": [1, 2]}],
            "reading_order": [1, 2],
        }
        blocks = [block(0, 0, 30, 20), block(300, 0, 330, 20), block(10, 22, 40, 42)]
        recovered = split_merged_regions(result, blocks)
        after = [item for region in recovered["regions"] for item in region["block_ids"]]
        self.assertEqual(Counter(after), Counter([0, 1, 2]))
        joined = next(region for region in recovered["regions"] if set(region["block_ids"]) == {0, 2})
        self.assertEqual(joined["split_from_region_ids"], [1, 2])

    def test_duplicate_or_lost_split_is_rejected(self):
        self.assertFalse(valid_split([0, 1], [[0], [0]]))
        self.assertFalse(valid_split([0, 1], [[0]]))

    def test_ambiguous_missing_geometry_stays_unsplit(self):
        result = {"regions": [{"id": 3, "block_ids": [0, 1]}], "reading_order": [3]}
        recovered = split_merged_regions(result, [{"text": "a"}, {"text": "b"}])
        self.assertEqual(recovered, result)


class OcrEmptyRecoveryTests(unittest.TestCase):
    def test_local_ocr_is_used_first_and_provenance_retained(self):
        calls = []

        def local(_path, _bbox):
            calls.append("local")
            return {"text": "Hãy", "confidence": 0.95}

        def vision(_path, _bbox):
            calls.append("vision")
            return {"text": "invented", "confidence": 1.0}

        result = recover_ocr_empty_candidate("page.jpg", [1, 2, 30, 40], local, vision)
        self.assertEqual(calls, ["local"])
        self.assertEqual(result["text"], "Hãy")
        self.assertEqual(result["region_source"], "local_ocr_recovery")
        self.assertFalse(result["needs_review"])

    def test_small_crop_fallback_runs_once_and_low_confidence_requires_review(self):
        calls = []
        result = recover_ocr_empty_candidate(
            "page.jpg",
            [1, 2, 30, 40],
            lambda *_: None,
            lambda *_: calls.append("vision") or {"text": "Hãy", "confidence": 0.62},
        )
        self.assertEqual(calls, ["vision"])
        self.assertEqual(result["region_source"], "vision_ocr_recovery")
        self.assertTrue(result["needs_review"])

    def test_failed_candidate_remains_unresolved(self):
        result = recover_ocr_empty_candidate("page.jpg", [1, 2, 30, 40], lambda *_: None)
        self.assertFalse(result["resolved"])
        self.assertEqual(result["region_source"], "unresolved_visual_candidate")


if __name__ == "__main__":
    unittest.main()
