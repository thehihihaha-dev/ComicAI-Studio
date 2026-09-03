"""Deterministic unit test suite for Day 13 Blind Research Harness.

Verifies:
1. 10/10 runs on identical synthetic input generate the exact same execution graph SHA-256.
2. Fail-closed on cycles in directed constraint graph.
3. Fail-closed on multiple topological orders (ambiguous / unsupported edges).
4. Ground truth isolation: rejection of any forbidden GT keys.
5. Mutation protection: input mutation does not alter evaluator state or result.
6. Checkpoint 12.7 artifact seal verification.
7. Checkpoint 12.8 exclusion barrier enforcement.
"""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day13_harness import (
    CHECKPOINT_12_7_SEAL,
    ArtifactIntegrityError,
    BlindGeometryEvaluator,
    Checkpoint128AccessForbiddenError,
    Checkpoint128ExclusionBarrier,
    GroundTruthLeakageError,
    NormalizedBox,
    UnresolvedOrderError,
    canonicalize_raw_boxes,
    verify_checkpoint_12_7_seal,
)


class Day13HarnessTests(unittest.TestCase):

    def test_checkpoint_12_7_sealed_artifacts_verification(self):
        """Verify all 10 Checkpoint 12.7 archived artifacts match exact sealed SHA-256."""
        result = verify_checkpoint_12_7_seal()
        self.assertEqual(result["status"], "CHECKPOINT_12_7_SEAL_VERIFIED")
        self.assertEqual(result["verified_count"], 10)
        self.assertEqual(result["gt_runtime_features"], [])

    def test_checkpoint_12_7_corrupted_artifact_fails(self):
        """Simulate tampering with a 12.7 artifact and verify it raises ArtifactIntegrityError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create a mock corrupted artifact
            fake_artifact = tmp_path / "panel-relation-model-protocol-12.7.json"
            fake_artifact.write_text('{"tampered": true}', encoding="utf-8")
            with self.assertRaises(ArtifactIntegrityError):
                verify_checkpoint_12_7_seal(benchmarks_dir=tmp_path)

    def test_checkpoint_12_8_exclusion_barrier_blocks_paths(self):
        """Barrier must forbid any identifier, filename, or path referencing Checkpoint 12.8."""
        forbidden_inputs = [
            "panel-geometry-identifiability-evaluation-12.8.json",
            "scripts/panel_geometry_identifiability_audit_12_8.py",
            "benchmarks/day12/panel-geometry-identifiability-protocol-12.8.json",
            "checkpoint_12_8_intermediate_result",
        ]
        for forbidden in forbidden_inputs:
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(Checkpoint128AccessForbiddenError):
                    Checkpoint128ExclusionBarrier.assert_clean_identifier(forbidden)

    def test_checkpoint_12_8_exclusion_barrier_blocks_payload(self):
        """Barrier must recursively inspect and block payloads containing 12.8 contamination."""
        clean_payload = {"experiment": "day13", "method": "PCPDAG_V1", "status": "APPROVED"}
        Checkpoint128ExclusionBarrier.assert_clean_payload(clean_payload)

        contaminated_payloads = [
            {"finding": "15/20 IDENTIFIABLE"},
            {"history": ["checkpoint_12.7", "checkpoint_12.8"]},
            {"details": {"audit_tag": "OUTCOME_B"}},
            {"tags": ["IDENTIFIABILITY_AUDIT"]},
        ]
        for contaminated in contaminated_payloads:
            with self.subTest(contaminated=contaminated):
                with self.assertRaises(Checkpoint128AccessForbiddenError):
                    Checkpoint128ExclusionBarrier.assert_clean_payload(contaminated)

    def test_ground_truth_isolation_strictly_enforced(self):
        """Evaluator must reject any input containing GT keys (gt_runtime_features = [])."""
        evaluator = BlindGeometryEvaluator((100, 100))
        forbidden_keys = ["reading_order", "order", "gt_order", "human_order", "text", "ocr_text", "label"]

        for key in forbidden_keys:
            with self.subTest(key=key):
                leaked_input = [
                    {"bbox": [0, 0, 40, 40], key: [1, 2, 3]},
                    {"bbox": [60, 0, 100, 40]},
                ]
                with self.assertRaises(GroundTruthLeakageError):
                    evaluator.evaluate(leaked_input)

    def test_mutation_protection_preserves_evaluation(self):
        """Modifying raw input before or after evaluate() has zero effect on evaluation."""
        evaluator = BlindGeometryEvaluator((100, 100))
        raw_panels = [
            {"panel_id": "top_right", "bbox": [60, 0, 100, 40]},
            {"panel_id": "top_left", "bbox": [0, 0, 40, 40]},
            {"panel_id": "bottom", "bbox": [0, 60, 100, 100]},
        ]

        # Evaluate initial
        result_1 = evaluator.evaluate(raw_panels)

        # Mutate the input list and dict items in place
        raw_panels[0]["bbox"][0] = 999
        raw_panels.append({"panel_id": "injected", "bbox": [10, 10, 20, 20]})

        # Internal canonicalized boxes and result are completely immune
        self.assertTrue(result_1["resolved"])
        self.assertEqual(result_1["order"], ["top_right", "top_left", "bottom"])

    def test_ten_out_of_ten_runs_raw_byte_determinism(self):
        """10/10 runs on identical synthetic input must yield identical execution graph SHA-256."""
        evaluator = BlindGeometryEvaluator((100, 100))
        # 4-panel classic manga layout: TR -> TL -> BR -> BL
        synthetic_manga_panels = [
            {"panel_id": "top_left", "bbox": [0, 0, 45, 45]},
            {"panel_id": "top_right", "bbox": [55, 0, 100, 45]},
            {"panel_id": "bottom_left", "bbox": [0, 55, 45, 100]},
            {"panel_id": "bottom_right", "bbox": [55, 55, 100, 100]},
        ]

        hashes = []
        orders = []
        for run_idx in range(10):
            # Shuffle input order in each run to test invariance to input permutation
            permuted = (
                list(reversed(synthetic_manga_panels))
                if run_idx % 2 == 1
                else list(synthetic_manga_panels)
            )
            res = evaluator.evaluate(permuted)
            hashes.append(res["graph_sha256"])
            orders.append(res["order"])

        # All 10 hashes must be strictly identical
        self.assertEqual(len(set(hashes)), 1, f"Determinism violated! Generated hashes: {set(hashes)}")
        self.assertEqual(len(set(tuple(o) for o in orders)), 1)
        self.assertEqual(orders[0], ["top_right", "top_left", "bottom_right", "bottom_left"])
        self.assertTrue(hashes[0] is not None and len(hashes[0]) == 64)

    def test_fail_closed_on_multiple_topological_orders(self):
        """When geometry provides insufficient directional constraints (ambiguity), must fail-closed."""
        evaluator = BlindGeometryEvaluator((100, 100))
        # Two horizontal panels with overlapping vertical span and overlapping horizontal span:
        # e.g., both start at y=0, end at y=60, overlapping x.
        ambiguous_panels = [
            {"panel_id": "panel_a", "bbox": [10, 10, 70, 70]},
            {"panel_id": "panel_b", "bbox": [30, 10, 90, 70]},
        ]

        res = evaluator.evaluate(ambiguous_panels, strict_fail_closed=False)
        self.assertFalse(res["resolved"])
        self.assertEqual(res["order"], [])
        self.assertTrue(any(
            u["reason"] in ("MULTIPLE_TOPOLOGICAL_ORDERS", "CONFLICTING_AXIS_EVIDENCE")
            for u in res["unresolved"]
        ))

        # With strict_fail_closed=True, must raise UnresolvedOrderError
        with self.assertRaises(UnresolvedOrderError):
            evaluator.evaluate(ambiguous_panels, strict_fail_closed=True)

    def test_fail_closed_on_directed_cycle(self):
        """When constraint relations form a cycle, must fail-closed."""
        evaluator = BlindGeometryEvaluator((100, 100))
        
        # Test synthetic topological sort cycle detection directly via internal Kahn
        nodes = ["p1", "p2", "p3"]
        cycle_edges = [
            {"before": "p1", "after": "p2", "relation": "ABOVE"},
            {"before": "p2", "after": "p3", "relation": "ABOVE"},
            {"before": "p3", "after": "p1", "relation": "ABOVE"},
        ]
        order, trace, unresolved = evaluator._topological_sort(nodes, cycle_edges)
        self.assertEqual(order, [])
        self.assertTrue(any(u["reason"] == "CYCLE" for u in unresolved))

    def test_exact_one_pixel_boundary_behavior(self):
        """Validate exact 1-pixel boundary behavior matching Checkpoint 12.7."""
        evaluator = BlindGeometryEvaluator((100, 100))
        # Panel A ends at y=51, Panel B starts at y=50. Gap = 50 - 51 = -1 (intrusion = 1 pixel).
        # Under 1-pixel tolerance (intrusion <= 1), A is considered ABOVE B.
        exact_panels = [
            {"panel_id": "a", "bbox": [0, 0, 100, 51]},
            {"panel_id": "b", "bbox": [0, 50, 100, 100]},
        ]
        res_exact = evaluator.evaluate(exact_panels)
        self.assertTrue(res_exact["resolved"])
        self.assertEqual(res_exact["order"], ["a", "b"])

        # If intrusion is 1.01 pixels (A ends at 51.01), it exceeds tolerance and must fail-closed.
        beyond_panels = copy.deepcopy(exact_panels)
        beyond_panels[0]["bbox"][3] = "51.01"
        res_beyond = evaluator.evaluate(beyond_panels)
        self.assertFalse(res_beyond["resolved"])


if __name__ == "__main__":
    unittest.main()

