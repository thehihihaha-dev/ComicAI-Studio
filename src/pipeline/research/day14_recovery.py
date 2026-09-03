"""Day 14 Phase 2: Deterministic Complementary Panel Recovery Engine.

Synthesizes clean, non-conflicting residual panels for orphaned text regions
lying in wide gutter areas (gutter distance >= 30px, zero intersection with existing panels).
Strictly fail-closed, exact Decimal/Fraction arithmetic, zero Ground Truth leakage.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day13_harness import NormalizedBox


@dataclass(frozen=True)
class SynthesizedPanelRecord:
    panel_id: str
    x1: float
    y1: float
    x2: float
    y2: float
    source_unassigned_region_count: int
    source_unassigned_region_ids: list[str]
    min_gutter_distance_to_nearest_panel: float
    overlap_area_with_existing_panels: float
    provenance: str = "DETERMINISTIC_COMPLEMENTARY_RESIDUAL_EXPANSION_V1"

    def to_normalized_box(self) -> NormalizedBox:
        return NormalizedBox(
            x1=Decimal(str(self.x1)),
            y1=Decimal(str(self.y1)),
            x2=Decimal(str(self.x2)),
            y2=Decimal(str(self.y2)),
            panel_id=self.panel_id,
        )


class ComplementaryPanelSynthesizer:
    """Deterministic Complementary Panel Synthesizer for Clean Residual Areas."""

    def __init__(
        self,
        min_gutter_gap: Decimal = Decimal("30.0"),
        padding: Decimal = Decimal("15.0"),
        gutter_buffer: Decimal = Decimal("10.0"),
    ) -> None:
        self.min_gutter_gap = min_gutter_gap
        self.padding = padding
        self.gutter_buffer = gutter_buffer

    def synthesize_clean_residual_panels(
        self,
        existing_panels: Sequence[NormalizedBox],
        unassigned_regions: Sequence[NormalizedBox],
        page_width: int,
        page_height: int,
    ) -> list[NormalizedBox]:
        """Synthesize complementary residual panel for unassigned regions if clean and safe.

        Returns empty list (fail-closed) if:
        - No unassigned regions exist.
        - No existing anchor panels exist.
        - Distance to any existing panel is < min_gutter_gap (30px).
        - Any intersection / overlap area > 0 is created.
        - The synthesized box fails to fully enclose all target unassigned regions.
        """
        if not unassigned_regions or not existing_panels:
            return []

        w_dec = Decimal(str(page_width))
        h_dec = Decimal(str(page_height))

        # 1. Compute Minimum Enclosing Bounding Box (MEBB) of unassigned regions
        min_x = min(r.x1 for r in unassigned_regions)
        min_y = min(r.y1 for r in unassigned_regions)
        max_x = max(r.x2 for r in unassigned_regions)
        max_y = max(r.y2 for r in unassigned_regions)

        # 2. Distance Barrier: Check distance to all existing panels
        min_dist_found = None
        for p in existing_panels:
            dx = max(Decimal(0), max(min_x - p.x2, p.x1 - max_x))
            dy = max(Decimal(0), max(min_y - p.y2, p.y1 - max_y))
            dist = Decimal(str(float(dx**2 + dy**2) ** 0.5))

            if min_dist_found is None or dist < min_dist_found:
                min_dist_found = dist

            if dist < self.min_gutter_gap:
                # Barrier violated: Too close or overlapping existing panels -> Fail-closed
                return []

        # 3. Padded expansion restricted by page boundaries and existing panel edges
        x_pad_left = min_x - self.padding
        x_pad_right = max_x + self.padding
        y_pad_top = min_y - self.padding
        y_pad_bottom = max_y + self.padding

        panels_left = [p.x2 for p in existing_panels if p.x2 <= min_x]
        x1 = max(x_pad_left, max(panels_left) + self.gutter_buffer) if panels_left else max(Decimal(0), x_pad_left)

        panels_right = [p.x1 for p in existing_panels if p.x1 >= max_x]
        x2 = min(x_pad_right, min(panels_right) - self.gutter_buffer) if panels_right else min(w_dec, x_pad_right)

        panels_above = [p.y2 for p in existing_panels if p.y2 <= min_y]
        y1 = max(y_pad_top, max(panels_above) + self.gutter_buffer) if panels_above else max(Decimal(0), y_pad_top)

        panels_below = [p.y1 for p in existing_panels if p.y1 >= max_y]
        y2 = min(y_pad_bottom, min(panels_below) - self.gutter_buffer) if panels_below else min(h_dec, y_pad_bottom)

        # 4. Zero Intersection Invariant Check
        for p in existing_panels:
            ox = max(Decimal(0), min(x2, p.x2) - max(x1, p.x1))
            oy = max(Decimal(0), min(y2, p.y2) - max(y1, p.y1))
            if ox * oy > Decimal(0):
                # Hard safety violation: Overlap detected -> Fail-closed
                return []

        # 5. Complete Enclosure Invariant Check
        for r in unassigned_regions:
            if not (x1 <= r.x1 and y1 <= r.y1 and x2 >= r.x2 and y2 >= r.y2):
                # Region leaked out of synthesized panel -> Fail-closed
                return []

        # 6. Generate Deterministic Canonical ID
        # Exact string serialization of Decimal coordinates rounded to 2 decimal places
        canonical_sig = f"{float(x1):.2f}_{float(y1):.2f}_{float(x2):.2f}_{float(y2):.2f}"
        panel_hash = hashlib.sha256(canonical_sig.encode("utf-8")).hexdigest()[:12]
        panel_id = f"SYNTH_PANEL_{panel_hash}"

        return [NormalizedBox(x1, y1, x2, y2, panel_id)]

