from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DAY12 = ROOT / "benchmarks/day12"


class ReadingOrderFailureAudit120Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "scripts/reading_order_failure_audit_12_0.py")],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        cls.summary = json.loads((DAY12 / "reading-order-summary-12.0.json").read_text())
        cls.audit = json.loads((DAY12 / "reading-order-failure-audit-12.0.json").read_text())
        cls.candidates = json.loads((DAY12 / "reading-order-candidate-analysis-12.0.json").read_text())
        cls.synthetic = json.loads((DAY12 / "reading-order-synthetic-bridge-12.0.json").read_text())

    def test_frozen_overlap_baseline_and_page_3(self):
        metrics = self.summary["baseline_reproduction"]["metrics"]
        self.assertEqual((7, 43, 120, 4), (metrics["exact_pages"]["correct"],
                         metrics["exact_positions"]["correct"], metrics["pairwise"]["correct"], metrics["inversions"]))
        self.assertEqual({"improved": 3, "unchanged": 7, "regressed": 0},
                         self.summary["baseline_reproduction"]["page_deltas_vs_day11_control"])
        self.assertTrue(self.summary["baseline_reproduction"]["page_3_exact"])

    def test_four_failures_have_required_evidence(self):
        self.assertEqual(4, self.audit["inversion_count"])
        for case in self.audit["cases"]:
            for key in ("asset_id", "source_hash", "regions", "human_relative_order", "predicted_relative_order",
                        "geometry", "neighbors", "algorithm_decision_path", "primary_root_class", "exact_reason"):
                self.assertIn(key, case)

    def test_human_gt_integrity_and_exclusions(self):
        integrity = self.audit["human_gt_integrity"]
        self.assertEqual(integrity["human_gt_sha256_before_after"]["before"], integrity["human_gt_sha256_before_after"]["after"])
        for page in integrity["pages"]:
            self.assertFalse(page["duplicate_order_positions"])
            self.assertEqual([], page["missing_ordered_regions"])
            self.assertEqual([], page["excluded_in_order"])
            self.assertEqual([], page["unclassified_regions"])

    def test_structural_candidates_are_deterministic_and_not_threshold_shop(self):
        self.assertIn("No threshold sweep", self.candidates["protocol"])
        first = (DAY12 / "reading-order-candidate-analysis-12.0.json").read_bytes()
        subprocess.run([sys.executable, str(ROOT / "scripts/reading_order_failure_audit_12_0.py")],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        self.assertEqual(first, (DAY12 / "reading-order-candidate-analysis-12.0.json").read_bytes())

    def test_synthetic_fixture_is_separate_and_exposes_bridge(self):
        self.assertEqual("SYNTHETIC", self.synthetic["evidence_class"])
        self.assertFalse(self.synthetic["counted_as_human_gt"])
        self.assertEqual(0.0, self.synthetic["relations"]["A_C_overlap"])
        with_bridge = self.synthetic["actual_frozen_with_bridge"]
        without_bridge = self.synthetic["actual_frozen_without_bridge"]
        self.assertEqual([["C", "B", "A"]], with_bridge["tiers"])
        self.assertEqual(["C", "B", "A"], with_bridge["order"])
        self.assertEqual([["A"], ["C"]], without_bridge["tiers"])
        self.assertEqual(["A", "C"], without_bridge["order"])
        self.assertLess(with_bridge["order"].index("C"), with_bridge["order"].index("A"))
        self.assertLess(without_bridge["order"].index("A"), without_bridge["order"].index("C"))

    def test_panel_root_causes_and_direct_source_bytes(self):
        self.assertEqual({"C. panel/group construction": 4}, self.audit["root_classes"])
        for case in self.audit["cases"]:
            self.assertEqual("BENCHMARK_ONLY_MANUAL_AUDIT", case["manual_visual_panel_evidence"]["evidence_class"])
            self.assertTrue(case["direct_source_byte_verification"]["direct_source_byte_match"])
            self.assertEqual(1, case["direct_source_byte_verification"]["match_count"])
            self.assertIn("contributing_geometric_symptom", case)

    def test_first_next_experiment_uses_existing_gt(self):
        self.assertFalse(self.summary["human_testing_required_for_next_experiment"])
        self.assertEqual(10, self.summary["smallest_next_experiment"]["pages"])
        self.assertIn("existing immutable Day 11", self.summary["smallest_next_experiment"]["dataset"])

    def test_no_inference_or_production_integration(self):
        safety = self.summary["resource_safety"]
        self.assertEqual((0, 0, 0), (safety["ocr_calls"], safety["vlm_calls"], safety["ollama_calls"]))
        self.assertFalse(self.summary["production_integration"])


if __name__ == "__main__":
    unittest.main()
