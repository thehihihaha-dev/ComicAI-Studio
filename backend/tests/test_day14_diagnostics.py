"""Unit tests for Day 14 Phase 1: Diagnostic Audit of Missing Panel Coverage.

Verifies:
1. Spatial profiling of all 18 unassigned regions across Pages 1, 3, 5, 15.
2. Root cause distribution (8 BORDERLESS_BACKGROUND_PANEL, 10 UNDER_SEGMENTED_PANEL, 0 OUTSIDE_GUTTER_TEXT).
3. Zero overlap conflict of Minimum Enclosing Bounding Box on Pages 3 and 15.
4. Zero Ground Truth leakage (`gt_runtime_features = []`).
5. 100% Determinism of diagnostic SHA-256 signatures.
"""
from decimal import Decimal
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day14_diagnostics import (
    Day14DiagnosticAuditor,
    compute_box_distance_and_overlap,
)


class Day14DiagnosticsTests(unittest.TestCase):

    def setUp(self):
        self.auditor = Day14DiagnosticAuditor(ROOT)

    def test_box_distance_and_overlap_exact_arithmetic(self):
        """Test exact Decimal distance and overlap calculations."""
        # Disjoint boxes separated vertically by 10 units
        b1 = [Decimal("0"), Decimal("0"), Decimal("100"), Decimal("40")]
        b2 = [Decimal("0"), Decimal("50"), Decimal("100"), Decimal("90")]
        dist, dx, dy, overlap = compute_box_distance_and_overlap(b1, b2)
        self.assertEqual(dx, Decimal("0"))
        self.assertEqual(dy, Decimal("10"))
        self.assertEqual(dist, Decimal("10"))
        self.assertEqual(overlap, Decimal("0"))

        # Overlapping boxes
        b3 = [Decimal("0"), Decimal("0"), Decimal("50"), Decimal("50")]
        b4 = [Decimal("40"), Decimal("40"), Decimal("80"), Decimal("80")]
        dist, dx, dy, overlap = compute_box_distance_and_overlap(b3, b4)
        self.assertEqual(dist, Decimal("0"))
        self.assertEqual(overlap, Decimal("100"))  # 10 x 10

    def test_unassigned_counts_and_root_cause_distribution(self):
        """Verify profiling accurately catches all 18 unassigned regions and classifies root causes."""
        result = self.auditor.run_audit()

        self.assertEqual(result["analyzed_pages"], [1, 3, 5, 15])
        self.assertEqual(result["total_unassigned_regions"], 18)

        dist = result["root_cause_distribution"]
        self.assertEqual(dist["BORDERLESS_BACKGROUND_PANEL"], 8)  # Page 5
        self.assertEqual(dist["UNDER_SEGMENTED_PANEL"], 10)       # Pages 1, 3, 15
        self.assertEqual(dist["OUTSIDE_GUTTER_TEXT"], 0)

        # Check page breakdown
        by_page = {p["page_order"]: p for p in result["pages"]}
        self.assertEqual(by_page[1]["unassigned_count"], 4)
        self.assertEqual(by_page[3]["unassigned_count"], 3)
        self.assertEqual(by_page[5]["unassigned_count"], 8)
        self.assertEqual(by_page[15]["unassigned_count"], 3)

    def test_enclosing_box_simulation_conflict_free_on_pages_3_and_15(self):
        """Pages 3 and 15 must have cleanly separated enclosing boxes with 0 overlap conflict."""
        result = self.auditor.run_audit()
        by_page = {p["page_order"]: p for p in result["pages"]}

        sim3 = by_page[3]["simulation"]
        self.assertFalse(sim3["has_geometric_conflict"])
        self.assertEqual(sim3["overlap_conflicts"], [])
        self.assertEqual(sim3["synthesis_feasibility"], "CLEAN_COMPLEMENTARY_SEPARATION")
        self.assertAlmostEqual(sim3["vertical_gap_to_nearest_panel"], 55.0, places=1)

        sim15 = by_page[15]["simulation"]
        self.assertFalse(sim15["has_geometric_conflict"])
        self.assertEqual(sim15["overlap_conflicts"], [])
        self.assertEqual(sim15["synthesis_feasibility"], "CLEAN_COMPLEMENTARY_SEPARATION")
        self.assertAlmostEqual(sim15["vertical_gap_to_nearest_panel"], 75.0, places=1)

        # Pages 1 and 5 have 0 existing panels
        sim1 = by_page[1]["simulation"]
        self.assertEqual(sim1["synthesis_feasibility"], "ZERO_EXISTING_PANELS_FULL_SYNTHESIS_NEEDED")
        sim5 = by_page[5]["simulation"]
        self.assertEqual(sim5["synthesis_feasibility"], "ZERO_EXISTING_PANELS_FULL_SYNTHESIS_NEEDED")

    def test_zero_gt_leakage_and_audit_determinism(self):
        """Audit must be 100% deterministic and leak zero GT features."""
        r1 = self.auditor.run_audit()
        r2 = self.auditor.run_audit()

        self.assertEqual(r1["gt_runtime_features"], [])
        self.assertEqual(r1["diagnostic_audit_sha256"], r2["diagnostic_audit_sha256"])
        self.assertEqual(len(r1["diagnostic_audit_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()

