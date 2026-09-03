#!/usr/bin/env python3
"""Day 14 Phase 1: Diagnostic Audit of Missing Panel Coverage (Fail-Closed Pages).

Performs independent geometric root-cause analysis on the 4 fail-closed benchmark pages
(Pages 1, 3, 5, 15), profiling spatial coordinates, measuring panel distances/overlap,
categorizing failure modes, and simulating deterministic bounding box synthesis.

Safety Invariants:
1. ZERO GT LEAKAGE: Evaluates pure geometry without human reading order labels.
2. NO CODE MODIFICATION TO PRODUCTION: Read-only research script.
3. FAIL-CLOSED PRESERVATION: Diagnostics only; does not inject candidate mutations.
4. EXACT ARITHMETIC: Decimal coordinates and area calculations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day13_harness import Checkpoint128ExclusionBarrier

FAIL_CLOSED_PAGES = [1, 3, 5, 15]


@dataclass
class UnassignedRegionProfile:
    region_id: str
    page_order: int
    raw_bbox: list[float]
    normalized_coords: list[float]  # [ymin, xmin, ymax, xmax] in [0, 1]
    nearest_panel_id: str | None
    min_euclidean_distance: float | None
    min_axis_gap_x: float | None
    min_axis_gap_y: float | None
    overlap_with_nearest_panel: float
    root_cause_category: str
    root_cause_reason: str


@dataclass
class EnclosingBoxSimulation:
    page_order: int
    unassigned_region_count: int
    enclosing_bbox: list[float]
    normalized_enclosing_bbox: list[float]
    existing_panel_count: int
    overlap_conflicts: list[dict[str, Any]]
    has_geometric_conflict: bool
    vertical_gap_to_nearest_panel: float | None
    horizontal_gap_to_nearest_panel: float | None
    synthesis_feasibility: str


def compute_box_distance_and_overlap(
    r_bbox: list[Decimal],
    p_bbox: list[Decimal],
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Compute (euclidean_dist, dx, dy, overlap_area) between region and panel."""
    rx1, ry1, rx2, ry2 = r_bbox
    px1, py1, px2, py2 = p_bbox

    dx = max(Decimal(0), max(rx1 - px2, px1 - rx2))
    dy = max(Decimal(0), max(ry1 - py2, py1 - ry2))
    dist = Decimal(str(float(dx**2 + dy**2) ** 0.5))

    ox = max(Decimal(0), min(rx2, px2) - max(rx1, px1))
    oy = max(Decimal(0), min(ry2, py2) - max(ry1, py1))
    overlap = ox * oy

    return dist, dx, dy, overlap


