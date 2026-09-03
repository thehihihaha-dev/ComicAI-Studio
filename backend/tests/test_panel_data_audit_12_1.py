from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DAY12 = ROOT / "benchmarks/day12"


class PanelDataAudit121Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "scripts/panel_data_audit_12_1.py")], cwd=ROOT,
                       check=True, capture_output=True, text=True)
        cls.audit = json.loads((DAY12 / "panel-data-audit-12.1.json").read_text())
        cls.protocol = json.loads((DAY12 / "panel-aware-protocol-12.1.json").read_text())
        cls.comparison = json.loads((DAY12 / "panel-aware-comparison-12.1.json").read_text())
        cls.errors = json.loads((DAY12 / "panel-aware-structural-errors-12.1.json").read_text())
        cls.summary = json.loads((DAY12 / "panel-aware-summary-12.1.json").read_text())

    def test_ten_page_audit_is_complete_and_source_backed(self):
        self.assertEqual(10, len(self.audit["pages"]))
        self.assertEqual(63, self.audit["totals"]["text_regions"])
        self.assertEqual({1, 2, 3, 4, 5, 7, 15, 17, 18, 38}, {p["page_order"] for p in self.audit["pages"]})
        for page in self.audit["pages"]:
            self.assertTrue(page["asset_id"] and page["source_hash"])
            self.assertEqual(page["text_region_count"], page["regions_without_usable_panel"])

    def test_11_10_scale_and_cache_are_explicitly_audited_per_page(self):
        required = {"reader-v2-scale-40p-11.10.json", "reader-v2-scale-cache-11.10.json"}
        self.assertTrue(required <= set(self.audit["audit_inputs"]))
        sources = {source["artifact"]: source for source in self.audit["potential_panel_sources"]}
        for name in required:
            self.assertEqual(10, sources[name]["record_count"])
            self.assertEqual("PAGE_LEVEL_FALLBACK", sources[name]["classification"])
            self.assertFalse(sources[name]["legitimate_candidate_input"])
        for page in self.audit["pages"]:
            provenance = {entry["artifact"]: entry for entry in page["panel_geometry_provenance"]}
            scale = provenance["reader-v2-scale-40p-11.10.json"]
            cache = provenance["reader-v2-scale-cache-11.10.json"]
            self.assertEqual(0, scale["values"]["panel_count"])
            self.assertEqual(["PAGE"], scale["values"]["panel_order"])
            self.assertEqual("page_fallback_no_panel_hierarchy", scale["values"]["panel_source"])
            self.assertEqual(["PAGE"], [group["group_id"] for group in scale["values"]["group_assignments"]])
            self.assertEqual(["PAGE"], cache["values"]["panel_order"])
            self.assertEqual("page_fallback_no_panel_hierarchy", cache["values"]["panel_source"])
            self.assertEqual("PAGE_LEVEL_FALLBACK", scale["classification"])
            self.assertEqual("PAGE_LEVEL_FALLBACK", cache["classification"])

    def test_gate_fails_for_missing_non_human_panel_geometry(self):
        self.assertFalse(self.audit["gate_pass"])
        self.assertEqual([], self.audit["known_failure_page_gate"]["usable"])
        self.assertEqual(0, self.audit["totals"]["usable_predicted_panels"])
        self.assertEqual("FAILED", self.summary["panel_data_gate"])
        self.assertEqual("B. PANEL DETECTION/ASSIGNMENT IS THE BOTTLENECK", self.summary["outcome"])

    def test_gt_and_manual_evidence_are_excluded_from_runtime(self):
        self.assertFalse(self.audit["human_click_order_loaded_during_audit"])
        self.assertFalse(self.audit["manual_12_0_evidence_policy"]["used_as_prediction_input"])
        self.assertEqual([], self.protocol["gt_runtime_features"])
        self.assertFalse(self.protocol["human_or_manual_panel_input"])
        self.assertFalse(self.summary["gt_leakage_audit"]["human_or_manual_panel_evidence_used_as_prediction_input"])

    def test_not_run_artifacts_are_honest(self):
        self.assertEqual("NOT_RUN_PANEL_DATA_GATE_FAILED", self.protocol["status"])
        self.assertEqual("NOT_RUN_PANEL_DATA_GATE_FAILED", self.comparison["status"])
        self.assertEqual("NOT_RUN_PANEL_DATA_GATE_FAILED", self.errors["status"])
        self.assertFalse(self.summary["candidate_implemented"])
        self.assertFalse(self.summary["candidate_evaluated"])
        self.assertIsNone(self.comparison["candidate"])

    def test_frozen_control_and_page_3(self):
        control = self.comparison["control"]
        metrics = control["metrics"]
        self.assertEqual((7, 43, 120, 4), (metrics["exact_pages"]["correct"], metrics["exact_positions"]["correct"],
                                                metrics["pairwise"]["correct"], metrics["inversions"]))
        self.assertEqual({"improved": 3, "unchanged": 7, "regressed": 0}, control["page_deltas_vs_previous_control"])
        self.assertTrue(control["page_3_exact"])

    def test_pre_score_hashes_and_deterministic_audit(self):
        for name, expected in self.comparison["pre_score_artifact_hashes"].items():
            self.assertEqual(expected, hashlib.sha256((DAY12 / name).read_bytes()).hexdigest())
        first = (DAY12 / "panel-data-audit-12.1.json").read_bytes()
        subprocess.run([sys.executable, str(ROOT / "scripts/panel_data_audit_12_1.py")], cwd=ROOT,
                       check=True, capture_output=True, text=True)
        self.assertEqual(first, (DAY12 / "panel-data-audit-12.1.json").read_bytes())

    def test_no_models_no_candidate_no_human_request(self):
        safety = self.summary["resource_safety"]
        self.assertEqual((0, 0, 0), (safety["ocr_calls"], safety["vlm_calls"], safety["ollama_calls"]))
        self.assertFalse(self.summary["production_integration"])
        self.assertFalse(self.summary["unseen_human_testing_justified"])


if __name__ == "__main__":
    unittest.main()
