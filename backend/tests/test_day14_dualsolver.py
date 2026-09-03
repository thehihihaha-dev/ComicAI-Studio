"""Unit tests for Day 14 Phase 3: Dual-Solver for Dark-Gutter Bleed & Conflict De-escalation.

Verifies:
1. InvertedDarkGutterDetector on Page 5 (3 panels detected, zero activation on white-gutter pages).
2. DeterministicConflictDeescalator on Page 1 (clean sub-panels, 100% assignment).
3. solve_advanced_edge_cases unifying recovery across all stuck pages.
4. 10/10 Exact Pages and 0 Inversions across the entire benchmark cohort (50/50 regions, 124/124 pairs).
5. 100% Determinism across 10 runs.
"""
from decimal import Decimal
import hashlib
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
from src.pipeline.research.day14_dualsolver import (
    DeterministicConflictDeescalator,
    InvertedDarkGutterDetector,
    solve_advanced_edge_cases,
)


class Day14DualSolverTests(unittest.TestCase):

    def setUp(self):
        audit_path = ROOT / "benchmarks" / "day12" / "panel-relation-model-input-audit-12.7.json"
        gt_path = ROOT / "benchmarks" / "day11" / "reader-order-control-11.16.json"

        audit_doc = Checkpoint128ExclusionBarrier.safe_load_json(audit_path)
        gt_doc = Checkpoint128ExclusionBarrier.safe_load_json(gt_path)

        self.input_pages = {p["page_order"]: p for p in audit_doc["runtime_phase"]["pages"]}
        self.humans = {p["page_order"]: p["human"] for p in gt_doc["pages"]}
        self.assigner = DeterministicRegionAssigner()

    def test_inverted_dark_gutter_detector_page_5(self):
        """Page 5 dark gutters must be detected cleanly, while white-gutter pages yield []."""
        detector = InvertedDarkGutterDetector()

        # Page 5: Dark full-bleed
        p5_path = ROOT / self.input_pages[5]["source_path"]
        p5_panels = detector.detect_dark_panels(p5_path)
        self.assertEqual(len(p5_panels), 3, "Page 5 should have exactly 3 dark-gutter panels")

        # White-gutter pages must NOT trigger dark gutter detection
        p1_path = ROOT / self.input_pages[1]["source_path"]
        p2_path = ROOT / self.input_pages[2]["source_path"]
        self.assertEqual(detector.detect_dark_panels(p1_path), [])
        self.assertEqual(detector.detect_dark_panels(p2_path), [])

    def test_conflict_deescalator_page_1(self):
        """Page 1 container conflict must de-escalate into clean sub-panels covering all 4 regions."""
        deescalator = DeterministicConflictDeescalator()
        p1_path = ROOT / self.input_pages[1]["source_path"]
        p1_panels = deescalator.deescalate_container(p1_path)

        self.assertGreaterEqual(len(p1_panels), 3, "Page 1 should produce at least 3 sub-panels")

        regs = [
            NormalizedBox(
                Decimal(str(r["bbox"][0])),
                Decimal(str(r["bbox"][1])),
                Decimal(str(r["bbox"][2])),
                Decimal(str(r["bbox"][3])),
                r["id"],
            )
            for r in self.input_pages[1]["persisted_logical_regions"]
        ]
        ass = self.assigner.assign_regions(p1_panels, regs)

        # All 4 regions must be assigned
        self.assertEqual(len(ass.assigned_records), 4)
        self.assertEqual(len(ass.unassigned_region_ids), 0)
        self.assertEqual(len(ass.ambiguous_region_ids), 0)

    def test_full_10_pages_exact_resolution_zero_inversions(self):
        """All 10 benchmark pages must achieve 100% exact resolution with ZERO inversions."""
        def pairs(seq):
            return {(a, b) for i, a in enumerate(seq) for b in seq[i + 1 :]}

        exact_count = 0
        resolved_regions_count = 0
        total_inversions = 0
        total_pairs_count = 0

        for p_num in sorted(self.input_pages.keys()):
            info = self.input_pages[p_num]
            w, h = info["image_dimensions"]
            img_path = ROOT / info["source_path"]

            existing_pans = [
                NormalizedBox(
                    Decimal(str(p["bbox"][0])),
                    Decimal(str(p["bbox"][1])),
                    Decimal(str(p["bbox"][2])),
                    Decimal(str(p["bbox"][3])),
                    p["panel_id"],
                )
                for p in info["realistic_selected_panels"]
            ]
            regs = [
                NormalizedBox(
                    Decimal(str(r["bbox"][0])),
                    Decimal(str(r["bbox"][1])),
                    Decimal(str(r["bbox"][2])),
                    Decimal(str(r["bbox"][3])),
                    r["id"],
                )
                for r in info["persisted_logical_regions"]
            ]

            # Solve edge cases (dark gutters, conflicts, complementary synthesis)
            final_panels = solve_advanced_edge_cases(
                page_order=p_num,
                image_path=img_path,
                existing_panels=existing_pans,
                regions=regs,
                page_width=w,
                page_height=h,
            )

            ass = self.assigner.assign_regions(final_panels, regs)
            human_seq = self.humans[p_num]
            human_set = set(human_seq)

            active_ids = {pid for pid, rlist in ass.panel_to_regions.items() if any(r in human_set for r in rlist)}
            pan_dicts = [
                {"panel_id": p.panel_id, "bbox": [float(p.x1), float(p.y1), float(p.x2), float(p.y2)]}
                for p in final_panels
            ]
            pan_res = projection_constraint_order(pan_dicts, (w, h), active_ids)

            region_dict_map = {
                r.panel_id: {"id": r.panel_id, "bbox": [float(r.x1), float(r.y1), float(r.x2), float(r.y2)]}
                for r in regs
            }
            grouped = {
                pid: [region_dict_map[rid] for rid in r_list if rid in human_set]
                for pid, r_list in ass.panel_to_regions.items()
            }
            local_order = {pid: order_regions_in_panel(items) for pid, items in grouped.items()}

            prediction = []
            if pan_res["resolved"]:
                for pid in pan_res["order"]:
                    prediction.extend([rid for rid in local_order[pid]["order"] if rid in human_set])

            hp = pairs(human_seq)
            pp = pairs(prediction)
            inv = hp - pp

            is_exact = pan_res["resolved"] and (prediction == human_seq)
            if is_exact:
                exact_count += 1
            resolved_regions_count += len(prediction)
            total_inversions += len(inv)
            total_pairs_count += len(hp)

            self.assertTrue(pan_res["resolved"], f"Page {p_num} panel ordering unresolved")
            self.assertEqual(len(inv), 0, f"Page {p_num} produced inversion: {inv}")
            self.assertEqual(prediction, human_seq, f"Page {p_num} prediction mismatch")

        self.assertEqual(exact_count, 10, "Target 10/10 Exact Pages not reached")
        self.assertEqual(resolved_regions_count, 50, "Target 50/50 Resolved Regions not reached")
        self.assertEqual(total_inversions, 0, "Zero Inversion Invariant violated!")
        self.assertEqual(total_pairs_count, 124, "Total population pairs mismatch")

    def test_determinism_10_runs(self):
        """10 consecutive runs across all 10 pages must produce identical SHA-256 signatures."""
        def run_cohort():
            signatures = []
            for p_num in sorted(self.input_pages.keys()):
                info = self.input_pages[p_num]
                w, h = info["image_dimensions"]
                img_path = ROOT / info["source_path"]

                existing_pans = [
                    NormalizedBox(
                        Decimal(str(p["bbox"][0])),
                        Decimal(str(p["bbox"][1])),
                        Decimal(str(p["bbox"][2])),
                        Decimal(str(p["bbox"][3])),
                        p["panel_id"],
                    )
                    for p in info["realistic_selected_panels"]
                ]
                regs = [
                    NormalizedBox(
                        Decimal(str(r["bbox"][0])),
                        Decimal(str(r["bbox"][1])),
                        Decimal(str(r["bbox"][2])),
                        Decimal(str(r["bbox"][3])),
                        r["id"],
                    )
                    for r in info["persisted_logical_regions"]
                ]

                final_panels = solve_advanced_edge_cases(
                    p_num, img_path, existing_pans, regs, w, h
                )
                sig = "_".join(f"{p.panel_id}:{float(p.x1):.1f}:{float(p.y1):.1f}" for p in final_panels)
                signatures.append(sig)
            return hashlib.sha256(";".join(signatures).encode("utf-8")).hexdigest()

        base_hash = run_cohort()
        for _ in range(9):
            self.assertEqual(run_cohort(), base_hash, "Nondeterministic cohort recovery detected!")


if __name__ == "__main__":
    unittest.main()

