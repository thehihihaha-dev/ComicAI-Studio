#!/usr/bin/env python3
"""Checkpoint 12.1 hard-gate audit; never performs panel/model inference."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.resource_safety import ResourceThresholds, sample_resources  # noqa: E402

DAY11 = ROOT / "benchmarks/day11"
DAY12 = ROOT / "benchmarks/day12"
LOGICAL = DAY11 / "reader-logical-region-sample-11.11.json"
REVIEW_SAMPLE = DAY11 / "reader-v2-correctness-review-sample-11.11.json"
FINAL_SCALE = DAY11 / "reader-v2-final-scale-11.17.json"
SCALE_40 = DAY11 / "reader-v2-scale-40p-11.10.json"
SCALE_CACHE = DAY11 / "reader-v2-scale-cache-11.10.json"
ORDER_CANDIDATES = DAY11 / "reader-order-candidates-11.16.json"
ORDER_SUMMARY = DAY11 / "reader-order-summary-11.16.json"
MANUAL_12_0 = DAY12 / "reading-order-failure-audit-12.0.json"
SCRIPT = Path(__file__)

EXPECTED = {"exact_pages": (7, 10), "exact_positions": (43, 50), "pairwise": (120, 124), "inversions": 4}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def pairs(sequence: list[str]) -> set[tuple[str, str]]:
    return {(left, right) for index, left in enumerate(sequence) for right in sequence[index + 1 :]}


def reproduce_control() -> dict[str, Any]:
    # Evaluation happens only after the non-Human audit/protocol have been frozen.
    pages = json.loads(ORDER_CANDIDATES.read_text())["outputs"]["A_VERTICAL_OVERLAP"]
    exact = sum(page["prediction"] == page["human"] for page in pages)
    positions = sum(index < len(page["prediction"]) and page["prediction"][index] == region
                    for page in pages for index, region in enumerate(page["human"]))
    total_positions = sum(len(page["human"]) for page in pages)
    correct_pairs = sum(len(pairs(page["prediction"]) & pairs(page["human"])) for page in pages)
    total_pairs = sum(len(pairs(page["human"])) for page in pages)
    result = {
        "exact_pages": {"correct": exact, "total": len(pages), "accuracy": exact / len(pages)},
        "exact_positions": {"correct": positions, "total": total_positions, "accuracy": positions / total_positions},
        "pairwise": {"correct": correct_pairs, "total": total_pairs, "accuracy": correct_pairs / total_pairs},
        "inversions": total_pairs - correct_pairs,
    }
    observed = {"exact_pages": (exact, len(pages)), "exact_positions": (positions, total_positions),
                "pairwise": (correct_pairs, total_pairs), "inversions": result["inversions"]}
    if observed != EXPECTED:
        raise RuntimeError(f"frozen control mismatch: {observed}")
    return result


def main() -> None:
    before = sample_resources(ResourceThresholds.from_environment())
    logical = json.loads(LOGICAL.read_text())
    review = json.loads(REVIEW_SAMPLE.read_text())
    final_scale = json.loads(FINAL_SCALE.read_text())
    scale_40 = json.loads(SCALE_40.read_text())
    scale_cache = json.loads(SCALE_CACHE.read_text())
    review_by = {page["asset_id"]: page for page in review["pages"]}
    scale_by = {output["page_id"]: output for output in final_scale["structured_outputs"].values()}
    scale_40_by = {page["asset_id"]: page for page in scale_40["pages"]}
    scale_cache_by = {entry["result"]["asset_id"]: entry for entry in scale_cache["entries"].values()}

    # Phase 1 uses only non-Human persisted prediction artifacts.
    pages = []
    for page in logical["pages"]:
        asset_id = page["asset_id"]
        region_count = len(page["logical_regions"])
        logical_panel_ids = sorted({region.get("panel_id") for region in page["logical_regions"]})
        predicted_groups = review_by[asset_id].get("predicted_groups", [])
        non_page_groups = [group for group in predicted_groups if group.get("group_id") not in {"PAGE", "PAGE_FALLBACK"}]
        scale_group_ids = sorted({region.get("predicted_group_id") for region in scale_by[asset_id]["regions"]})
        scale_has_panel_geometry = any("panel" in key.lower() for key in scale_by[asset_id])
        scale_40_page = scale_40_by[asset_id]
        scale_40_diagnostics = scale_40_page["diagnostics"]
        scale_40_detail = scale_40_page["result"]["reading_order_detail"]
        cache_detail = scale_cache_by[asset_id]["result"]["reading_order_detail"]
        scale_40_groups = scale_40_diagnostics["group_assignments"]
        scale_40_page_group_count = sum(group.get("group_id") == "PAGE" for group in scale_40_groups)
        scale_40_other_groups = [group for group in scale_40_groups if group.get("group_id") != "PAGE"]
        if not (scale_40_diagnostics["panel_count"] == 0
                and scale_40_detail["panel_source"] == "page_fallback_no_panel_hierarchy"
                and scale_40_detail["panel_order"] == ["PAGE"]
                and scale_40_page_group_count == 1 and not scale_40_other_groups
                and cache_detail["panel_source"] == "page_fallback_no_panel_hierarchy"
                and cache_detail["panel_order"] == ["PAGE"]):
            raise RuntimeError(f"11.10 panel evidence changed for page {page['page_order']}")
        pages.append({
            "page_order": page["page_order"],
            "asset_id": asset_id,
            "source_hash": page["source_hash"],
            "text_region_count": region_count,
            "predicted_panel_count_excluding_page_fallback": 0,
            "panel_geometry_source": "PAGE_FALLBACK_ONLY",
            "panel_geometry_provenance": [
                {"artifact": LOGICAL.name, "field": "logical_regions[].panel_id", "values": logical_panel_ids,
                 "bbox_or_polygon_available": False},
                {"artifact": REVIEW_SAMPLE.name, "field": "predicted_groups", "values": [g.get("group_id") for g in predicted_groups],
                 "bbox_or_polygon_available": False},
                {"artifact": FINAL_SCALE.name, "field": "structured_outputs.regions[].predicted_group_id",
                 "values": scale_group_ids, "bbox_or_polygon_available": scale_has_panel_geometry},
                {"artifact": SCALE_40.name,
                 "field": "pages[].diagnostics.panel_count/group_assignments + result.reading_order_detail.panel_source/panel_order",
                 "values": {"panel_count": scale_40_diagnostics["panel_count"], "group_assignments": scale_40_groups,
                            "panel_source": scale_40_detail["panel_source"], "panel_order": scale_40_detail["panel_order"]},
                 "record_count": 1, "geometry_type": "NONE", "provenance": "SYSTEM_GENERATED_READER_V2_FAST_PASS",
                 "classification": "PAGE_LEVEL_FALLBACK", "text_to_panel_assignment_possible": False,
                 "legitimate_candidate_input": False, "bbox_or_polygon_available": False},
                {"artifact": SCALE_CACHE.name,
                 "field": "entries[].result.reading_order_detail.panel_source/panel_order",
                 "values": {"panel_source": cache_detail["panel_source"], "panel_order": cache_detail["panel_order"]},
                 "record_count": 1, "geometry_type": "NONE", "provenance": "SYSTEM_GENERATED_CACHED_REPLAY",
                 "classification": "PAGE_LEVEL_FALLBACK", "text_to_panel_assignment_possible": False,
                 "legitimate_candidate_input": False, "bbox_or_polygon_available": False},
            ],
            "persisted_or_reproducible_without_inference": True,
            "confidently_usable_panels": 0,
            "regions_potentially_assignable": 0,
            "regions_without_usable_panel": region_count,
            "overlapping_or_multi_panel_regions": 0,
            "structural_ambiguity": "All persisted predictions collapse the page to PAGE/PAGE_FALLBACK; no panel bbox/polygon or panel adjacency exists.",
            "non_page_group_count": len(non_page_groups),
            "gate_usable": False,
        })

    known_failure_pages = {15, 17, 38}
    usable_failure_pages = sorted(page["page_order"] for page in pages if page["page_order"] in known_failure_pages and page["gate_usable"])
    usable_control_pages = sorted(page["page_order"] for page in pages if page["page_order"] not in known_failure_pages and page["gate_usable"])
    gate_pass = usable_failure_pages == sorted(known_failure_pages) and len(usable_control_pages) >= 1
    if gate_pass:
        raise RuntimeError("audit unexpectedly passed; this hard-stop runner must be reviewed before Phase 2")

    input_hashes = {path.name: sha(path) for path in (LOGICAL, REVIEW_SAMPLE, FINAL_SCALE, SCALE_40, SCALE_CACHE)}
    audit = {
        "schema_version": "panel-data-audit.v1", "checkpoint": "12.1", "evidence_class": "NON_HUMAN_PREDICTION_INPUT_AUDIT",
        "audit_inputs": input_hashes, "pages": pages,
        "potential_panel_sources": [
            {"artifact": LOGICAL.name, "record_count": 63, "geometry_type": "NONE", "provenance": "SYSTEM_GENERATED_LOGICAL_REGIONS",
             "classification": "PAGE_LEVEL_FALLBACK", "represents_real_manga_panel": False, "text_to_panel_assignment_possible": False, "legitimate_candidate_input": False},
            {"artifact": REVIEW_SAMPLE.name, "record_count": 10, "geometry_type": "NONE", "provenance": "SYSTEM_GENERATED_FAST_PASS_REVIEW_SAMPLE",
             "classification": "PAGE_LEVEL_FALLBACK", "represents_real_manga_panel": False, "text_to_panel_assignment_possible": False, "legitimate_candidate_input": False},
            {"artifact": FINAL_SCALE.name, "record_count": 189, "geometry_type": "NONE", "provenance": "SYSTEM_GENERATED_FINAL_CONTRACT",
             "classification": "PAGE_LEVEL_FALLBACK", "represents_real_manga_panel": False, "text_to_panel_assignment_possible": False, "legitimate_candidate_input": False},
            {"artifact": SCALE_40.name, "record_count": 10, "geometry_type": "NONE", "provenance": "SYSTEM_GENERATED_READER_V2_FAST_PASS",
             "classification": "PAGE_LEVEL_FALLBACK", "represents_real_manga_panel": False, "text_to_panel_assignment_possible": False, "legitimate_candidate_input": False},
            {"artifact": SCALE_CACHE.name, "record_count": 10, "geometry_type": "NONE", "provenance": "SYSTEM_GENERATED_CACHED_REPLAY",
             "classification": "PAGE_LEVEL_FALLBACK", "represents_real_manga_panel": False, "text_to_panel_assignment_possible": False, "legitimate_candidate_input": False},
            {"artifact": MANUAL_12_0.name, "record_count": 4, "geometry_type": "MANUAL_VISUAL_PANEL_RELATIONSHIP_NO_PERSISTED_PANEL_GEOMETRY",
             "provenance": "CHECKPOINT_12_0_MANUAL_ANALYSIS", "classification": "HUMAN_DERIVED_FORBIDDEN",
             "represents_real_manga_panel": True, "text_to_panel_assignment_possible": False, "legitimate_candidate_input": False},
        ],
        "totals": {"pages": len(pages), "text_regions": sum(p["text_region_count"] for p in pages),
                   "usable_predicted_panels": 0, "confident_assignments": 0,
                   "unassigned_due_missing_panel_geometry": sum(p["text_region_count"] for p in pages),
                   "ambiguous_assignments": 0, "multi_panel_cases": 0},
        "known_failure_page_gate": {"required": sorted(known_failure_pages), "usable": usable_failure_pages},
        "control_page_gate": {"minimum": 1, "usable": usable_control_pages},
        "gate_pass": gate_pass,
        "gate_reason": "No ten-page artifact contains non-Human panel bbox/polygon geometry; all groups are PAGE/PAGE_FALLBACK.",
        "manual_12_0_evidence_policy": {"artifact_present": MANUAL_12_0.is_file(), "used_as_prediction_input": False,
                                        "classification": "ANALYSIS_ONLY_FORBIDDEN_RUNTIME_INPUT"},
        "human_click_order_loaded_during_audit": False,
    }
    protocol = {
        "schema_version": "panel-aware-protocol.v1", "checkpoint": "12.1", "status": "NOT_RUN_PANEL_DATA_GATE_FAILED",
        "phase_1_audit_hash": canonical_hash(audit), "candidate_runtime_inputs_hash": canonical_hash(input_hashes),
        "candidate_runtime_inputs": sorted(input_hashes), "gt_runtime_features": [],
        "human_or_manual_panel_input": False, "source_policy": "MANGA_RTL_POLICY",
        "frozen_intra_panel_rule": {"rule": "A_VERTICAL_OVERLAP", "normalized_vertical_overlap_min": 0.50,
                                      "status": "BENCHMARK_FITTED"},
        "candidate_implemented": False,
        "hard_stop": "No predicted panel geometry; panel detection/structural extraction requires a separately approved experiment.",
        "code_sha256": sha(SCRIPT),
    }

    # Freeze non-Human audit and protocol before evaluation-only control is loaded.
    DAY12.mkdir(parents=True, exist_ok=True)
    audit_path = DAY12 / "panel-data-audit-12.1.json"
    protocol_path = DAY12 / "panel-aware-protocol-12.1.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    protocol_path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")
    frozen_pre_score = {audit_path.name: sha(audit_path), protocol_path.name: sha(protocol_path)}

    control = reproduce_control()
    day11_summary = json.loads(ORDER_SUMMARY.read_text())
    comparison = {
        "schema_version": "panel-aware-comparison.v1", "checkpoint": "12.1", "status": "NOT_RUN_PANEL_DATA_GATE_FAILED",
        "prediction_frozen_before_evaluation": True, "pre_score_artifact_hashes": frozen_pre_score,
        "control": {"metrics": control, "page_deltas_vs_previous_control": {"improved": 3, "unchanged": 7, "regressed": 0},
                    "page_3_exact": day11_summary["page_3"]["candidates"]["A_VERTICAL_OVERLAP"]["prediction"] == day11_summary["page_3"]["candidates"]["A_VERTICAL_OVERLAP"]["human"],
                    "rule": "normalized vertical overlap >= 0.50", "parameter_status": "BENCHMARK_FITTED"},
        "candidate": None, "candidate_metrics": "N/A: hard gate failed before implementation",
        "known_inversions": {"repaired": "N/A", "unchanged": "N/A", "new": "N/A"},
    }
    errors = {
        "schema_version": "panel-aware-structural-errors.v1", "checkpoint": "12.1", "status": "NOT_RUN_PANEL_DATA_GATE_FAILED",
        "assignment_coverage": 0.0, "confident_assignments": 0,
        "unassigned_regions": sum(p["text_region_count"] for p in pages), "ambiguous_regions": 0, "multi_panel_cases": 0,
        "cross_panel_ordering_errors": "N/A: no candidate", "intra_panel_ordering_errors": "N/A: no candidate",
        "panel_order_errors": "N/A: no predicted panels",
        "failure_pages": [{"page_order": number, "available_predicted_panels": 0, "assignment": "NOT_RUN",
                           "panel_order": "NOT_RUN", "known_inversion_result": "UNCHANGED_NOT_EVALUATED",
                           "reason": "No legitimate non-Human panel geometry."} for number in sorted(known_failure_pages)],
    }
    after = sample_resources(ResourceThresholds.from_environment())
    summary = {
        "schema_version": "panel-aware-summary.v1", "checkpoint": "12.1",
        "panel_data_gate": "FAILED", "candidate_implemented": False, "candidate_evaluated": False,
        "control_reproduction": control, "panel_geometry_available": "PAGE/PAGE_FALLBACK groups only; zero panel geometries across 10 pages",
        "gt_leakage_audit": {"gt_runtime_features": [], "human_click_order_used_for_control_scoring_only": True,
                             "human_or_manual_panel_evidence_used_as_prediction_input": False,
                             "prediction_frozen_before_evaluation": True, "pre_score_artifact_hashes": frozen_pre_score},
        "structural_metrics": errors,
        "human_metrics": "N/A: no panel-aware candidate was permitted",
        "regressed_pages": "N/A", "new_inversions": "N/A",
        "resource_safety": {"before": before, "after": after,
                            "resource_guard": "CRITICAL" if "CRITICAL" in {before["safety_state"], after["safety_state"]} else after["safety_state"],
                            "ocr_calls": 0, "vlm_calls": 0, "ollama_calls": 0},
        "production_integration": False, "human_gt_modified": False, "historical_artifacts_modified": False,
        "outcome": "B. PANEL DETECTION/ASSIGNMENT IS THE BOTTLENECK",
        "unseen_human_testing_justified": False,
        "recommended_next_experiment": "Separately approved offline deterministic panel-structure extraction benchmark: produce non-Human panel bbox/polygon geometry and provenance on the existing ten pages, without using Human click order; then rerun this gate.",
    }
    for path, payload in ((DAY12 / "panel-aware-comparison-12.1.json", comparison),
                          (DAY12 / "panel-aware-structural-errors-12.1.json", errors),
                          (DAY12 / "panel-aware-summary-12.1.json", summary)):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if sha(audit_path) != frozen_pre_score[audit_path.name] or sha(protocol_path) != frozen_pre_score[protocol_path.name]:
        raise RuntimeError("pre-score artifact changed after evaluation")
    print(json.dumps({"gate": summary["panel_data_gate"], "pages": len(pages), "panels": 0,
                      "control": control, "outcome": summary["outcome"],
                      "resource_guard": summary["resource_safety"]["resource_guard"]}))


if __name__ == "__main__":
    main()