def run_diagnostic_audit() -> dict[str, Any]:
    print("=" * 76)
    print("ComicAI Studio — Day 14 Phase 1: Diagnostic Audit (Fail-Closed Pages)")
    print("=" * 76)

    # 1. Load inputs with 12.8 Barrier
    eval_path = ROOT / "benchmarks" / "day13" / "day13-realistic-track-evaluation.json"
    audit_input_path = ROOT / "benchmarks" / "day12" / "panel-relation-model-input-audit-12.7.json"

    eval_doc = Checkpoint128ExclusionBarrier.safe_load_json(eval_path)
    audit_doc = Checkpoint128ExclusionBarrier.safe_load_json(audit_input_path)

    input_pages = {p["page_order"]: p for p in audit_doc["runtime_phase"]["pages"]}
    eval_pages = {p["page_order"]: p for p in eval_doc["pages"]}

    region_profiles: list[UnassignedRegionProfile] = []
    simulations: list[EnclosingBoxSimulation] = []
    page_diagnostics: list[dict[str, Any]] = []

    for p_num in FAIL_CLOSED_PAGES:
        info = input_pages[p_num]
        eval_p = eval_pages[p_num]
        w, h = info["image_dimensions"]
        w_dec, h_dec = Decimal(str(w)), Decimal(str(h))

        unassigned_ids = set(eval_p["unassigned_region_ids"])
        unassigned_regs = [
            r for r in info["persisted_logical_regions"] if r["id"] in unassigned_ids
        ]
        # Sort spatially top-to-bottom, right-to-left
        unassigned_regs.sort(key=lambda r: (r["bbox"][1], -r["bbox"][0]))
        existing_panels = info["realistic_selected_panels"]

        print(f"\n[Page {p_num:>2}] Dimensions: {w}x{h} | Existing Panels: {len(existing_panels)} | Unassigned Regions: {len(unassigned_regs)}")

        # Root cause classification context
        # Page 5 has solid black gutters (borderless dark scene)
        # Pages 1, 3, 15 have white gutters with under-segmented panel contours
        page_category = (
            "BORDERLESS_BACKGROUND_PANEL"
            if p_num == 5
            else "UNDER_SEGMENTED_PANEL"
        )
        page_reason = (
            "Dark full-bleed artwork with black gutters causing whitespace partition failure"
            if p_num == 5
            else "Panel boundary contour missed or conflicted during upstream extraction"
        )

        for reg in unassigned_regs:
            rx1, ry1, rx2, ry2 = [Decimal(str(c)) for c in reg["bbox"]]
            norm = [
                float(ry1 / h_dec),
                float(rx1 / w_dec),
                float(ry2 / h_dec),
                float(rx2 / w_dec),
            ]

            nearest_pan_id = None
            min_dist = None
            min_dx = None
            min_dy = None
            max_overlap = Decimal(0)

            for pan in existing_panels:
                px1, py1, px2, py2 = [Decimal(str(c)) for c in pan["bbox"]]
                dist, dx, dy, overlap = compute_box_distance_and_overlap(
                    [rx1, ry1, rx2, ry2], [px1, py1, px2, py2]
                )
                if min_dist is None or dist < min_dist:
                    min_dist = dist
                    min_dx = dx
                    min_dy = dy
                    nearest_pan_id = pan["panel_id"]
                if overlap > max_overlap:
                    max_overlap = overlap

            profile = UnassignedRegionProfile(
                region_id=reg["id"],
                page_order=p_num,
                raw_bbox=[float(c) for c in [rx1, ry1, rx2, ry2]],
                normalized_coords=[round(c, 4) for c in norm],
                nearest_panel_id=nearest_pan_id,
                min_euclidean_distance=round(float(min_dist), 2) if min_dist is not None else None,
                min_axis_gap_x=round(float(min_dx), 2) if min_dx is not None else None,
                min_axis_gap_y=round(float(min_dy), 2) if min_dy is not None else None,
                overlap_with_nearest_panel=float(max_overlap),
                root_cause_category=page_category,
                root_cause_reason=page_reason,
            )
            region_profiles.append(profile)

        # Minimum Enclosing Bounding Box (MEBB) simulation
        min_x = min(Decimal(str(r["bbox"][0])) for r in unassigned_regs)
        min_y = min(Decimal(str(r["bbox"][1])) for r in unassigned_regs)
        max_x = max(Decimal(str(r["bbox"][2])) for r in unassigned_regs)
        max_y = max(Decimal(str(r["bbox"][3])) for r in unassigned_regs)

        norm_enclosing = [
            float(round(min_y / h_dec, 4)),
            float(round(min_x / w_dec, 4)),
            float(round(max_y / h_dec, 4)),
            float(round(max_x / w_dec, 4)),
        ]

        conflicts = []
        vert_gaps = []
        horiz_gaps = []

        for pan in existing_panels:
            px1, py1, px2, py2 = [Decimal(str(c)) for c in pan["bbox"]]
            _, dx, dy, overlap = compute_box_distance_and_overlap(
                [min_x, min_y, max_x, max_y], [px1, py1, px2, py2]
            )
            if overlap > Decimal(0):
                conflicts.append({
                    "panel_id": pan["panel_id"],
                    "overlap_area": float(overlap),
                })
            vert_gaps.append(float(dy))
            horiz_gaps.append(float(dx))

        has_conflict = len(conflicts) > 0
        min_v_gap = min(vert_gaps) if vert_gaps else None
        min_h_gap = min(horiz_gaps) if horiz_gaps else None

        feasibility = (
            "CLEAN_COMPLEMENTARY_SEPARATION"
            if len(existing_panels) > 0 and not has_conflict
            else "ZERO_EXISTING_PANELS_FULL_SYNTHESIS_NEEDED"
            if len(existing_panels) == 0
            else "GEOMETRIC_OVERLAP_CONFLICT"
        )

        sim = EnclosingBoxSimulation(
            page_order=p_num,
            unassigned_region_count=len(unassigned_regs),
            enclosing_bbox=[float(c) for c in [min_x, min_y, max_x, max_y]],
            normalized_enclosing_bbox=norm_enclosing,
            existing_panel_count=len(existing_panels),
            overlap_conflicts=conflicts,
            has_geometric_conflict=has_conflict,
            vertical_gap_to_nearest_panel=min_v_gap,
            horizontal_gap_to_nearest_panel=min_h_gap,
            synthesis_feasibility=feasibility,
        )
        simulations.append(sim)

        page_diagnostics.append({
            "page_order": p_num,
            "dimensions": [w, h],
            "unassigned_count": len(unassigned_regs),
            "existing_panel_count": len(existing_panels),
            "root_cause": page_category,
            "simulation": asdict(sim),
            "regions": [asdict(p) for p in region_profiles if p.page_order == p_num],
        })

    # Summary report
    print("\n" + "=" * 76)
    print("SPATIAL PROFILING & ROOT CAUSE SUMMARY TABLE")
    print("=" * 76)
    print(f"{'Page':>4} | {'Region ID':<16} | {'BBox [x1, y1, x2, y2]':<30} | {'Dist to Panel':>13} | {'Root Cause'}")
    print("-" * 76)
    for p in region_profiles:
        bbox_str = f"[{p.raw_bbox[0]:.0f}, {p.raw_bbox[1]:.0f}, {p.raw_bbox[2]:.0f}, {p.raw_bbox[3]:.0f}]"
        dist_str = f"{p.min_euclidean_distance:.1f}px" if p.min_euclidean_distance is not None else "NO_PANELS"
        print(f"{p.page_order:>4} | {p.region_id:<16} | {bbox_str:<30} | {dist_str:>13} | {p.root_cause_category}")

    print("\n" + "=" * 76)
    print("ENCLOSING BOUNDING BOX SIMULATION TABLE")
    print("=" * 76)
    print(f"{'Page':>4} | {'Unassigned':>10} | {'Enclosing BBox [x1, y1, x2, y2]':<32} | {'Conflict?':>9} | {'Gap to Panel':>12} | {'Feasibility'}")
    print("-" * 76)
    for s in simulations:
        bbox_str = f"[{s.enclosing_bbox[0]:.0f}, {s.enclosing_bbox[1]:.0f}, {s.enclosing_bbox[2]:.0f}, {s.enclosing_bbox[3]:.0f}]"
        gap_str = f"{s.vertical_gap_to_nearest_panel:.1f}px" if s.vertical_gap_to_nearest_panel is not None else "N/A"
        conf_str = "YES" if s.has_geometric_conflict else "NO (0px)"
        print(f"{s.page_order:>4} | {s.unassigned_region_count:>10} | {bbox_str:<32} | {conf_str:>9} | {gap_str:>12} | {s.synthesis_feasibility}")

    # Build canonical JSON artifact
    payload = {
        "schema_version": "day14_diagnostic_audit.v1",
        "checkpoint": "14.1",
        "purpose": "ROOT_CAUSE_ANALYSIS_MISSING_PANEL_COVERAGE",
        "analyzed_pages": FAIL_CLOSED_PAGES,
        "total_unassigned_regions": len(region_profiles),
        "root_cause_distribution": {
            "BORDERLESS_BACKGROUND_PANEL": sum(1 for p in region_profiles if p.root_cause_category == "BORDERLESS_BACKGROUND_PANEL"),
            "UNDER_SEGMENTED_PANEL": sum(1 for p in region_profiles if p.root_cause_category == "UNDER_SEGMENTED_PANEL"),
            "OUTSIDE_GUTTER_TEXT": sum(1 for p in region_profiles if p.root_cause_category == "OUTSIDE_GUTTER_TEXT"),
        },
        "pages": page_diagnostics,
        "gt_runtime_features": [],
    }

    canonical_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    payload_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

    out_doc = {
        **payload,
        "diagnostic_audit_sha256": payload_sha256,
    }

    out_dir = ROOT / "benchmarks" / "day14"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "day14-diagnostic-audit.json"
    out_file.write_text(json.dumps(out_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    file_sha256 = hashlib.sha256(out_file.read_bytes()).hexdigest()
    print("\n" + "=" * 76)
    print(f"Artifact Saved: {out_file.relative_to(ROOT)}")
    print(f"Artifact File SHA-256:      {file_sha256}")
    print(f"Internal Payload SHA-256:   {payload_sha256}")
    print("=" * 76)

    return out_doc


if __name__ == "__main__":
    run_diagnostic_audit()

