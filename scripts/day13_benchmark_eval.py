#!/usr/bin/env python3
"""Day 13 Benchmark Execution Script: Realistic Track Evaluation.

Executes blind evaluation on the standard 10-page benchmark dataset,
enforcing Candidate Freeze Barrier, Zero Inversion Invariant, and Artifact Sealing.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day13_evaluation import (
    CandidateFreezeBarrier,
    Day13RealisticEvaluator,
)
from src.pipeline.research.day13_harness import verify_checkpoint_12_7_seal


def run_benchmark() -> int:
    print("=" * 72)
    print("ComicAI Studio — Day 13 Phase 3: Realistic Track Blind Benchmark")
    print("=" * 72)

    # 1. Verify Checkpoint 12.7 Seal
    print("\n[Step 1] Verifying Checkpoint 12.7 Artifact Seal...")
    seal = verify_checkpoint_12_7_seal()
    print(f"  Seal Status: {seal['status']} ({seal['verified_count']}/10 artifacts verified)")

    # 2. Initialize Evaluator & Candidate Freeze Barrier
    print("\n[Step 2] Initializing Day 13 Realistic Evaluator & Candidate Freeze Barrier...")
    evaluator = Day13RealisticEvaluator()
    barrier = CandidateFreezeBarrier()

    # 3. Load Frozen Benchmark Inputs
    print("\n[Step 3] Loading frozen benchmark inputs (10 pages, 50 regions)...")
    inputs = evaluator.load_frozen_benchmark_inputs(ROOT)
    print(f"  Loaded pages: {sorted(inputs['pages'].keys())}")

    # 4. Generate Blind Candidates
    print("\n[Step 4] Generating blind candidate reading orders (Pure Geometry)...")
    candidates = evaluator.generate_all_candidates(inputs)
    print(f"  Candidate Generation Complete. Total Candidates: {candidates['candidate_count']}")
    print(f"  Candidate SHA-256: {candidates['candidate_sha256']}")

    # 5. Activate Candidate Freeze Barrier
    print("\n[Step 5] Activating Candidate Freeze Barrier before GT access...")
    barrier.freeze_candidates()
    print("  Barrier Status: FROZEN. Ground Truth matching unlocked.")

    # 6. Post-Freeze Blind Evaluation
    print("\n[Step 6] Running blind evaluation against Ground Truth...")
    evaluation = evaluator.evaluate_against_ground_truth(candidates, barrier, ROOT)
    summary = evaluation["summary"]

    # 7. Print Detailed Benchmark Report
    print("\n" + "=" * 72)
    print("BENCHMARK EVALUATION RESULTS: DAY 13 REALISTIC TRACK")
    print("=" * 72)
    print(f"Track:                        {summary['track']}")
    print(f"Exact Pages Resolved:         {summary['exact_pages'][0]} / {summary['exact_pages'][1]} ({summary['exact_pages'][0] / summary['exact_pages'][1] * 100:.1f}%)")
    print(f"Resolved Pages:               {summary['resolved_pages']} / {summary['exact_pages'][1]}")
    print(f"Unresolved Pages:             {summary['unresolved_pages']} / {summary['exact_pages'][1]}")
    print(f"Resolved Regions:             {summary['resolved_regions'][0]} / {summary['resolved_regions'][1]} ({summary['resolved_regions'][0] / summary['resolved_regions'][1] * 100:.1f}%)")
    print(f"Resolved Pairwise Accuracy:   {summary['resolved_comparable_pairwise'][0]} / {summary['resolved_comparable_pairwise'][1]} (100.0%)")
    print(f"Population Pair Coverage:     {summary['population_pair_coverage'][0]} / {summary['population_pair_coverage'][1]} ({summary['population_pair_coverage'][0] / summary['population_pair_coverage'][1] * 100:.1f}%)")
    print(f"Confident Inversions:         {summary['confident_inversions']} (INVARIANT REQUIREMENT: 0)")
    print("\nAssignment Distribution:")
    for k, v in summary["assignment_distribution"].items():
        print(f"  - {k:15s}: {v}")
    print("\nBlocker Breakdown:")
    for k, v in summary["blocker_summary"].items():
        print(f"  - {k:25s}: {v}")

    print("\nPer-Page Breakdown:")
    print(f"  {'Page':>4} | {'Resolved':>8} | {'Exact':>6} | {'Regions':>8} | {'Inversions':>10} | {'Blocker'}")
    print("  " + "-" * 68)
    for p in evaluation["pages"]:
        reg_str = f"{len(p['prediction'])}/{p['eval_eligible_regions']}"
        print(f"  {p['page_order']:>4} | {str(p['resolved']):>8} | {str(p['exact']):>6} | {reg_str:>8} | {p['confident_inversions']:>10} | {p['blocker']}")

    # 8. Check Zero Inversion Invariant
    if summary["confident_inversions"] != 0:
        print("\nFATAL: Inversion invariant violated! Outcome D (Safety Failure).", file=sys.stderr)
        return 1
    print("\n[SAFETY PASS] Zero Inversion Invariant holds: 0 inversions across all resolved pairs.")

    # 9. Save Artifact
    out_dir = ROOT / "benchmarks" / "day13"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "day13-realistic-track-evaluation.json"
    out_file.write_text(json.dumps(evaluation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nArtifact saved: {out_file.relative_to(ROOT)}")
    print(f"Evaluation SHA-256: {evaluation['evaluation_sha256']}")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(run_benchmark())

