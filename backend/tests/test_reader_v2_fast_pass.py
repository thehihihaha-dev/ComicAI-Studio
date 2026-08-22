import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.services.reader_v2_fast_pass import (
    ReaderV2FastPass, ReadingOrderPolicy, fast_pass_fingerprint, logical_crop_box,
    prepare_reading_order, tiered_order,
)


class FakeOCR:
    name = "fake"
    version = "1"
    config = {"languages": ["vi", "en"]}

    def __init__(self, text="TEST"):
        self.text = text
        self.calls = 0

    def read(self, crop):
        self.calls += 1
        return [{"id": 0, "bbox": [[0.0, 0.0], [3.0, 0.0], [3.0, 2.0], [0.0, 2.0]],
                 "text": self.text, "confidence": .99}]


class ReaderV2FastPassTests(unittest.TestCase):
    def test_logical_crop_has_two_percent_padding_and_clips(self):
        self.assertEqual(logical_crop_box([1, 1, 101, 51], (105, 55)), [0, 0, 103, 53])
        self.assertTrue(all(type(value) is int for value in logical_crop_box([1, 1, 5, 5], (10, 10))))

    def test_manga_panel_order_a_c_b(self):
        panels = [{"id": "A", "bbox": [0, 0, 200, 80]}, {"id": "B", "bbox": [0, 100, 90, 180]},
                  {"id": "C", "bbox": [110, 100, 200, 180]}]
        self.assertEqual(tiered_order(panels, ReadingOrderPolicy.MANGA_RTL), ["A", "C", "B"])

    def test_bubbles_same_tier_are_right_to_left(self):
        regions = [{"id": "left", "bbox": [10, 10, 40, 40]}, {"id": "right", "bbox": [60, 12, 90, 42]},
                   {"id": "bottom", "bbox": [30, 80, 60, 110]}]
        result = prepare_reading_order(regions, None)
        self.assertEqual(result["reading_order"], ["right", "left", "bottom"])

    def test_crossing_overlapping_panels_is_ambiguous(self):
        panels = [{"id": 1, "bbox": [0, 0, 60, 60]}, {"id": 2, "bbox": [40, 0, 100, 60]}]
        regions = [{"id": 9, "bbox": [45, 10, 55, 30]}]
        result = prepare_reading_order(regions, panels)
        self.assertIn("crosses_overlapping_panels", result["region_ambiguity"][9])
        self.assertIn("multiple_panel_containment", result["region_ambiguity"][9])

    def test_orphan_region_is_flagged(self):
        result = prepare_reading_order([{"id": 2, "bbox": [80, 80, 90, 90]}], [{"id": 1, "bbox": [0, 0, 50, 50]}])
        self.assertEqual(result["reading_order"], [2])
        self.assertEqual(result["region_ambiguity"][2], ["orphan_region"])

    def test_partial_panel_boundary_crossing_is_not_silently_assigned(self):
        result = prepare_reading_order([{"id": "bubble", "bbox": [40, 10, 70, 30]}],
                                       [{"id": "panel", "bbox": [0, 0, 50, 50]}])
        self.assertEqual(result["region_ambiguity"]["bubble"], ["orphan_region"])

    def test_uneven_panels_remain_tiered_and_deterministic(self):
        panels = [{"id": "top", "bbox": [0, 0, 200, 55]}, {"id": "right", "bbox": [120, 70, 200, 180]},
                  {"id": "left", "bbox": [0, 65, 100, 130]}]
        self.assertEqual(tiered_order(panels, ReadingOrderPolicy.MANGA_RTL), ["top", "right", "left"])

    def test_end_to_end_is_structured_zero_model_call_and_deterministic(self):
        engine = FakeOCR()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.png"; Image.new("RGB", (100, 100), "white").save(path)
            regions = [{"id": 1, "bbox": [10, 10, 50, 30], "type": "dialogue"}]
            result = ReaderV2FastPass(engine).run(str(path), "asset", hashlib.sha256(path.read_bytes()).hexdigest(), regions)
        self.assertEqual(engine.calls, 1)
        self.assertEqual(result["regions"][0]["routing_state"], "ACCEPT_CANDIDATE")
        self.assertEqual(result["stats"]["vlm_calls"], 0)
        self.assertEqual(result["stats"]["ollama_calls"], 0)
        self.assertEqual(result["fingerprint"], fast_pass_fingerprint(result["source_hash"], engine, ReadingOrderPolicy.MANGA_RTL, regions))

    def test_fingerprint_changes_with_panel_geometry(self):
        engine = FakeOCR(); regions = [{"id": 1, "bbox": [10, 10, 20, 20]}]
        first = fast_pass_fingerprint("hash", engine, ReadingOrderPolicy.MANGA_RTL, regions,
                                      panels=[{"id": "p", "bbox": [0, 0, 30, 30]}])
        second = fast_pass_fingerprint("hash", engine, ReadingOrderPolicy.MANGA_RTL, regions,
                                       panels=[{"id": "p", "bbox": [0, 0, 40, 40]}])
        self.assertNotEqual(first, second)


if __name__ == "__main__": unittest.main()
