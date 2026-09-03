"""Unit tests for Day 13 Realistic Track Evaluation and Safety Invariants.

Verifies:
1. Zero Inversion Invariant across all resolved pairs.
2. Candidate Freeze Barrier enforcement (cannot access GT before freeze).
3. Exact page reproduction (6/10 exact pages, 24/50 resolved regions).
4. Status of the 6 pages from PCPDAG V1 audit.
5. 100% Determinism of candidate generation and evaluation SHA-256 signatures.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day13_evaluation import (
    CandidateFreezeBarrier,
    Day13RealisticEvaluator,
)


class Day13EvaluationTests(unittest.TestCase):

    def setUp(self):
        self.evaluator = Day13RealisticEvaluator()

    def test_candidate_freeze_barrier_prevents_premature_gt_access(self):
        """GT access must be blocked before candidate generation is frozen."""
        barrier = CandidateFreezeBarrier()
        with self.assertRaisesRegex(RuntimeError, "Ground Truth access forbidden before candidate generation is frozen"):
            barrier.access_ground_truth()

    def test_candidate_freeze_barrier_lifecycle(self):
        """Candidate freeze barrier must transition cleanly from candidate to evaluation."""
        barrier = CandidateFreezeBarrier()
        self.assertFalse(barrier.is_frozen)
        self.assertFalse(barrier.gt_accessed)

        barrier.freeze_candidates()
        self.assertTrue(barrier.is_frozen)
        self.assertFalse(barrier.gt_accessed)

        barrier.access_ground_truth()
        self.assertTrue(barrier.gt_accessed)

    def test_realistic_track_zero_inversion_invariant(self):
        """Zero Inversion Invariant: confident_inversions must be strictly 0."""
        inputs = self.evaluator.load_frozen_benchmark_inputs(ROOT)
        candidates = self.evaluator.generate_all_candidates(inputs)

        barrier = CandidateFreezeBarrier()
        barrier.freeze_candidates()

        evaluation = self.evaluator.evaluate_against_ground_truth(candidates, barrier, ROOT)
        summary = evaluation["summary"]

        self.assertEqual(summary["confident_inversions"], 0, "FATAL: Inversion detected in realistic track!")
        self.assertEqual(summary["exact_pages"], [6, 10])
        self.assertEqual(summary["resolved_regions"], [24, 50])
        self.assertEqual(summary["resolved_comparable_pairwise"], [47, 47])
        self.assertEqual(summary["population_pair_coverage"], [47, 124])

    def test_fail_closed_unresolved_pages_behavior(self):
        """Pages with missing panel coverage (1, 3, 5, 15) must fail-closed with empty prediction."""
        inputs = self.evaluator.load_frozen_benchmark_inputs(ROOT)
        candidates = self.evaluator.generate_all_candidates(inputs)

        barrier = CandidateFreezeBarrier()
        barrier.freeze_candidates()

        evaluation = self.evaluator.evaluate_against_ground_truth(candidates, barrier, ROOT)
        by_page = {p["page_order"]: p for p in evaluation["pages"]}

        for p_order in [1, 3, 5, 15]:
            p = by_page[p_order]
            self.assertFalse(p["resolved"], f"Page {p_order} should be fail-closed unresolved")
            self.assertFalse(p["exact"])
            self.assertEqual(p["prediction"], [])
            self.assertEqual(p["confident_inversions"], 0)
            self.assertEqual(p["blocker"], "MISSING_PANEL_COVERAGE")

        for p_order in [2, 4, 7, 17, 18, 38]:
            p = by_page[p_order]
            self.assertTrue(p["resolved"], f"Page {p_order} should be resolved")
            self.assertTrue(p["exact"])
            self.assertEqual(p["prediction"], p["human"])
            self.assertEqual(p["confident_inversions"], 0)
            self.assertEqual(p["blocker"], "RESOLVED")

    def test_candidate_generation_determinism_sha256(self):
        """Generating candidates multiple times must yield exact same SHA-256."""
        inputs = self.evaluator.load_frozen_benchmark_inputs(ROOT)
        c1 = self.evaluator.generate_all_candidates(inputs)
        c2 = self.evaluator.generate_all_candidates(inputs)

        self.assertEqual(c1["candidate_sha256"], c2["candidate_sha256"])
        self.assertEqual(len(c1["candidate_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()

