"""Deterministic unit test suite for Day 13 Region-to-Panel Assignment Engine.

Verifies:
a. Region strictly contained in 1 Panel -> 100% assigned (ASSIGNED_CONTAINED).
b. Region crossing panel boundary with clear majority in 1 Panel -> ASSIGNED_MAJORITY.
c. Region on the boundary between 2 panels with equal or close split -> AMBIGUOUS (fail-closed).
d. Region completely outside all panels -> UNASSIGNED (no centroid distance heuristic).
e. 10/10 runs with permuted input lists produce identical raw-byte SHA-256 of AssignmentResult.
f. Zero Ground Truth leakage enforcement (GroundTruthLeakageError).
g. Input mutation protection.
h. Exact Decimal / Fraction arithmetic in geometric helpers.
"""
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day13_assignment import (
    AssignmentResult,
    DeterministicRegionAssigner,
    exact_box_area,
    exact_coverage_ratio,
    exact_intersection_area,
)
from src.pipeline.research.day13_harness import (
    GroundTruthLeakageError,
    NormalizedBox,
)


class Day13AssignmentTests(unittest.TestCase):

    def setUp(self):
        self.assigner = DeterministicRegionAssigner(
            min_majority_ratio=Fraction(1, 2),  # > 50%
            ambiguity_margin=Fraction(1, 10),    # > 10%
        )

    def test_case_a_region_completely_inside_single_panel(self):
        """Scenario A: Region completely contained in 1 panel -> 100% ASSIGNED_CONTAINED."""
        panels = [
            NormalizedBox(Decimal(0), Decimal(0), Decimal(100), Decimal(50), "panel_top"),
            NormalizedBox(Decimal(0), Decimal(50), Decimal(100), Decimal(100), "panel_bottom"),
        ]
        # Region strictly inside panel_top
        regions = [
            NormalizedBox(Decimal(10), Decimal(10), Decimal(30), Decimal(30), "reg_1"),
            NormalizedBox(Decimal(60), Decimal(60), Decimal(80), Decimal(80), "reg_2"),
        ]

        result = self.assigner.assign_regions(panels, regions)

        self.assertEqual(result.panel_to_regions["panel_top"], ["reg_1"])
        self.assertEqual(result.panel_to_regions["panel_bottom"], ["reg_2"])
        self.assertEqual(result.ambiguous_region_ids, [])
        self.assertEqual(result.unassigned_region_ids, [])

        rec_1 = next(r for r in result.assigned_records if r["region_id"] == "reg_1")
        self.assertEqual(rec_1["status"], "ASSIGNED_CONTAINED")
        self.assertEqual(rec_1["assigned_panel_id"], "panel_top")
        self.assertEqual(rec_1["containment_ratio"], "1")

    def test_case_b_region_crossing_border_with_clear_majority(self):
        """Scenario B: Region crosses border but has overwhelming majority in 1 panel -> ASSIGNED_MAJORITY."""
        panels = [
            NormalizedBox(Decimal(0), Decimal(0), Decimal(100), Decimal(50), "panel_top"),
            NormalizedBox(Decimal(0), Decimal(50), Decimal(100), Decimal(100), "panel_bottom"),
        ]
        # Region from y=10 to y=60 (height=50, width=20, area=1000):
        # In panel_top (y 10 to 50): height 40, area = 40 * 20 = 800 (80%)
        # In panel_bottom (y 50 to 60): height 10, area = 10 * 20 = 200 (20%)
        # Majority = 80% > 50%, Margin = 80% - 20% = 60% > 10%
        regions = [
            NormalizedBox(Decimal(20), Decimal(10), Decimal(40), Decimal(60), "reg_cross_majority"),
        ]

        result = self.assigner.assign_regions(panels, regions)

        self.assertEqual(result.panel_to_regions["panel_top"], ["reg_cross_majority"])
        self.assertEqual(result.panel_to_regions["panel_bottom"], [])
        self.assertEqual(result.ambiguous_region_ids, [])
        self.assertEqual(result.unassigned_region_ids, [])

        rec = result.assigned_records[0]
        self.assertEqual(rec["status"], "ASSIGNED_MAJORITY")
        self.assertEqual(rec["assigned_panel_id"], "panel_top")
        self.assertEqual(rec["containment_ratio"], "4/5")
        self.assertEqual(rec["margin"], "3/5")

    def test_case_c_region_boundary_dispute_ambiguous(self):
        """Scenario C: Region split 50/50 or difference within ambiguity margin -> AMBIGUOUS."""
        panels = [
            NormalizedBox(Decimal(0), Decimal(0), Decimal(100), Decimal(50), "panel_top"),
            NormalizedBox(Decimal(0), Decimal(50), Decimal(100), Decimal(100), "panel_bottom"),
        ]
        # Region 1: Exact 50/50 split across boundary at y=50 (y=40 to y=60, center exactly at 50)
        # Region 2: 52/48 split (height 100, y=0 to y=100 with boundary at y=52, margin=4% < 10%)
        regions = [
            NormalizedBox(Decimal(10), Decimal(40), Decimal(30), Decimal(60), "reg_50_50"),
            NormalizedBox(Decimal(50), Decimal(2), Decimal(70), Decimal(102), "reg_close_margin"),
        ]

        result = self.assigner.assign_regions(panels, regions)

        self.assertEqual(result.panel_to_regions["panel_top"], [])
        self.assertEqual(result.panel_to_regions["panel_bottom"], [])
        self.assertEqual(sorted(result.ambiguous_region_ids), ["reg_50_50", "reg_close_margin"])
        self.assertEqual(result.unassigned_region_ids, [])

        rec_50 = next(r for r in result.ambiguous_details if r["region_id"] == "reg_50_50")
        self.assertEqual(rec_50["status"], "AMBIGUOUS")
        self.assertEqual(rec_50["decision_reason"], "INSUFFICIENT_MAJORITY_RATIO")

    def test_case_d_region_outside_all_panels_unassigned(self):
        """Scenario D: Region outside all panels -> UNASSIGNED (no centroid guessing)."""
        panels = [
            NormalizedBox(Decimal(20), Decimal(20), Decimal(80), Decimal(80), "panel_center"),
        ]
        # Region located in margin/gutter at [0, 0, 15, 15] with zero overlap
        regions = [
            NormalizedBox(Decimal(0), Decimal(0), Decimal(15), Decimal(15), "reg_margin"),
        ]

        result = self.assigner.assign_regions(panels, regions)

        self.assertEqual(result.panel_to_regions["panel_center"], [])
        self.assertEqual(result.ambiguous_region_ids, [])
        self.assertEqual(result.unassigned_region_ids, ["reg_margin"])

        rec = result.unassigned_details[0]
        self.assertEqual(rec["status"], "UNASSIGNED")
        self.assertEqual(rec["decision_reason"], "NO_INTERSECTING_PANELS")

    def test_case_e_ten_out_of_ten_runs_determinism_under_permutation(self):
        """Scenario E: 10/10 runs on identical dataset with permuted input lists produce identical SHA-256."""
        panels = [
            NormalizedBox(Decimal(0), Decimal(0), Decimal(50), Decimal(50), "p1"),
            NormalizedBox(Decimal(50), Decimal(0), Decimal(100), Decimal(50), "p2"),
            NormalizedBox(Decimal(0), Decimal(50), Decimal(50), Decimal(100), "p3"),
            NormalizedBox(Decimal(50), Decimal(50), Decimal(100), Decimal(100), "p4"),
        ]
        regions = [
            NormalizedBox(Decimal(5), Decimal(5), Decimal(25), Decimal(25), "r_contained_p1"),
            NormalizedBox(Decimal(40), Decimal(10), Decimal(70), Decimal(30), "r_majority_p2"),  # 10 to 50 in p1 (10px), 50 to 70 in p2 (20px)
            NormalizedBox(Decimal(20), Decimal(40), Decimal(30), Decimal(60), "r_ambiguous_p1_p3"),  # 50/50 split at y=50
            NormalizedBox(Decimal(90), Decimal(90), Decimal(95), Decimal(95), "r_contained_p4"),
            NormalizedBox(Decimal(200), Decimal(200), Decimal(220), Decimal(220), "r_unassigned"),
        ]

        signatures = []
        for i in range(10):
            # Deterministically permute order using seed derived from run index
            perm_panels = list(panels)
            perm_regions = list(regions)
            rng = random.Random(i * 1337)
            rng.shuffle(perm_panels)
            rng.shuffle(perm_regions)

            res = self.assigner.assign_regions(perm_panels, perm_regions)
            signatures.append(res.assignment_sha256)

        self.assertEqual(len(set(signatures)), 1, f"Determinism violated across runs! {set(signatures)}")
        self.assertEqual(len(signatures[0]), 64)

    def test_ground_truth_leakage_rejection(self):
        """Passing forbidden GT keys in dictionary inputs must raise GroundTruthLeakageError."""
        panels = [{"panel_id": "p1", "bbox": [0, 0, 100, 100]}]
        leaked_regions = [{"panel_id": "r1", "bbox": [10, 10, 20, 20], "reading_order": [1]}]

        with self.assertRaises(GroundTruthLeakageError):
            self.assigner.assign_regions(panels, leaked_regions)

    def test_mutation_protection(self):
        """Mutating input lists after passing must not mutate or affect internal processing."""
        raw_panels = [{"panel_id": "p1", "bbox": [0, 0, 100, 100]}]
        raw_regions = [{"panel_id": "r1", "bbox": [10, 10, 20, 20]}]

        res = self.assigner.assign_regions(raw_panels, raw_regions)
        self.assertEqual(res.panel_to_regions["p1"], ["r1"])

        # Mutate raw input
        raw_panels[0]["bbox"][0] = 999
        raw_regions.append({"panel_id": "r_injected", "bbox": [0, 0, 10, 10]})

        # Prior result must remain completely valid
        self.assertEqual(res.summary["total_regions"], 1)
        self.assertEqual(res.panel_to_regions["p1"], ["r1"])

    def test_exact_geometry_helpers(self):
        """Test exact intersection and coverage helpers without floating point error."""
        b1 = NormalizedBox(Decimal("0.1"), Decimal("0.2"), Decimal("10.5"), Decimal("20.4"), "b1")
        b2 = NormalizedBox(Decimal("5.0"), Decimal("10.0"), Decimal("15.0"), Decimal("25.0"), "b2")

        area1 = exact_box_area(b1)
        # width = 10.4, height = 20.2 => area = 210.08
        self.assertEqual(area1, Decimal("210.08"))

        # x overlap: [5.0, 10.5] => width = 5.5
        # y overlap: [10.0, 20.4] => height = 10.4
        # inter area = 5.5 * 10.4 = 57.2
        inter = exact_intersection_area(b1, b2)
        self.assertEqual(inter, Decimal("57.2"))

        ratio = exact_coverage_ratio(b1, b2)
        # 57.2 / 210.08 = 5720 / 21008 = 715 / 2626
        expected_ratio = Fraction(Decimal("57.2")) / Fraction(Decimal("210.08"))
        self.assertEqual(ratio, expected_ratio)


if __name__ == "__main__":
    unittest.main()

