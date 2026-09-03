"""Day 13 Research: Deterministic Region-to-Panel Assignment Engine.

Strict Invariants:
1. ARITHMETIC PRECISION: Decimal and Fraction arithmetic for all areas, ratios, and margins. Zero floats.
2. IMMUTABLE INPUT: Input sequences deep-frozen into immutable tuples of NormalizedBox.
3. FAIL-CLOSED ASSIGNMENT:
   - 100% containment in 1 panel -> ASSIGNED_CONTAINED.
   - Distinct majority (> min_majority_ratio) with margin (> ambiguity_margin) -> ASSIGNED_MAJORITY.
   - Ambiguous boundary / competing candidates without decisive margin -> AMBIGUOUS.
   - Zero intersection -> UNASSIGNED (no centroid distance or nearest-neighbor heuristic).
4. GT ISOLATION: gt_runtime_features = [] strictly enforced.
5. REPRODUCIBILITY: Canonical serialization with raw-byte SHA-256 assignment signature.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from typing import Any, Mapping, Sequence

from src.pipeline.research.day13_harness import (
    FORBIDDEN_GT_KEYS,
    GroundTruthLeakageError,
    NormalizedBox,
)


def exact_box_area(box: NormalizedBox) -> Decimal:
    """Calculate exact area of a NormalizedBox in Decimal."""
    return (box.x2 - box.x1) * (box.y2 - box.y1)


def exact_intersection_area(a: NormalizedBox, b: NormalizedBox) -> Decimal:
    """Calculate exact intersection area between two boxes in Decimal."""
    x_overlap = max(Decimal(0), min(a.x2, b.x2) - max(a.x1, b.x1))
    y_overlap = max(Decimal(0), min(a.y2, b.y2) - max(a.y1, b.y1))
    return x_overlap * y_overlap


def exact_coverage_ratio(region: NormalizedBox, panel: NormalizedBox) -> Fraction:
    """Calculate exact fraction of region's area covered by panel."""
    reg_area = exact_box_area(region)
    if reg_area <= Decimal(0):
        raise ValueError(f"Region {region.panel_id} has non-positive area.")
    inter_area = exact_intersection_area(region, panel)
    return Fraction(inter_area) / Fraction(reg_area)


@dataclass(frozen=True)
class RegionAssignmentRecord:
    """Immutable record for a single region assignment decision."""
    region_id: str
    assigned_panel_id: str | None
    status: str  # ASSIGNED_CONTAINED, ASSIGNED_MAJORITY, AMBIGUOUS, UNASSIGNED
    decision_reason: str
    containment_ratio: Fraction
    margin: Fraction
    competing_panels: tuple[tuple[str, Fraction], ...]  # tuple of (panel_id, ratio)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "assigned_panel_id": self.assigned_panel_id,
            "status": self.status,
            "decision_reason": self.decision_reason,
            "containment_ratio": str(self.containment_ratio),
            "margin": str(self.margin),
            "competing_panels": [
                {"panel_id": pid, "ratio": str(r)}
                for pid, r in self.competing_panels
            ],
        }


@dataclass(frozen=True)
class AssignmentResult:
    """Deterministic result of the region-to-panel assignment process."""
    panel_to_regions: dict[str, list[str]]
    assigned_records: list[dict[str, Any]]
    ambiguous_region_ids: list[str]
    unassigned_region_ids: list[str]
    ambiguous_details: list[dict[str, Any]]
    unassigned_details: list[dict[str, Any]]
    summary: dict[str, int]
    gt_runtime_features: list[str]
    assignment_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "day13_region_assignment.v1",
            "panel_to_regions": self.panel_to_regions,
            "assigned_records": self.assigned_records,
            "ambiguous_region_ids": self.ambiguous_region_ids,
            "unassigned_region_ids": self.unassigned_region_ids,
            "ambiguous_details": self.ambiguous_details,
            "unassigned_details": self.unassigned_details,
            "summary": self.summary,
            "gt_runtime_features": self.gt_runtime_features,
            "assignment_sha256": self.assignment_sha256,
        }


