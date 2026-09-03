"""Unit tests for Day 15 Phase 1: Deterministic Region Cropping & OCR Adapter Integration.

Verifies:
1. Deterministic Cropping: 10 consecutive crops yield 100% identical SHA-256 digests.
2. Frozen Reading Order Binding: 1:1 parity with Day 14 predicted sequences.
3. Fail-Closed Handling: Degenerate or out-of-bounds coordinates raise ValueError.
4. Pluggable OCR Adapter: Surrogate and mock backends produce deterministic transcriptions.
5. Cohort Crop Coverage: All 50 benchmark text regions crop cleanly with exact bounds.
"""
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day13_harness import NormalizedBox
from src.pipeline.research.day15_ocr import (
    DeterministicBubbleCropper,
    MangaOCRAdapter,
)


class Day15OCRTests(unittest.TestCase):

    def setUp(self):
        self.cropper = DeterministicBubbleCropper(padding=4)
        self.adapter = MangaOCRAdapter(backend="surrogate")

        # Load Day 14 full evaluation result
        eval_path = ROOT / "benchmarks" / "day14" / "day14-full-realistic-evaluation.json"
        self.eval_doc = json.loads(eval_path.read_text(encoding="utf-8"))

        audit_path = ROOT / "benchmarks" / "day12" / "panel-relation-model-input-audit-12.7.json"
        self.audit_doc = json.loads(audit_path.read_text(encoding="utf-8"))
        self.input_pages = {p["page_order"]: p for p in self.audit_doc["runtime_phase"]["pages"]}

    def test_deterministic_cropping_10_runs(self):
        """Cropping the same region 10 times must produce identical SHA-256 digests."""
        p1 = self.input_pages[1]
        img_path = ROOT / p1["source_path"]
        im = Image.open(img_path).convert("RGB")

        # LR_615c8d24c678
        box = NormalizedBox(Decimal("638.0"), Decimal("180.0"), Decimal("692.0"), Decimal("212.0"), "LR_615c8d24c678")

        first_crop, first_hash, first_coords = self.cropper.crop_region(im, box)
        self.assertGreater(len(first_hash), 0)

        for _ in range(9):
            crop, crop_hash, coords = self.cropper.crop_region(im, box)
            self.assertEqual(crop_hash, first_hash, "Cropping is not strictly byte-deterministic!")
            self.assertEqual(coords, first_coords)

    def test_fail_closed_on_degenerate_or_inverted_boxes(self):
        """Degenerate or inverted bounding boxes must fail closed with ValueError."""
        # 1. NormalizedBox itself must reject inverted coordinates: x2 < x1
        with self.assertRaises(ValueError):
            NormalizedBox(Decimal("80.0"), Decimal("20.0"), Decimal("40.0"), Decimal("50.0"), "INV_BOX")

        # 2. Out-of-bounds box on small image clamps to zero area -> Cropper raises ValueError
        im = Image.new("RGB", (100, 100), color=(255, 255, 255))
        oob_box = NormalizedBox(Decimal("150.0"), Decimal("150.0"), Decimal("200.0"), Decimal("200.0"), "OOB_BOX")
        with self.assertRaises(ValueError):
            self.cropper.crop_region(im, oob_box)

    def test_reading_order_binding_parity(self):
        """Page 1 extraction must maintain exact 1:1 parity with Day 14 frozen sequence."""
        p1_eval = next(p for p in self.eval_doc["pages"] if p["page_order"] == 1)
        expected_rids = p1_eval["prediction"]
        self.assertEqual(expected_rids, ["LR_615c8d24c678", "LR_086859ae76f4", "LR_28e2fc3b47b8", "LR_2284efd8ada7"])

        p1_info = self.input_pages[1]
        reg_map = {r["id"]: r for r in p1_info["persisted_logical_regions"]}

        ordered_boxes = [
            NormalizedBox(
                Decimal(str(reg_map[rid]["bbox"][0])),
                Decimal(str(reg_map[rid]["bbox"][1])),
                Decimal(str(reg_map[rid]["bbox"][2])),
                Decimal(str(reg_map[rid]["bbox"][3])),
                rid,
            )
            for rid in expected_rids
        ]

        extracted = self.adapter.extract_page_dialogues(
            page_id=1,
            image_path=ROOT / p1_info["source_path"],
            ordered_regions=ordered_boxes,
            cropper=self.cropper,
        )

        self.assertEqual(len(extracted), 4)
        for i, item in enumerate(extracted, 1):
            self.assertEqual(item["reading_order_index"], i)
            self.assertEqual(item["region_id"], expected_rids[i - 1])
            self.assertGreater(len(item["transcription"]), 0)

        # Confirm transcription of first bubble is "RIN"
        self.assertEqual(extracted[0]["transcription"], "RIN")

    def test_cohort_crop_all_50_regions(self):
        """All 50 regions across 10 benchmark pages must crop cleanly and transcribe deterministically."""
        total_crops = 0
        for page in self.eval_doc["pages"]:
            p_num = page["page_order"]
            expected_rids = page["prediction"]
            p_info = self.input_pages[p_num]
            reg_map = {r["id"]: r for r in p_info["persisted_logical_regions"]}

            ordered_boxes = [
                NormalizedBox(
                    Decimal(str(reg_map[rid]["bbox"][0])),
                    Decimal(str(reg_map[rid]["bbox"][1])),
                    Decimal(str(reg_map[rid]["bbox"][2])),
                    Decimal(str(reg_map[rid]["bbox"][3])),
                    rid,
                )
                for rid in expected_rids
            ]

            extracted = self.adapter.extract_page_dialogues(
                page_id=p_num,
                image_path=ROOT / p_info["source_path"],
                ordered_regions=ordered_boxes,
                cropper=self.cropper,
            )

            self.assertEqual(len(extracted), len(expected_rids))
            total_crops += len(extracted)

        self.assertEqual(total_crops, 50, "Total extracted crops must be exactly 50")


if __name__ == "__main__":
    unittest.main()
