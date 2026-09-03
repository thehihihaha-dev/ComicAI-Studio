#!/usr/bin/env python3
"""Day 13 Research Harness CLI & Bridge module."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.research.day13_harness import (
    CHECKPOINT_12_7_SEAL,
    FORBIDDEN_12_8_PATTERNS,
    FORBIDDEN_GT_KEYS,
    ArtifactIntegrityError,
    BlindGeometryEvaluator,
    Checkpoint128AccessForbiddenError,
    Checkpoint128ExclusionBarrier,
    Day13HarnessError,
    GroundTruthLeakageError,
    NormalizedBox,
    UnresolvedOrderError,
    canonicalize_raw_boxes,
    compute_file_sha256,
    verify_checkpoint_12_7_seal,
)

__all__ = [
    "CHECKPOINT_12_7_SEAL",
    "FORBIDDEN_12_8_PATTERNS",
    "FORBIDDEN_GT_KEYS",
    "ArtifactIntegrityError",
    "BlindGeometryEvaluator",
    "Checkpoint128AccessForbiddenError",
    "Checkpoint128ExclusionBarrier",
    "Day13HarnessError",
    "GroundTruthLeakageError",
    "NormalizedBox",
    "UnresolvedOrderError",
    "canonicalize_raw_boxes",
    "compute_file_sha256",
    "verify_checkpoint_12_7_seal",
]


def main() -> int:
    print("=== Day 13 Research Harness: Verifying Checkpoint 12.7 Artifact Seal ===")
    try:
        seal_result = verify_checkpoint_12_7_seal()
        print(f"Status: {seal_result['status']}")
        print(f"Verified {seal_result['verified_count']}/{len(CHECKPOINT_12_7_SEAL)} sealed artifacts successfully.")
        return 0
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

