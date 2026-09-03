#!/usr/bin/env python3
"""Day 13 Region-to-Panel Assignment CLI & Bridge."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.research.day13_assignment import (
    AssignmentResult,
    DeterministicRegionAssigner,
    RegionAssignmentRecord,
    exact_box_area,
    exact_coverage_ratio,
    exact_intersection_area,
)

__all__ = [
    "AssignmentResult",
    "DeterministicRegionAssigner",
    "RegionAssignmentRecord",
    "exact_box_area",
    "exact_coverage_ratio",
    "exact_intersection_area",
]

if __name__ == "__main__":
    print("Day 13 Deterministic Region Assigner module ready.")

