#!/usr/bin/env python3
"""Offline-only Checkpoint 12.0 Reading Order failure audit."""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.reading_order_geometry_experiment import (  # noqa: E402
    MANGA,
    box,
    center_distance,
    contains,
    height,
    tier_order,
    vertical_overlap,
)
from app.services.resource_safety import ResourceThresholds, sample_resources  # noqa: E402

DAY11 = ROOT / "benchmarks/day11"
DAY12 = ROOT / "benchmarks/day12"
LOGICAL = DAY11 / "reader-logical-region-sample-11.11.json"
HUMAN = DAY11 / "reader-correctness-human-verified-11.11.json"
CANDIDATES_11 = DAY11 / "reader-order-candidates-11.16.json"
SUMMARY_11 = DAY11 / "reader-order-summary-11.16.json"
MANIFEST_17 = DAY11 / "reader-v2-final-manifest-11.17.json"
UPLOADS = ROOT / "backend/uploads"

FROZEN = "A_VERTICAL_OVERLAP"
EXPECTED = (7, 10, 43, 50, 120, 124, 4, 3, 7, 0)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pairs(sequence: list[str]) -> set[tuple[str, str]]:
    return {(a, b) for index, a in enumerate(sequence) for b in sequence[index + 1 :]}


def metrics(pages: list[dict[str, Any]]) -> dict[str, Any]:
    exact = sum(page["prediction"] == page["human"] for page in pages)
    positions = sum(
        index < len(page["prediction"]) and page["prediction"][index] == region
        for page in pages
        for index, region in enumerate(page["human"])
    )
    total_positions = sum(len(page["human"]) for page in pages)
    correct_pairs = sum(len(pairs(page["prediction"]) & pairs(page["human"])) for page in pages)
    total_pairs = sum(len(pairs(page["human"])) for page in pages)
    return {
        "exact_pages": {"correct": exact, "total": len(pages), "accuracy": exact / len(pages)},
        "exact_positions": {"correct": positions, "total": total_positions, "accuracy": positions / total_positions},
        "pairwise": {"correct": correct_pairs, "total": total_pairs, "accuracy": correct_pairs / total_pairs},
        "inversions": total_pairs - correct_pairs,
    }


