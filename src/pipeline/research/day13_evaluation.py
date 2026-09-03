"""Day 13 Research: End-to-End Realistic Track Evaluation & Blind Benchmark Harness.

Strict Methodological & Safety Constraints:
1. ZERO INVERSION INVARIANT: Inversion count must be strictly 0. Any inversion causes immediate failure.
2. NO THRESHOLD SWEEPING / NO FITTING: Fixed canonical parameters:
   - min_majority_ratio = Fraction(1, 2)
   - ambiguity_margin = Fraction(1, 10)
   - tolerance = 1-pixel exact / source-normalized (1/W, 1/H)
3. GT ISOLATION (BLIND AUDIT):
   - Candidate generation has zero access to Human reading order.
   - Evaluation matches Ground Truth only after candidate generation is fully frozen.
4. FAIL-CLOSED PRESERVATION: Pages with ambiguity or unassigned regions are strictly UNRESOLVED.
5. NO PRODUCTION MUTATION: Fully isolated in research pipeline.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.services.panel_aware_reading_order import (
    order_regions_in_panel,
    projection_constraint_order,
)
from src.pipeline.research.day13_assignment import DeterministicRegionAssigner
from src.pipeline.research.day13_harness import (
    Checkpoint128ExclusionBarrier,
    NormalizedBox,
)

BENCHMARK_PAGES: list[int] = [1, 2, 3, 4, 5, 7, 15, 17, 18, 38]


def pairs_from_sequence(seq: Sequence[str]) -> set[tuple[str, str]]:
    """Generate all ordered pairs (a, b) where a appears before b in seq."""
    return {(a, b) for i, a in enumerate(seq) for b in seq[i + 1:]}


class CandidateFreezeBarrier:
    """Barrier ensuring candidate generation is complete and frozen before GT matching."""

    def __init__(self) -> None:
        self.is_frozen = False
        self.gt_accessed = False

    def freeze_candidates(self) -> None:
        if self.gt_accessed:
            raise RuntimeError("Cannot freeze candidates: Ground Truth was accessed before freeze.")
        self.is_frozen = True

    def access_ground_truth(self) -> None:
        if not self.is_frozen:
            raise RuntimeError("Ground Truth access forbidden before candidate generation is frozen.")
        self.gt_accessed = True


class Day13RealisticEvaluator:
    """End-to-End Realistic Track Evaluator integrating PCPDAG V1 and Deterministic Assignment."""

    def __init__(
        self,
        min_majority_ratio: Fraction = Fraction(1, 2),
        ambiguity_margin: Fraction = Fraction(1, 10),
    ) -> None:
        self.assigner = DeterministicRegionAssigner(
            min_majority_ratio=min_majority_ratio,
            ambiguity_margin=ambiguity_margin,
        )

    def load_frozen_benchmark_inputs(
        self,
        root_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Load frozen realistic candidate inputs from Checkpoint 12.7 input audit.

        Passes through Checkpoint 12.8 Exclusion Barrier.
        """
        base = root_dir or ROOT
        audit_path = base / "benchmarks" / "day12" / "panel-relation-model-input-audit-12.7.json"
        
        # Enforce 12.8 exclusion barrier
        audit_doc = Checkpoint128ExclusionBarrier.safe_load_json(audit_path)

        pages_data = audit_doc["runtime_phase"]["pages"]
        loaded_pages: dict[int, dict[str, Any]] = {}
        for p in pages_data:
            p_order = p["page_order"]
            if p_order in BENCHMARK_PAGES:
                loaded_pages[p_order] = {
                    "page_order": p_order,
                    "source_hash": p["source_hash"],
                    "image_dimensions": tuple(p["image_dimensions"]),
                    "persisted_logical_regions": p["persisted_logical_regions"],
                    "realistic_selected_panels": p["realistic_selected_panels"],
                }

        if sorted(loaded_pages) != BENCHMARK_PAGES:
            raise RuntimeError(f"Cohort mismatch: expected {BENCHMARK_PAGES}, got {sorted(loaded_pages)}")

        return {
            "schema_version": "day13_realistic_inputs.v1",
            "pages": loaded_pages,
            "gt_runtime_features": [],
        }

    def generate_page_candidate(
        self,
        page_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate reading order for a single page deterministically without GT access."""
        p_num = page_info["page_order"]
        dims = page_info["image_dimensions"]

        # Step 1: Normalize boxes
        regs = [
            NormalizedBox(
                Decimal(str(r["bbox"][0])),
                Decimal(str(r["bbox"][1])),
                Decimal(str(r["bbox"][2])),
                Decimal(str(r["bbox"][3])),
                str(r["id"]),
            )
            for r in page_info["persisted_logical_regions"]
        ]
        pans = [
            NormalizedBox(
                Decimal(str(p["bbox"][0])),
                Decimal(str(p["bbox"][1])),
                Decimal(str(p["bbox"][2])),
                Decimal(str(p["bbox"][3])),
                str(p["panel_id"]),
            )
            for p in page_info["realistic_selected_panels"]
        ]

        # Step 2: Deterministic Region Assignment (Phase 2 Engine)
        ass = self.assigner.assign_regions(pans, regs)

        # Active panels: panels that contain at least 1 assigned region
        active_panel_ids = {
            pid for pid, r_list in ass.panel_to_regions.items() if len(r_list) > 0
        }

        # Step 3: Panel Ordering via PCPDAG V1
        pan_dicts = [
            {"panel_id": p.panel_id, "bbox": [float(p.x1), float(p.y1), float(p.x2), float(p.y2)]}
            for p in pans
        ]
        pan_order_res = projection_constraint_order(pan_dicts, dims, active_panel_ids)

        # Step 4: Intra-panel Region Ordering
        region_dict_map = {
            r.panel_id: {"id": r.panel_id, "bbox": [float(r.x1), float(r.y1), float(r.x2), float(r.y2)]}
            for r in regs
        }
        grouped = {
            pid: [region_dict_map[rid] for rid in r_list]
            for pid, r_list in ass.panel_to_regions.items()
        }
        local_order = {
            pid: order_regions_in_panel(items)
            for pid, items in grouped.items()
        }

        # Step 5: Full Candidate Assembly (Fail-closed on panel conflict or region ambiguity)
        has_ambiguity = len(ass.ambiguous_region_ids) > 0
        has_unassigned = len(ass.unassigned_region_ids) > 0
        panels_resolved = pan_order_res["resolved"]

        candidate_resolved = panels_resolved and not has_ambiguity and not has_unassigned
        raw_sequence: list[str] = []
        if candidate_resolved:
            for pid in pan_order_res["order"]:
                raw_sequence.extend(local_order[pid]["order"])

        return {
            "page_order": p_num,
            "source_hash": page_info["source_hash"],
            "image_dimensions": list(dims),
            "candidate_resolved": candidate_resolved,
            "raw_predicted_sequence": raw_sequence,
            "panel_order_result": pan_order_res,
            "assignment_result": ass.to_dict(),
            "intra_panel_order": local_order,
            "gt_runtime_features": [],
        }

    def generate_all_candidates(
        self,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate blind candidate reading orders for all benchmark pages."""
        pages = inputs["pages"]
        candidate_pages: list[dict[str, Any]] = []
        for p_num in BENCHMARK_PAGES:
            cand = self.generate_page_candidate(pages[p_num])
            candidate_pages.append(cand)

        payload = {
            "schema_version": "day13_realistic_candidates.v1",
            "track": "REALISTIC_TRACK_PCPDAG_V1",
            "candidate_count": len(candidate_pages),
            "pages": candidate_pages,
            "gt_runtime_features": [],
        }

        canonical_bytes = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        return {
            **payload,
            "candidate_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        }

    def evaluate_against_ground_truth(
        self,
        candidates_doc: dict[str, Any],
        barrier: CandidateFreezeBarrier,
        root_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Post-freeze blind evaluation against Human Reading Order Ground Truth.

        Computes Exact Pages, Resolved Regions, Pairwise Coverage, and Inversions.
        """
        barrier.access_ground_truth()

        base = root_dir or ROOT
        gt_path = base / "benchmarks" / "day11" / "reader-order-control-11.16.json"
        gt_doc = Checkpoint128ExclusionBarrier.safe_load_json(gt_path)

        humans: dict[int, list[str]] = {
            p["page_order"]: p["human"] for p in gt_doc["pages"]
        }

        page_evaluations: list[dict[str, Any]] = []
        total_exact = 0
        total_resolved_regions = 0
        total_correct_pairs = 0
        total_denom_pairs = 0
        total_population_pairs = 0
        total_inversions = 0
        cross_panel_inversions = 0
        intra_panel_inversions = 0

        unassigned_total = 0
        ambiguous_total = 0
        assigned_total = 0

        for cand in candidates_doc["pages"]:
            p_num = cand["page_order"]
            human_seq = humans[p_num]
            human_set = set(human_seq)

            ass_data = cand["assignment_result"]
            panel_order_res = cand["panel_order_result"]

            # Filter eval-eligible regions (those verified in GT)
            assigned_eval = [
                r for r in ass_data["assigned_records"]
                if r["region_id"] in human_set and r["status"] in ("ASSIGNED_CONTAINED", "ASSIGNED_MAJORITY")
            ]
            amb_eval = [rid for rid in ass_data["ambiguous_region_ids"] if rid in human_set]
            un_eval = [rid for rid in ass_data["unassigned_region_ids"] if rid in human_set]

            assigned_total += len(assigned_eval)
            ambiguous_total += len(amb_eval)
            unassigned_total += len(un_eval)

            # Check resolution for eval-eligible subset
            page_resolved = panel_order_res["resolved"] and not amb_eval and not un_eval
            prediction: list[str] = []

            if page_resolved:
                for pid in panel_order_res["order"]:
                    panel_seq = cand["intra_panel_order"].get(pid, {}).get("order", [])
                    prediction.extend([rid for rid in panel_seq if rid in human_set])

                # Integrity check: prediction must contain exactly all human regions
                if sorted(prediction) != sorted(human_seq):
                    page_resolved = False
                    prediction = []

            hp = pairs_from_sequence(human_seq)
            pp = pairs_from_sequence(prediction)
            inversions = (hp - pp) if page_resolved else set()
            correct_pairs = len(hp & pp)

            is_exact = page_resolved and (prediction == human_seq)
            if is_exact:
                total_exact += 1

            total_resolved_regions += len(prediction)
            total_correct_pairs += correct_pairs
            if page_resolved:
                total_denom_pairs += len(hp)
            total_population_pairs += len(hp)
            total_inversions += len(inversions)

            blocker = (
                "RESOLVED"
                if page_resolved
                else "MISSING_PANEL_COVERAGE"
                if un_eval
                else "ASSIGNMENT_AMBIGUITY"
                if amb_eval
                else "PANEL_ORDER_AMBIGUOUS"
            )

            page_evaluations.append({
                "page_order": p_num,
                "resolved": page_resolved,
                "exact": is_exact,
                "prediction": prediction,
                "human": human_seq,
                "eval_eligible_regions": len(human_seq),
                "assigned_regions": len(assigned_eval),
                "ambiguous_regions": len(amb_eval),
                "unassigned_regions": len(un_eval),
                "population_pairs": len(hp),
                "resolved_pairs": len(hp) if page_resolved else 0,
                "correct_pairs": correct_pairs,
                "confident_inversions": len(inversions),
                "blocker": blocker,
                "ambiguous_region_ids": amb_eval,
                "unassigned_region_ids": un_eval,
            })

        summary = {
            "track": "DAY13_REALISTIC_TRACK",
            "exact_pages": [total_exact, len(BENCHMARK_PAGES)],
            "resolved_pages": sum(p["resolved"] for p in page_evaluations),
            "unresolved_pages": sum(not p["resolved"] for p in page_evaluations),
            "resolved_regions": [total_resolved_regions, 50],
            "resolved_comparable_pairwise": [total_correct_pairs, total_denom_pairs],
            "population_pair_coverage": [total_denom_pairs, total_population_pairs],
            "confident_inversions": total_inversions,
            "assignment_distribution": {
                "assigned": assigned_total,
                "ambiguous": ambiguous_total,
                "unassigned": unassigned_total,
                "total": assigned_total + ambiguous_total + unassigned_total,
            },
            "blocker_summary": {
                "resolved": sum(p["blocker"] == "RESOLVED" for p in page_evaluations),
                "missing_panel_coverage": sum(p["blocker"] == "MISSING_PANEL_COVERAGE" for p in page_evaluations),
                "assignment_ambiguity": sum(p["blocker"] == "ASSIGNMENT_AMBIGUITY" for p in page_evaluations),
                "panel_order_ambiguous": sum(p["blocker"] == "PANEL_ORDER_AMBIGUOUS" for p in page_evaluations),
            },
            "gt_runtime_features": [],
        }

        eval_result = {
            "schema_version": "day13_realistic_evaluation.v1",
            "summary": summary,
            "pages": page_evaluations,
            "gt_runtime_features": [],
        }

        canonical_bytes = json.dumps(
            eval_result,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        eval_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

        return {
            **eval_result,
            "evaluation_sha256": eval_sha256,
        }

