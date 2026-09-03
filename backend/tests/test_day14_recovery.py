"""Unit tests for Day 14 Phase 2: Deterministic Complementary Panel Recovery Engine.

Verifies:
1. Clean synthesis of residual panels on Page 3 and Page 15 with zero overlap.
2. Rejection of synthesis if distance to existing panels < 30px or intersection risk exists (fail-closed).
3. 10/10 runs determinism (exact identical SHA-256 signatures).
4. Region assignment on Page 3 and Page 15 with 100% assignment (unassigned=0, ambiguous=0).
5. Reading order and zero inversions invariant on recovered pages.
"""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.services.panel_aware_reading_order import (
    order_regions_in_panel,
    projection_constraint_order,
)
from src.pipeline.research.day13_assignment import DeterministicRegionAssigner
from src.pipeline.research.day13_harness import (
    Checkpoint128ExclusionBarrier,
    NormalizedBox,
)
from src.pipeline.research.day14_recovery import ComplementaryPanelSynthesizer


class Day14RecoveryTests(unittest.TestCase):

    def setUp(self):
        self.synthesizer = ComplementaryPanelSynthesizer()
        self.assigner = DeterministicRegionAssigner()

        # Load audit data with barrier
        audit_path = ROOT / "benchmarks" / "day12" / "panel-relation-model-input-audit-12.7.json"
        eval_path = ROOT / "benchmarks" / "day13" / "day13-realistic-track-evaluation.json"
        gt_path = ROOT / "benchmarks" / "day11" / "reader-order-control-11.16.json"

        audit_doc = Checkpoint128ExclusionBarrier.safe_load_json(audit_path)
        eval_doc = Checkpoint128ExclusionBarrier.safe_load_json(eval_path)
        gt_doc = Checkpoint128ExclusionBarrier.safe_load_json(gt_path)

        self.input_pages = {p["page_order"]: p for p in audit_doc["runtime_phase"]["pages"]}
        self.eval_pages = {p["page_order"]: p for p in eval_doc["pages"]}
        self.humans = {p["page_order"]: p["human"] for p in gt_doc["pages"]}

    def test_page_3_and_15_clean_synthesis_no_overlap(self):
        """Page 3 and 15 must generate exactly 1 clean residual panel with zero overlap."""
        for p_num in [3, 15]:
            info = self.input_pages[p_num]
            w, h = info["image_dimensions"]
            eval_p = self.eval_pages[p_num]
            un_ids = set(eval_p["unassigned_region_ids"])

            pans = [
                NormalizedBox(
                    Decimal(str(p["bbox"][0])),
                    Decimal(str(p["bbox"][1])),
                    Decimal(str(p["bbox"][2])),
                    Decimal(str(p["bbox"][3])),
                    p["panel_id"],
                )
                for p in info["realistic_selected_panels"]
            ]
            un_regs = [
                NormalizedBox(
                    Decimal(str(r["bbox"][0])),
                    Decimal(str(r["bbox"][1])),
                    Decimal(str(r["bbox"][2])),
                    Decimal(str(r["bbox"][3])),
                    r["id"],
                )
                for r in info["persisted_logical_regions"]
                if r["id"] in un_ids
            ]

            synths = self.synthesizer.synthesize_clean_residual_panels(pans, un_regs, w, h)
            self.assertEqual(len(synths), 1, f"Expected 1 synthesized panel for Page {p_num}")

            sp = synths[0]
            self.assertTrue(sp.panel_id.startswith("SYNTH_PANEL_"))

            # Overlap check
            for p in pans:
                ox = max(Decimal(0), min(sp.x2, p.x2) - max(sp.x1, p.x1))
                oy = max(Decimal(0), min(sp.y2, p.y2) - max(sp.y1, p.y1))
                self.assertEqual(ox * oy, Decimal(0), f"Synthesized panel overlaps existing panel {p.panel_id}")

            # Enclosure check
            for r in un_regs:
                self.assertTrue(
                    sp.x1 <= r.x1 and sp.y1 <= r.y1 and sp.x2 >= r.x2 and sp.y2 >= r.y2,
                    f"Unassigned region {r.panel_id} not fully enclosed by synthesized panel",
                )

    def test_rejection_on_insufficient_gutter_gap(self):
        """Must reject synthesis if unassigned region is closer than min_gutter_gap (30px)."""
        existing_panels = [
            NormalizedBox(Decimal("0"), Decimal("0"), Decimal("100"), Decimal("50"), "p1")
        ]
        # Region only 15px away vertically (dy = 15 < 30)
        close_regions = [
            NormalizedBox(Decimal("10"), Decimal("65"), Decimal("90"), Decimal("90"), "r1")
        ]
        res = self.synthesizer.synthesize_clean_residual_panels(existing_panels, close_regions, 200, 200)
        self.assertEqual(res, [], "Should reject synthesis when gutter gap < 30px")

    def test_rejection_on_zero_existing_panels(self):
        """Must fail-closed when there are zero existing panels."""
        regions = [
            NormalizedBox(Decimal("10"), Decimal("10"), Decimal("50"), Decimal("50"), "r1")
        ]
        res = self.synthesizer.synthesize_clean_residual_panels([], regions, 200, 200)
        self.assertEqual(res, [], "Should fail-closed when existing_panels is empty")

    def test_determinism_10_runs(self):
        """10 consecutive runs must yield identical SHA-256 signatures."""
        hashes = []
        for _ in range(10):
            info = self.input_pages[3]
            w, h = info["image_dimensions"]
            eval_p = self.eval_pages[3]
            un_ids = set(eval_p["unassigned_region_ids"])

            pans = [
                NormalizedBox(
                    Decimal(str(p["bbox"][0])),
                    Decimal(str(p["bbox"][1])),
                    Decimal(str(p["bbox"][2])),
                    Decimal(str(p["bbox"][3])),
                    p["panel_id"],
                )
                for p in info["realistic_selected_panels"]
            ]
            un_regs = [
                NormalizedBox(
                    Decimal(str(r["bbox"][0])),
                    Decimal(str(r["bbox"][1])),
                    Decimal(str(r["bbox"][2])),
                    Decimal(str(r["bbox"][3])),
                    r["id"],
                )
                for r in info["persisted_logical_regions"]
                if r["id"] in un_ids
            ]

            synths = self.synthesizer.synthesize_clean_residual_panels(pans, un_regs, w, h)
            sig = f"{synths[0].panel_id}_{float(synths[0].x1)}_{float(synths[0].y1)}_{float(synths[0].x2)}_{float(synths[0].y2)}"
            hashes.append(hashlib.sha256(sig.encode("utf-8")).hexdigest())

        self.assertEqual(len(set(hashes)), 1, "Non-deterministic panel synthesis detected!")

    def test_region_assignment_complete_on_recovered_pages(self):
        """Region assignment on recovered Pages 3 and 15 must have 0 unassigned and 0 ambiguous."""
        for p_num in [3, 15]:
            info = self.input_pages[p_num]
            w, h = info["image_dimensions"]
            eval_p = self.eval_pages[p_num]
            un_ids = set(eval_p["unassigned_region_ids"])

            pans = [
                NormalizedBox(
                    Decimal(str(p["bbox"][0])),
                    Decimal(str(p["bbox"][1])),
                    Decimal(str(p["bbox"][2])),
                    Decimal(str(p["bbox"][3])),
                    p["panel_id"],
                )
                for p in info["realistic_selected_panels"]
            ]
            un_regs = [
                NormalizedBox(
                    Decimal(str(r["bbox"][0])),
                    Decimal(str(r["bbox"][1])),
                    Decimal(str(r["bbox"][2])),
                    Decimal(str(r["bbox"][3])),
                    r["id"],
                )
                for r in info["persisted_logical_regions"]
                if r["id"] in un_ids
            ]

            synths = self.synthesizer.synthesize_clean_residual_panels(pans, un_regs, w, h)
            all_pans = pans + synths

            all_regs = [
                NormalizedBox(
                    Decimal(str(r["bbox"][0])),
                    Decimal(str(r["bbox"][1])),
                    Decimal(str(r["bbox"][2])),
                    Decimal(str(r["bbox"][3])),
                    r["id"],
                )
                for r in info["persisted_logical_regions"]
            ]

            ass = self.assigner.assign_regions(all_pans, all_regs)
            human_set = set(self.humans[p_num])

            un_eval = [rid for rid in ass.unassigned_region_ids if rid in human_set]
            amb_eval = [rid for rid in ass.ambiguous_region_ids if rid in human_set]

            self.assertEqual(len(un_eval), 0, f"Page {p_num} still has unassigned regions: {un_eval}")
            self.assertEqual(len(amb_eval), 0, f"Page {p_num} has ambiguous regions: {amb_eval}")

    def test_end_to_end_ordering_exact_with_zero_inversions(self):
        """Recovered Pages 3 and 15 must resolve to EXACT with 0 inversions."""
        def pairs(seq):
            return {(a, b) for i, a in enumerate(seq) for b in seq[i + 1 :]}

        for p_num in [3, 15]:
            info = self.input_pages[p_num]
            w, h = info["image_dimensions"]
            eval_p = self.eval_pages[p_num]
            un_ids = set(eval_p["unassigned_region_ids"])

            pans = [
                NormalizedBox(
                    Decimal(str(p["bbox"][0])),
                    Decimal(str(p["bbox"][1])),
                    Decimal(str(p["bbox"][2])),
                    Decimal(str(p["bbox"][3])),
                    p["panel_id"],
                )
                for p in info["realistic_selected_panels"]
            ]
            un_regs = [
                NormalizedBox(
                    Decimal(str(r["bbox"][0])),
                    Decimal(str(r["bbox"][1])),
                    Decimal(str(r["bbox"][2])),
                    Decimal(str(r["bbox"][3])),
                    r["id"],
                )
                for r in info["persisted_logical_regions"]
                if r["id"] in un_ids
            ]

            synths = self.synthesizer.synthesize_clean_residual_panels(pans, un_regs, w, h)
            all_pans = pans + synths

            all_regs = [
                NormalizedBox(
                    Decimal(str(r["bbox"][0])),
                    Decimal(str(r["bbox"][1])),
                    Decimal(str(r["bbox"][2])),
                    Decimal(str(r["bbox"][3])),
                    r["id"],
                )
                for r in info["persisted_logical_regions"]
            ]

            ass = self.assigner.assign_regions(all_pans, all_regs)
            human_seq = self.humans[p_num]
            human_set = set(human_seq)

            active_ids = {pid for pid, rlist in ass.panel_to_regions.items() if len(rlist) > 0}
            pan_dicts = [
                {"panel_id": p.panel_id, "bbox": [float(p.x1), float(p.y1), float(p.x2), float(p.y2)]}
                for p in all_pans
            ]
            pan_res = projection_constraint_order(pan_dicts, (w, h), active_ids)

            region_dict_map = {
                r.panel_id: {"id": r.panel_id, "bbox": [float(r.x1), float(r.y1), float(r.x2), float(r.y2)]}
                for r in all_regs
            }
            grouped = {
                pid: [region_dict_map[rid] for rid in r_list if rid in human_set]
                for pid, r_list in ass.panel_to_regions.items()
            }
            local_order = {pid: order_regions_in_panel(items) for pid, items in grouped.items()}

            prediction = []
            for pid in pan_res["order"]:
                prediction.extend([rid for rid in local_order[pid]["order"] if rid in human_set])

            hp = pairs(human_seq)
            pp = pairs(prediction)
            inv = hp - pp

            self.assertTrue(pan_res["resolved"], f"Page {p_num} panel order unresolved")
            self.assertEqual(len(inv), 0, f"Page {p_num} generated inversions: {inv}")
            self.assertEqual(prediction, human_seq, f"Page {p_num} prediction mismatch with human order")


if __name__ == "__main__":
    unittest.main()