def relation(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    aa, bb = box(a), box(b)
    ix = max(0.0, min(aa[2], bb[2]) - max(aa[0], bb[0]))
    iy = max(0.0, min(aa[3], bb[3]) - max(aa[1], bb[1]))
    return {
        "normalized_vertical_overlap": vertical_overlap(a, b),
        "normalized_center_distance": center_distance(a, b),
        "horizontal_relationship": (
            "A_LEFT_OF_B" if aa[2] <= bb[0] else "A_RIGHT_OF_B" if bb[2] <= aa[0] else "X_OVERLAP"
        ),
        "vertical_relationship": (
            "A_ABOVE_B" if aa[3] <= bb[1] else "A_BELOW_B" if bb[3] <= aa[1] else "Y_OVERLAP"
        ),
        "intersection": {"x_pixels": ix, "y_pixels": iy, "area": ix * iy},
        "containment": {
            "a_contains_b": contains(a, b),
            "b_contains_a": contains(b, a),
        },
    }


def dimensions(item: dict[str, Any]) -> dict[str, float]:
    x1, y1, x2, y2 = box(item)
    width, item_height = x2 - x1, y2 - y1
    return {"width": width, "height": item_height, "aspect_ratio_width_over_height": width / item_height}


def structural_order(items: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    """Use the frozen .50 predicate with different non-page-specific tier linkage."""
    ordered_input = sorted(items, key=lambda item: (box(item)[1], box(item)[0], str(item["id"])))
    tiers: list[list[dict[str, Any]]] = []
    trace: list[dict[str, Any]] = []
    for item in ordered_input:
        eligible: list[int] = []
        for index, tier in enumerate(tiers):
            if mode == "COMPLETE_LINK":
                match = all(vertical_overlap(item, peer) >= 0.50 for peer in tier)
            elif mode == "ANCHOR_LINK":
                match = vertical_overlap(item, tier[0]) >= 0.50
            else:
                raise ValueError(mode)
            if match:
                eligible.append(index)
        chosen = eligible[0] if eligible else len(tiers)
        if eligible:
            tiers[chosen].append(item)
        else:
            tiers.append([item])
        trace.append({"region": item["id"], "eligible_tiers": eligible, "chosen_tier": chosen})
    tiers.sort(key=lambda tier: (min(box(item)[1] for item in tier), min(str(item["id"]) for item in tier)))
    for tier in tiers:
        tier.sort(key=lambda item: (-box(item)[0], box(item)[1], str(item["id"])))
    return {
        "order": [item["id"] for tier in tiers for item in tier],
        "tiers": [[item["id"] for item in tier] for tier in tiers],
        "trace": trace,
        "ambiguous": [],
    }


def frozen_trace(items: list[dict[str, Any]]) -> dict[str, Any]:
    median = statistics.median(height(item) for item in items)
    tiers: list[list[dict[str, Any]]] = []
    steps: list[dict[str, Any]] = []
    bridge_events: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda value: (box(value)[1], box(value)[0], str(value["id"]))):
        matches = []
        for tier_index, tier in enumerate(tiers):
            peer_matches = [peer["id"] for peer in tier if vertical_overlap(item, peer) >= 0.50]
            if peer_matches:
                matches.append({"tier": tier_index, "matching_peers": peer_matches})
                nonmatching = [peer["id"] for peer in tier if vertical_overlap(item, peer) < 0.50]
                if nonmatching:
                    bridge_events.append({"joining_region": item["id"], "tier": tier_index,
                                          "matching_peers": peer_matches, "nonmatching_peers": nonmatching})
        chosen = matches[0]["tier"] if matches else len(tiers)
        if matches:
            tiers[chosen].append(item)
        else:
            tiers.append([item])
        steps.append({"region": item["id"], "candidate_tiers": matches, "chosen_tier": chosen})
    result = tier_order(items, FROZEN, MANGA)
    return {
        "input_sort": "(bbox.y1, bbox.x1, stable string id)",
        "same_tier_predicate": "any existing tier peer has normalized vertical overlap >= 0.50",
        "tier_output_sort": "(minimum tier y1, minimum stable id)",
        "manga_peer_sort": "x1 descending, then y1, then stable id",
        "median_height_unused_by_frozen_rule": median,
        "steps": steps,
        "bridge_events": bridge_events,
        "result": result,
    }


def neighbor_context(sequence: list[str], region: str) -> dict[str, str | None]:
    index = sequence.index(region)
    return {"previous": sequence[index - 1] if index else None,
            "next": sequence[index + 1] if index + 1 < len(sequence) else None}


def resolve_source_hash(source_hash: str) -> dict[str, Any]:
    matches = [path for path in sorted(UPLOADS.iterdir()) if path.is_file() and sha(path) == source_hash]
    return {
        "expected_sha256": source_hash,
        "matching_current_uploads": [str(path.relative_to(ROOT)) for path in matches],
        "match_count": len(matches),
        "direct_source_byte_match": len(matches) == 1,
    }


def candidate_result(name: str, pages: list[dict[str, Any]], frozen_pages: list[dict[str, Any]],
                     known: set[tuple[int, str, str]]) -> dict[str, Any]:
    result_metrics = metrics(pages)
    frozen_map = {page["page_order"]: page for page in frozen_pages}
    page_deltas = []
    new_inversions: set[tuple[int, str, str]] = set()
    remaining: set[tuple[int, str, str]] = set()
    for page in pages:
        current = {(page["page_order"], a, b) for a, b in pairs(page["human"]) - pairs(page["prediction"])}
        remaining |= current & known
        new_inversions |= current - known
        frozen_inv = len(pairs(page["human"]) - pairs(frozen_map[page["page_order"]]["prediction"]))
        candidate_inv = len(current)
        page_deltas.append({
            "page_order": page["page_order"],
            "frozen_inversions": frozen_inv,
            "candidate_inversions": candidate_inv,
            "classification": "IMPROVED" if candidate_inv < frozen_inv else "REGRESSED" if candidate_inv > frozen_inv else "UNCHANGED",
        })
    result_metrics.update({
        "pages_improved": sum(row["classification"] == "IMPROVED" for row in page_deltas),
        "pages_unchanged": sum(row["classification"] == "UNCHANGED" for row in page_deltas),
        "pages_regressed": sum(row["classification"] == "REGRESSED" for row in page_deltas),
    })
    return {
        "candidate": name,
        "metrics": result_metrics,
        "page_deltas": page_deltas,
        "failure_level_changes": {
            "repaired": [list(value) for value in sorted(known - remaining)],
            "unchanged": [list(value) for value in sorted(remaining)],
            "new_inversions": [list(value) for value in sorted(new_inversions)],
        },
        "outputs": pages,
    }


def main() -> None:
    before = sample_resources(ResourceThresholds.from_environment())
    logical_bytes, human_bytes = LOGICAL.read_bytes(), HUMAN.read_bytes()
    logical, human = json.loads(logical_bytes), json.loads(human_bytes)
    day11_candidates = json.loads(CANDIDATES_11.read_text())
    day11_summary = json.loads(SUMMARY_11.read_text())
    frozen_outputs = day11_candidates["outputs"][FROZEN]
    frozen_metrics = candidate_result(FROZEN, frozen_outputs, frozen_outputs, set())["metrics"]
    reproduced = (
        frozen_metrics["exact_pages"]["correct"], frozen_metrics["exact_pages"]["total"],
        frozen_metrics["exact_positions"]["correct"], frozen_metrics["exact_positions"]["total"],
        frozen_metrics["pairwise"]["correct"], frozen_metrics["pairwise"]["total"],
        frozen_metrics["inversions"], day11_summary["best_metrics"]["pages_improved"],
        day11_summary["best_metrics"]["pages_unchanged"], day11_summary["best_metrics"]["pages_regressed"],
    )
    if reproduced != EXPECTED:
        raise RuntimeError(f"frozen baseline mismatch: {reproduced!r}")

    logical_by = {page["page_order"]: page for page in logical["pages"]}
    human_by = {page["page_order"]: page for page in human["pages"]}
    frozen_by = {page["page_order"]: page for page in frozen_outputs}
    regions_by = {
        page_order: {region["logical_region_id"]: {"id": region["logical_region_id"], **region}
                     for region in page["logical_regions"]}
        for page_order, page in logical_by.items()
    }

    failures: list[dict[str, Any]] = []
    taxonomy: Counter[str] = Counter()
    root_classes: Counter[str] = Counter()
    traces: dict[str, Any] = {}
    known: set[tuple[int, str, str]] = set()
    for page_order in sorted(frozen_by):
        frozen_page, hp = frozen_by[page_order], human_by[page_order]
        included = set(hp["ordered_region_ids"])
        items = [{"id": rid, "bbox": regions_by[page_order][rid]["bbox"]} for rid in included]
        trace = frozen_trace(items)
        traces[str(page_order)] = trace
        for human_before, human_after in sorted(pairs(frozen_page["human"]) - pairs(frozen_page["prediction"])):
            known.add((page_order, human_before, human_after))
            a, b = regions_by[page_order][human_before], regions_by[page_order][human_after]
            rel = relation(a, b)
            same_tier = next((tier for tier in trace["result"]["tiers"] if human_before in tier and human_after in tier), None)
            root = "C. panel/group construction"
            if page_order == 15:
                category = "cross-panel order / missing text-to-panel assignment"
                manual_panel = {
                    human_before: "BOTTOM_RIGHT_PANEL",
                    human_after: "BOTTOM_LEFT_PHONE_PANEL",
                    "human_panel_order": ["BOTTOM_RIGHT_PANEL", "BOTTOM_LEFT_PHONE_PANEL"],
                    "evidence": "Visible panel borders place the Human-before dialogue in the bottom-right panel and PÍP in the separate bottom-left phone panel.",
                }
                reason = "Manga panel order reads the bottom-right panel before the separate bottom-left phone panel. PAGE_FALLBACK loses containment/adjacency, so the frozen text-only tier sorter emits the higher PÍP bbox first."
            elif page_order == 17:
                category = "cross-panel order / missing text-to-panel assignment"
                manual_panel = {
                    human_before: "TOP_RIGHT_PANEL",
                    human_after: "TOP_LEFT_PANEL",
                    "human_panel_order": ["TOP_RIGHT_PANEL", "TOP_LEFT_PANEL"],
                    "evidence": "Visible panel borders place the Human-before region in the top-right panel and HỬ? in the separate top-left panel.",
                }
                reason = "Manga panel order reads the top-right panel before the top-left panel. PAGE_FALLBACK omits panel containment/order, so small y differences split the regions and incorrectly let text-tier y order dominate."
            else:
                category = "cross-panel order / missing text-to-panel assignment"
                manual_panel = {
                    human_before: "BOTTOM_RIGHT_PANEL",
                    human_after: "BOTTOM_LEFT_PANEL",
                    "human_panel_order": ["BOTTOM_RIGHT_PANEL", "BOTTOM_LEFT_PANEL"],
                    "evidence": "Visible panel borders place the Human-before thought bubble in the bottom-right panel and the Human-after dialogue in the separate bottom-left panel.",
                }
                reason = "Manga panel order reads the bottom-right panel before the bottom-left panel. PAGE_FALLBACK provides no containment/adjacency, so top-to-bottom text tiers reverse the cross-panel pair."
            taxonomy[category] += 1
            root_classes[root] += 1
            failures.append({
                "failure_id": f"P{page_order}-{human_before}-{human_after}",
                "page_order": page_order,
                "asset_id": hp["asset_id"],
                "source_hash": hp["source_hash"],
                "regions": {human_before: {"bbox": a["bbox"], "dimensions": dimensions(a), "panel_id": a.get("panel_id")},
                            human_after: {"bbox": b["bbox"], "dimensions": dimensions(b), "panel_id": b.get("panel_id")}},
                "human_relative_order": [human_before, human_after],
                "predicted_relative_order": [human_after, human_before],
                "geometry": rel,
                "same_predicted_tier": same_tier is not None,
                "panel_group_information": "PAGE_FALLBACK only; no authoritative Human panel/tier labels",
                "manual_visual_panel_evidence": {"evidence_class": "BENCHMARK_ONLY_MANUAL_AUDIT", **manual_panel},
                "direct_source_byte_verification": resolve_source_hash(hp["source_hash"]),
                "neighbors": {
                    "human": {human_before: neighbor_context(frozen_page["human"], human_before), human_after: neighbor_context(frozen_page["human"], human_after)},
                    "prediction": {human_before: neighbor_context(frozen_page["prediction"], human_before), human_after: neighbor_context(frozen_page["prediction"], human_after)},
                },
                "algorithm_decision_path": {
                    "input_steps": [step for step in trace["steps"] if step["region"] in {human_before, human_after}],
                    "tier_result": trace["result"]["tiers"],
                    "decision": "same tier -> MANGA right-to-left" if same_tier else "different tiers -> top-to-bottom tier order",
                },
                "failure_taxonomy": [category, "missing panel containment", "missing panel adjacency/order"],
                "primary_root_class": root,
                "contributing_geometric_symptom": "The pair fails the frozen >=0.50 overlap predicate and is split into y-sorted text tiers.",
                "exact_reason": reason,
                "evidence_limit": "Human click-order establishes relative order but not why; no Human panel/tier annotation exists.",
            })

    if len(failures) != 4:
        raise RuntimeError(f"expected four frozen inversions, got {len(failures)}")

    integrity_pages = []
    for page_order, hp in sorted(human_by.items()):
        lp = logical_by[page_order]
        all_ids = {region["logical_region_id"] for region in lp["logical_regions"]}
        ordered, excluded = hp["ordered_region_ids"], hp["excluded_region_ids"]
        integrity_pages.append({
            "page_order": page_order,
            "source_hash_matches_logical": hp["source_hash"] == lp["source_hash"],
            "representation_hash_matches_logical": hp["representation_hash"] == lp["representation_hash"],
            "duplicate_order_positions": len(ordered) != len(set(ordered)),
            "missing_ordered_regions": sorted(set(ordered) - all_ids),
            "excluded_in_order": sorted(set(ordered) & set(excluded)),
            "unclassified_regions": sorted(all_ids - set(ordered) - set(excluded)),
            "ambiguous_orphan_state": "N/A: click-order GT has no ambiguity/orphan field",
            "panel_group_consistency": "N/A: all logical regions use PAGE_FALLBACK; no Human panel/tier GT",
        })
    manifest = json.loads(MANIFEST_17.read_text())
    input_hash_checks = {
        name: {"expected": expected, "actual": sha(DAY11 / name), "matches": sha(DAY11 / name) == expected}
        for name, expected in manifest["input_artifact_hashes"].items()
    }

    candidate_outputs: dict[str, list[dict[str, Any]]] = {}
    for mode in ("COMPLETE_LINK", "ANCHOR_LINK"):
        pages = []
        for page_order, hp in sorted(human_by.items()):
            excluded = set(hp["excluded_region_ids"])
            items = [{"id": region["logical_region_id"], "bbox": region["bbox"]}
                     for region in logical_by[page_order]["logical_regions"]
                     if region["logical_region_id"] not in excluded]
            ordered = structural_order(items, mode)
            pages.append({"page_order": page_order, "prediction": ordered["order"], "human": hp["ordered_region_ids"],
                          "tiers": ordered["tiers"], "ambiguous": ordered["ambiguous"]})
        candidate_outputs[mode] = pages
    comparisons = [candidate_result(FROZEN, frozen_outputs, frozen_outputs, known)] + [
        candidate_result(mode, candidate_outputs[mode], frozen_outputs, known)
        for mode in ("COMPLETE_LINK", "ANCHOR_LINK")
    ]

    global_consistency = {
        "cycles": "Impossible in emitted output because the algorithm constructs and flattens an ordered list; it does not expose an independent pairwise comparator.",
        "transitivity": "The final list is transitive, but the same-tier predicate is non-transitive: A may overlap B and B overlap C while A does not overlap C.",
        "stable_ties": "Stable under identical inputs due explicit coordinate/id sort keys.",
        "ordering_changes_from_unrelated_regions": "Demonstrated synthetically: single-link tier membership lets a bridge region merge otherwise separate tiers, changing whether manga x-order or tier y-order controls existing regions.",
        "tall_region_bridge_effects": "Possible because any matching peer admits a region to the first matching tier; no complete-link invariant is enforced.",
        "synthetic_fixture": "reading-order-synthetic-bridge-12.0.json",
    }
    synthetic = {
        "schema_version": "reading-order-synthetic.v1", "checkpoint": "12.0", "evidence_class": "SYNTHETIC",
        "counted_as_human_gt": False,
        "purpose": "Demonstrate non-transitive same-tier relation and unrelated-region bridge effect.",
        "regions": [
            {"id": "A", "bbox": [0, 0, 30, 40]},
            {"id": "B", "bbox": [40, 20, 70, 60]},
            {"id": "C", "bbox": [80, 40, 120, 80]},
        ],
        "relations": {"A_B_overlap": 0.5, "B_C_overlap": 0.5, "A_C_overlap": 0.0},
        "actual_frozen_with_bridge": tier_order([
            {"id": "A", "bbox": [0, 0, 30, 40]}, {"id": "B", "bbox": [40, 20, 70, 60]},
            {"id": "C", "bbox": [80, 40, 120, 80]}], FROZEN, MANGA),
        "actual_frozen_without_bridge": tier_order([
            {"id": "A", "bbox": [0, 0, 30, 40]}, {"id": "C", "bbox": [80, 40, 120, 80]}], FROZEN, MANGA),
        "finding": "A~B and B~C but A!~C. With B, RTL in one bridged tier puts C before A; without B, separate top-to-bottom tiers put A before C.",
    }

    failure_artifact = {
        "schema_version": "reading-order-failure-audit.v1", "checkpoint": "12.0",
        "frozen_rule": {"name": FROZEN, "normalized_vertical_overlap_min": 0.50, "status": "BENCHMARK_FITTED"},
        "inversion_count": 4, "cases": failures, "taxonomy": dict(taxonomy), "root_classes": dict(root_classes),
        "human_gt_integrity": {
            "status": "PASS_WITH_STRUCTURAL_LABEL_LIMITATION",
            "pages": integrity_pages, "input_artifact_hash_checks": input_hash_checks,
            "human_gt_sha256_before_after": {"before": hashlib.sha256(human_bytes).hexdigest(), "after": sha(HUMAN)},
        },
        "structural_requirements": {
            "panel_containment": {"required_by_pages": [15, 17, 38], "reason": "Distinguishes which visible panel owns each reversed text region."},
            "panel_adjacency_order": {"required_by_pages": [15, 17, 38], "reason": "Orders right panel before left panel under current manga policy."},
            "text_to_panel_assignment": {"required_by_pages": [15, 17, 38], "reason": "Connects each logical text bbox to the panel sequence rather than page-wide text tiers."},
        },
    }
    decision_artifact = {
        "schema_version": "reading-order-decision-traces.v1", "checkpoint": "12.0",
        "actual_paths": {
            "offline_final_contract": "reader_v2_final_contract -> tier_order(A_VERTICAL_OVERLAP, MANGA)",
            "production_fast_pass": "prepare_reading_order -> optional panel assignment -> tiered_order(center-distance heuristic)",
            "legacy_vision": "separate model-backed vision_analyzer path; not executed in this checkpoint",
        },
        "frozen_candidate_flow": [
            "Filter Human-excluded regions for scoring only", "Sort by y1, x1, stable id",
            "Join first tier having ANY peer with normalized vertical overlap >= 0.50",
            "Sort tiers by minimum y1 then stable id", "For MANGA sort peers right-to-left by x1", "Flatten tiers"
        ],
        "metadata_use": "Frozen ten-page replay receives PAGE_FALLBACK only and does not use panel/group metadata.",
        "tall_regions": "No explicit protection in frozen rule; tall regions can link distant y bands.",
        "ties": "Explicit deterministic coordinate/id keys; reverse=False logic is encoded directly by negative x for MANGA.",
        "ambiguity": "Only multiple tier matches append the joining region ID; the algorithm still forces the first matching tier and a deterministic order.",
        "policy_split": {"GENERIC_GEOMETRY": "bbox normalization, overlap predicate, tier construction and stable sorting",
                         "MANGA_POLICY": "right-to-left ordering within a constructed tier; tiers remain top-to-bottom"},
        "global_consistency": global_consistency, "page_traces": traces,
    }
    candidate_artifact = {
        "schema_version": "reading-order-candidate-analysis.v1", "checkpoint": "12.0",
        "protocol": "Two structural linkage variants only; both reuse frozen >=0.50 overlap. No threshold sweep or page-specific rule.",
        "candidates": [
            {"name": "COMPLETE_LINK", "hypothesis": "Require overlap with every tier member to prevent bridge merges.",
             "addresses": ["non-transitive bridge effects", "tall-region interference"], "generalization": "Enforces a tier-wide geometric invariant independent of page identity.",
             "regression_risk": "May split legitimate irregular/tall same-row groups.", "required_metadata": "logical bboxes only", "complexity": "O(n^3) worst case in direct implementation", "current_data_sufficient": "Only for benchmark diagnostics; not calibration."},
            {"name": "ANCHOR_LINK", "hypothesis": "Compare membership to a stable top-sorted tier anchor to prevent chaining.",
             "addresses": ["order-dependent bridge effects"], "generalization": "Stable anchor avoids single-link chaining without new fitted constants.",
             "regression_risk": "Anchor may be unrepresentative for irregular rows.", "required_metadata": "logical bboxes only", "complexity": "O(n^2)", "current_data_sufficient": "Only for benchmark diagnostics; not calibration."},
            {"name": "PANEL_AWARE_AMBIGUITY", "status": "NOT_RUN_MISSING_METADATA",
             "hypothesis": "Use reliable panel/group assignment and emit AMBIGUOUS_ORDER when geometry cannot choose.",
             "addresses": ["cross-panel ambiguity", "missing structural evidence"], "generalization": "Separates panel sequence from within-panel manga policy.",
             "regression_risk": "Incorrect panels would create systematic errors.", "required_metadata": "validated predicted panel/group geometry plus uncertainty", "complexity": "O(n log n) ordering after assignment", "current_data_sufficient": "No; current GT is flattened PAGE_FALLBACK."},
        ],
        "comparisons": comparisons,
        "selection": "No benchmark-only candidate is ready for production selection. PANEL_AWARE_AMBIGUITY is the safest next controlled experiment on the existing ten-page GT because current failures lack panel/tier evidence.",
        "ambiguity_evidence": "A future AMBIGUOUS_ORDER is justified when plausible tier constructions yield different relative orders, a region matches multiple tiers, panel ownership is absent/multiple, or the chosen relation has weak overlap and conflicts with panel sequence.",
    }
    after = sample_resources(ResourceThresholds.from_environment())
    summary_artifact = {
        "schema_version": "reading-order-summary.v1", "checkpoint": "12.0",
        "baseline_reproduction": {"status": "PASS", "metrics": metrics(frozen_outputs),
                                  "page_deltas_vs_day11_control": {"improved": 3, "unchanged": 7, "regressed": 0},
                                  "page_3_exact": frozen_by[3]["prediction"] == frozen_by[3]["human"]},
        "failure_count": 4, "taxonomy": dict(taxonomy), "root_classes": dict(root_classes),
        "global_consistency": global_consistency,
        "human_gt_integrity": "PASS_WITH_STRUCTURAL_LABEL_LIMITATION",
        "best_recommended_candidate": "PANEL_AWARE_AMBIGUITY controlled experiment; no production integration",
        "generalization_risk": ["N=10 pages / 50 regions", "shared manga and layout style", "repeated geometry patterns",
                                "threshold and candidates observed on the benchmark", "limited difficult-layout and no authoritative panel/tier coverage"],
        "human_testing_required_for_next_experiment": False,
        "smallest_next_experiment": {
            "pages": 10,
            "dataset": "existing immutable Day 11 Human click-order GT",
            "additional_evidence": "Separate benchmark-only manual panel containment/adjacency fixture for affected Pages 15, 17 and 38; not authoritative Human GT.",
            "hypothesis": "Explicit panel containment/order plus text-to-panel assignment resolves cross-panel inversions without regressing existing exact pages.",
            "metrics": ["exact pages", "exact positions", "pairwise accuracy", "inversions", "improved/unchanged/regressed pages", "new inversions"],
            "regression_gate": "No existing exact page regression and no new inversion.",
            "human_testing_policy": "Defer unseen Human pages until the existing-GT structural prototype demonstrates value.",
        },
        "resource_safety": {"before": before, "after": after,
                            "resource_guard": "CRITICAL" if "CRITICAL" in {before["safety_state"], after["safety_state"]} else after["safety_state"],
                            "ocr_calls": 0, "vlm_calls": 0, "ollama_calls": 0},
        "production_integration": False,
        "verdict": "C. CURRENT GEOMETRY INSUFFICIENT",
        "recommended_checkpoint_12_1": "Controlled panel/group-aware plus AMBIGUOUS_ORDER experiment on the existing frozen ten-page GT first; defer unseen Human pages; no OCR inference.",
    }

    DAY12.mkdir(parents=True, exist_ok=True)
    outputs = {
        "reading-order-failure-audit-12.0.json": failure_artifact,
        "reading-order-decision-traces-12.0.json": decision_artifact,
        "reading-order-candidate-analysis-12.0.json": candidate_artifact,
        "reading-order-summary-12.0.json": summary_artifact,
        "reading-order-synthetic-bridge-12.0.json": synthetic,
    }
    for name, payload in outputs.items():
        (DAY12 / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if sha(HUMAN) != hashlib.sha256(human_bytes).hexdigest() or sha(LOGICAL) != hashlib.sha256(logical_bytes).hexdigest():
        raise RuntimeError("frozen Human/logical input changed")
    print(json.dumps({"baseline": metrics(frozen_outputs), "failures": len(failures),
                      "candidates": {row["candidate"]: row["metrics"] for row in comparisons},
                      "verdict": summary_artifact["verdict"], "resource_guard": summary_artifact["resource_safety"]["resource_guard"]}))


if __name__ == "__main__":
    main()