class DeterministicRegionAssigner:
    """Fail-closed geometric assigner with exact Decimal / Fraction arithmetic."""

    DEFAULT_MIN_MAJORITY_RATIO = Fraction(1, 2)  # 50%
    DEFAULT_AMBIGUITY_MARGIN = Fraction(1, 10)    # 10%

    def __init__(
        self,
        min_majority_ratio: Fraction = DEFAULT_MIN_MAJORITY_RATIO,
        ambiguity_margin: Fraction = DEFAULT_AMBIGUITY_MARGIN,
    ) -> None:
        if min_majority_ratio <= Fraction(0) or min_majority_ratio > Fraction(1):
            raise ValueError("min_majority_ratio must be in (0, 1].")
        if ambiguity_margin < Fraction(0) or ambiguity_margin >= Fraction(1):
            raise ValueError("ambiguity_margin must be in [0, 1).")
        self.min_majority_ratio = min_majority_ratio
        self.ambiguity_margin = ambiguity_margin

    def _freeze_boxes(self, boxes: Sequence[Any], label: str) -> tuple[NormalizedBox, ...]:
        """Validate, deep-copy, check GT leakage, and freeze input into canonical order."""
        frozen_list: list[NormalizedBox] = []
        for idx, item in enumerate(boxes):
            if isinstance(item, NormalizedBox):
                frozen_list.append(item)
            elif isinstance(item, Mapping):
                # Check Ground Truth Leakage
                leakage = FORBIDDEN_GT_KEYS.intersection(item.keys())
                if leakage:
                    raise GroundTruthLeakageError(
                        f"Ground truth leakage detected in {label} at index {idx}: {sorted(leakage)}"
                    )
                bbox = item.get("bbox")
                if not bbox or len(bbox) != 4:
                    raise ValueError(f"{label} at index {idx} must have 4-element 'bbox'.")
                x1, y1, x2, y2 = (Decimal(str(v)) for v in bbox)
                box_id = str(item.get("panel_id") or item.get("region_id") or item.get("id") or f"{label}_{idx}")
                frozen_list.append(NormalizedBox(x1=x1, y1=y1, x2=x2, y2=y2, panel_id=box_id))
            else:
                raise TypeError(f"Items in {label} must be NormalizedBox or Mapping, got {type(item)}")

        # Deterministic sorting
        frozen_list.sort(key=lambda b: (b.panel_id, b.x1, b.y1, b.x2, b.y2))
        return tuple(frozen_list)

    def assign_regions(
        self,
        panels: Sequence[Any],
        regions: Sequence[Any],
    ) -> AssignmentResult:
        """Assign regions to panels deterministically based purely on 2D geometry.

        Args:
            panels: Sequence of NormalizedBox or panel dicts.
            regions: Sequence of NormalizedBox or region dicts.

        Returns:
            AssignmentResult with deterministic signature and fail-closed resolution.
        """
        # Step 1: Immutable input freezing and sorting
        frozen_panels = self._freeze_boxes(panels, "panels")
        frozen_regions = self._freeze_boxes(regions, "regions")

        panel_to_regions: dict[str, list[str]] = {p.panel_id: [] for p in frozen_panels}
        assigned_records: list[dict[str, Any]] = []
        ambiguous_ids: list[str] = []
        unassigned_ids: list[str] = []
        ambiguous_details: list[dict[str, Any]] = []
        unassigned_details: list[dict[str, Any]] = []

        # Step 2: Iterate through each region deterministically
        for reg in frozen_regions:
            reg_area = exact_box_area(reg)
            candidates: list[dict[str, Any]] = []

            for pan in frozen_panels:
                inter_area = exact_intersection_area(reg, pan)
                if inter_area > Decimal(0):
                    ratio = Fraction(inter_area) / Fraction(reg_area)
                    is_contained = (inter_area == reg_area)
                    candidates.append({
                        "panel_id": pan.panel_id,
                        "intersection_area": inter_area,
                        "ratio": ratio,
                        "is_contained": is_contained,
                    })

            # Sort candidates by ratio descending, then panel_id ascending for 100% determinism
            candidates.sort(key=lambda c: (-c["ratio"], c["panel_id"]))

            # Step 3: Decision Logic (Strict Fail-Closed)
            if not candidates:
                # Region has 0 intersection with all panels
                unassigned_ids.append(reg.panel_id)
                rec = RegionAssignmentRecord(
                    region_id=reg.panel_id,
                    assigned_panel_id=None,
                    status="UNASSIGNED",
                    decision_reason="NO_INTERSECTING_PANELS",
                    containment_ratio=Fraction(0),
                    margin=Fraction(0),
                    competing_panels=(),
                )
                unassigned_details.append(rec.to_dict())
                assigned_records.append(rec.to_dict())
                continue

            # Check 100% Containment
            containing = [c for c in candidates if c["is_contained"]]
            if len(containing) == 1:
                assigned_panel = containing[0]["panel_id"]
                panel_to_regions[assigned_panel].append(reg.panel_id)
                second_ratio = candidates[1]["ratio"] if len(candidates) > 1 else Fraction(0)
                margin = Fraction(1) - second_ratio
                rec = RegionAssignmentRecord(
                    region_id=reg.panel_id,
                    assigned_panel_id=assigned_panel,
                    status="ASSIGNED_CONTAINED",
                    decision_reason="UNIQUE_100_PERCENT_CONTAINMENT",
                    containment_ratio=Fraction(1),
                    margin=margin,
                    competing_panels=tuple((c["panel_id"], c["ratio"]) for c in candidates),
                )
                assigned_records.append(rec.to_dict())
                continue

            if len(containing) > 1:
                # Multiple panels contain region completely (nested/overlapping panels)
                ambiguous_ids.append(reg.panel_id)
                rec = RegionAssignmentRecord(
                    region_id=reg.panel_id,
                    assigned_panel_id=None,
                    status="AMBIGUOUS",
                    decision_reason="MULTIPLE_CONTAINING_PANELS",
                    containment_ratio=Fraction(1),
                    margin=Fraction(0),
                    competing_panels=tuple((c["panel_id"], c["ratio"]) for c in candidates),
                )
                ambiguous_details.append(rec.to_dict())
                assigned_records.append(rec.to_dict())
                continue

            # Check Unique Majority Intersection
            top_c = candidates[0]
            top_ratio = top_c["ratio"]
            second_ratio = candidates[1]["ratio"] if len(candidates) > 1 else Fraction(0)
            margin = top_ratio - second_ratio

            has_majority = (top_ratio > self.min_majority_ratio)
            has_margin = (margin > self.ambiguity_margin)

            if has_majority and has_margin:
                assigned_panel = top_c["panel_id"]
                panel_to_regions[assigned_panel].append(reg.panel_id)
                rec = RegionAssignmentRecord(
                    region_id=reg.panel_id,
                    assigned_panel_id=assigned_panel,
                    status="ASSIGNED_MAJORITY",
                    decision_reason="UNIQUE_STRICT_MAJORITY_INTERSECTION",
                    containment_ratio=top_ratio,
                    margin=margin,
                    competing_panels=tuple((c["panel_id"], c["ratio"]) for c in candidates),
                )
                assigned_records.append(rec.to_dict())
            else:
                reason = (
                    "INSUFFICIENT_MAJORITY_RATIO"
                    if not has_majority
                    else "MARGIN_WITHIN_AMBIGUITY_BAND"
                )
                ambiguous_ids.append(reg.panel_id)
                rec = RegionAssignmentRecord(
                    region_id=reg.panel_id,
                    assigned_panel_id=None,
                    status="AMBIGUOUS",
                    decision_reason=reason,
                    containment_ratio=top_ratio,
                    margin=margin,
                    competing_panels=tuple((c["panel_id"], c["ratio"]) for c in candidates),
                )
                ambiguous_details.append(rec.to_dict())
                assigned_records.append(rec.to_dict())

        # Step 4: Final Canonical Assembly & SHA-256 Signature
        # Sort assigned regions inside each panel deterministically
        for pid in panel_to_regions:
            panel_to_regions[pid].sort()

        assigned_records.sort(key=lambda r: r["region_id"])
        ambiguous_ids.sort()
        unassigned_ids.sort()
        ambiguous_details.sort(key=lambda r: r["region_id"])
        unassigned_details.sort(key=lambda r: r["region_id"])

        summary = {
            "total_panels": len(frozen_panels),
            "total_regions": len(frozen_regions),
            "assigned_regions": len(frozen_regions) - len(ambiguous_ids) - len(unassigned_ids),
            "ambiguous_regions": len(ambiguous_ids),
            "unassigned_regions": len(unassigned_ids),
        }

        raw_payload = {
            "schema_version": "day13_region_assignment.v1",
            "panel_to_regions": panel_to_regions,
            "assigned_records": assigned_records,
            "ambiguous_region_ids": ambiguous_ids,
            "unassigned_region_ids": unassigned_ids,
            "ambiguous_details": ambiguous_details,
            "unassigned_details": unassigned_details,
            "summary": summary,
            "gt_runtime_features": [],
        }

        canonical_bytes = json.dumps(
            raw_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        assignment_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

        return AssignmentResult(
            panel_to_regions=panel_to_regions,
            assigned_records=assigned_records,
            ambiguous_region_ids=ambiguous_ids,
            unassigned_region_ids=unassigned_ids,
            ambiguous_details=ambiguous_details,
            unassigned_details=unassigned_details,
            summary=summary,
            gt_runtime_features=[],
            assignment_sha256=assignment_sha256,
        )

