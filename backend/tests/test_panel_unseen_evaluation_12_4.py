import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.panel_unseen_evaluation_12_4 import canonical_hash, generate


DAY12 = ROOT / "benchmarks/day12"


class PanelUnseenEvaluation12_4Tests(unittest.TestCase):
    def test_two_generations_are_byte_identical(self):
        self.assertEqual(generate(), generate())

    def test_frozen_inputs_and_protocol(self):
        protocol, _, _ = map(json.loads, (part.decode() for part in generate()))
        self.assertEqual(protocol["frozen_inputs"]["prediction_fingerprint_sha256"],
                         "a0f7d0559922376be3bb665bce814d003425c59fdfbafb77c0a6bda78457e26a")
        self.assertEqual(protocol["frozen_inputs"]["human_gt_fingerprint_sha256"],
                         "f62e38d5ed28531681b9165cca77e0f62ab37b7cf92a5161cab0c9f0cb6216ea")
        self.assertEqual(protocol["matching"]["bbox_iou_threshold"], 0.5)
        self.assertEqual(protocol["gt_runtime_features"], [])

    def test_metrics_reconcile(self):
        _, evaluation_bytes, _ = generate()
        result = json.loads(evaluation_bytes)
        pages = result["per_page"]
        aggregate = result["aggregate"]
        self.assertEqual(sum(row["human_panel_count"] for row in pages), aggregate["human_panels"])
        self.assertEqual(sum(row["selected_prediction_count"] for row in pages), aggregate["selected_predictions"])
        self.assertEqual(sum(row["matched"] for row in pages), aggregate["matched"])
        self.assertEqual(sum(row["missed"] for row in pages), aggregate["missed"])
        self.assertEqual(sum(row["false_promoted"] for row in pages), aggregate["false_promoted"])
        self.assertEqual(len(result["missed_panel_audit"]), aggregate["missed"])
        self.assertEqual(len(result["false_promotion_audit"]), aggregate["false_promoted"])

    def test_outcome_a_is_mechanical_and_raw_control_does_not_regress(self):
        _, evaluation_bytes, _ = generate()
        result = json.loads(evaluation_bytes)
        self.assertTrue(all(result["predeclared_gate_results"].values()))
        self.assertTrue(result["outcome"].startswith("A."))
        self.assertTrue(result["raw_detected_control"]["resolver_matches_not_below_control"])

    def test_artifacts_reproduce_generated_bytes_when_present(self):
        generated = generate()
        names = ("panel-unseen-evaluation-protocol-12.4.json", "panel-unseen-evaluation-12.4.json",
                 "panel-unseen-summary-12.4.json")
        for name, expected in zip(names, generated, strict=True):
            path = DAY12 / name
            if path.exists():
                self.assertEqual(path.read_bytes(), expected)
        summary = json.loads(generated[2])
        self.assertEqual(summary["determinism"]["evaluation_semantic_sha256"],
                         canonical_hash(json.loads(generated[1])))


if __name__ == "__main__":
    unittest.main()
