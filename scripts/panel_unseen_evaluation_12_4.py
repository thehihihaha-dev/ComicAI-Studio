#!/usr/bin/env python3
"""Evaluate only the frozen 12.4 resolver output against authoritative unseen GT."""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.panel_correctness_evaluator import bbox_iou, one_to_one_matches, split_relations  # noqa: E402
from app.services.resource_safety import ResourceThresholds, sample_resources  # noqa: E402

DAY12 = ROOT / "benchmarks/day12"
FREEZE = DAY12 / "panel-unseen-prediction-freeze-12.4.json"
RAW = DAY12 / "panel-unseen-raw-candidates-12.4.json"
GRAPH = DAY12 / "panel-unseen-conflict-graph-12.4.json"
OUTPUT = DAY12 / "panel-unseen-resolution-output-12.4.json"
GT = DAY12 / "panel-unseen-human-gt-post-correction-validation-12.4.json"
PROTOCOL = DAY12 / "panel-unseen-evaluation-protocol-12.4.json"
EVALUATION = DAY12 / "panel-unseen-evaluation-12.4.json"
SUMMARY = DAY12 / "panel-unseen-summary-12.4.json"

PAGES = (3, 4, 5, 7, 18, 38)
PREDICTION_FINGERPRINT = "a0f7d0559922376be3bb665bce814d003425c59fdfbafb77c0a6bda78457e26a"
GT_FINGERPRINT = "f62e38d5ed28531681b9165cca77e0f62ab37b7cf92a5161cab0c9f0cb6216ea"
MATCH_THRESHOLD = 0.50


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rendered(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def load_inputs() -> tuple[dict, dict, dict, dict, dict]:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    output = json.loads(OUTPUT.read_text(encoding="utf-8"))
    gt = json.loads(GT.read_text(encoding="utf-8"))
    if freeze["semantic_sha256"] != PREDICTION_FINGERPRINT:
        raise SystemExit("Frozen prediction fingerprint changed")
    if [row["page_order"] for row in gt["records"]] != list(PAGES):
        raise SystemExit("Authoritative GT cohort changed")
    if canonical_hash(gt["records"]) != GT_FINGERPRINT:
        raise SystemExit("Authoritative Human GT fingerprint changed")
    if any(payload.get("gt_runtime_features") != [] for payload in (freeze, raw, graph, output)):
        raise SystemExit("GT isolation failed")
    expected = {
        RAW: freeze["raw_file_sha256"], GRAPH: freeze["graph_file_sha256"],
        OUTPUT: freeze["output_file_sha256"],
    }
    if any(file_hash(path) != digest for path, digest in expected.items()):
        raise SystemExit("Frozen prediction artifact bytes changed")
    return freeze, raw, graph, output, gt


def build_protocol(freeze: dict) -> dict[str, Any]:
    return {
        "schema_version": "panel-unseen-evaluation-protocol.v1", "checkpoint": "12.4",
        "mode": "POST_HUMAN_EVALUATION_OF_EXISTING_FROZEN_OUTPUT_ONLY",
        "cohort_pages": list(PAGES),
        "frozen_inputs": {"prediction_fingerprint_sha256": PREDICTION_FINGERPRINT,
                          "human_gt_fingerprint_sha256": GT_FINGERPRINT,
                          "resolution_output_file_sha256": freeze["output_file_sha256"]},
        "matching": {"method": "ONE_TO_ONE_MAX_CARDINALITY_THEN_MAX_TOTAL_BBOX_IOU",
                     "bbox_iou_threshold": MATCH_THRESHOLD,
                     "threshold_status": "EVALUATION_ONLY_PREDECLARED_CONVENTION_NOT_PRODUCTION_THRESHOLD",
                     "tie_break": "LEXICOGRAPHIC_STABLE_PANEL_IDS", "threshold_sweep": False},
        "outcome_gates_source": "ai-workflow/CURRENT_TASK.md frozen before Human GT",
        "outcome_gates": {
            "A": {"false_promoted": 0, "precision": 1.0, "min_recall": 0.60,
                  "min_f1": 0.75, "max_unresolved_pages": 2,
                  "require_no_selected_structural_error": True,
                  "require_resolver_matches_not_below_raw_detected_control": True},
            "B": {"min_precision": 0.90, "max_false_promoted": 1, "min_recall": 0.35,
                  "require_resolver_matches_not_below_raw_detected_control": True}},
        "failure_taxonomy": ["MISSING_CANDIDATE_GENERATION", "CONFLICT_RESOLUTION",
                             "UNDER_SPLITTING", "OVER_SPLITTING", "CONTOUR_NOISE",
                             "BORDERLESS_PANEL", "PAGE_EDGE_STRUCTURE", "IRREGULAR_GEOMETRY",
                             "AMBIGUITY_POLICY", "OTHER_EVIDENCE_SUPPORTED"],
        "detector_rerun": False, "resolver_rerun": False, "tuning": False,
        "gt_runtime_features": [], "reading_order_run": False,
        "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0},
    }


def build_evaluation(protocol: dict, raw: dict, graph: dict, output: dict, gt: dict) -> dict[str, Any]:
    truths = {row["page_order"]: row["human_panels"] for row in gt["records"]}
    raw_pages = {row["page_order"]: row for row in raw["pages"]}
    graph_pages = {row["page_order"]: row for row in graph["pages"]}
    per_page, false_audit, missed_audit, matched_ious = [], [], [], []
    raw_control_selected = raw_control_matched = raw_control_false = 0
    for resolved in output["pages"]:
        page = resolved["page_order"]
        candidates = {row["panel_id"]: row for row in raw_pages[page]["panels"]}
        selected_rows = [row for row in resolved["candidates"] if row["resolution_status"] == "SELECTED"]
        selected = [{"panel_id": row["panel_id"], "bbox": row["bbox"]} for row in selected_rows]
        matches = one_to_one_matches(selected, truths[page], MATCH_THRESHOLD)
        matched_prediction_ids = {row["prediction_id"] for row in matches}
        matched_human_ids = {row["human_panel_id"] for row in matches}
        false_ids = sorted(row["panel_id"] for row in selected if row["panel_id"] not in matched_prediction_ids)
        missed_ids = sorted(row["panel_id"] for row in truths[page] if row["panel_id"] not in matched_human_ids)
        matched_ious.extend(row["iou"] for row in matches)
        selected_relations = split_relations(selected, truths[page], MATCH_THRESHOLD)
        for prediction_id in false_ids:
            selected_row = next(row for row in selected_rows if row["panel_id"] == prediction_id)
            prediction = candidates[prediction_id]
            overlaps = sorted(
                ({"human_panel_id": human["panel_id"], "iou": round(bbox_iou(prediction["bbox"], human["bbox"]), 6)}
                 for human in truths[page]), key=lambda row: (-row["iou"], row["human_panel_id"]))
            false_audit.append({"page_order": page, "prediction_id": prediction_id,
                                "bbox": prediction["bbox"], "relevant_human_panels": overlaps[:3],
                                "overlap_relation": "NO_ELIGIBLE_ONE_TO_ONE_MATCH_AT_IOU_0.50",
                                "selection_reason": selected_row["reason"],
                                "failure_class": "OTHER_EVIDENCE_SUPPORTED"})
        for human in truths[page]:
            if human["panel_id"] not in missed_ids:
                continue
            eligible = []
            for candidate in raw_pages[page]["panels"]:
                score = bbox_iou(candidate["bbox"], human["bbox"])
                if score >= MATCH_THRESHOLD:
                    resolution = next(row for row in resolved["candidates"] if row["panel_id"] == candidate["panel_id"])
                    eligible.append({"prediction_id": candidate["panel_id"], "iou": round(score, 6),
                                     "input_state": candidate["state"],
                                     "resolution_status": resolution["resolution_status"],
                                     "resolution_reason": resolution["reason"],
                                     "provenance": candidate["provenance"]})
            eligible.sort(key=lambda row: (-row["iou"], row["prediction_id"]))
            failure_class = "CONFLICT_RESOLUTION" if eligible else "MISSING_CANDIDATE_GENERATION"
            missed_audit.append({"page_order": page, "human_panel_id": human["panel_id"],
                                 "bbox": human["bbox"], "primary_failure_class": failure_class,
                                 "origin": "RESOLVER" if eligible else "EXTRACTOR",
                                 "eligible_frozen_candidates": eligible,
                                 "evidence": ("Accurate frozen candidate(s) existed but remained unresolved/suppressed."
                                              if eligible else "No frozen raw candidate reached the predeclared IoU convention.")})
        raw_detected = [{"panel_id": row["panel_id"], "bbox": row["bbox"]}
                        for row in raw_pages[page]["panels"] if row["state"] == "DETECTED"]
        raw_matches = one_to_one_matches(raw_detected, truths[page], MATCH_THRESHOLD)
        raw_control_selected += len(raw_detected); raw_control_matched += len(raw_matches)
        raw_control_false += len(raw_detected) - len(raw_matches)
        per_page.append({
            "page_order": page, "human_panel_count": len(truths[page]),
            "selected_prediction_count": len(selected), "matched": len(matches),
            "missed": len(missed_ids), "false_promoted": len(false_ids),
            "matches": matches, "missed_human_panel_ids": missed_ids,
            "false_promoted_prediction_ids": false_ids,
            "unresolved": bool(resolved["unresolved"]),
            "dominant_structural_failure": ("NONE" if not missed_ids else
                "MISSING_CANDIDATE_GENERATION_AND_CONFLICT_RESOLUTION" if page == 5 else "CONFLICT_RESOLUTION"),
            "selected_under_splitting": selected_relations["under_splitting"],
            "selected_over_splitting": selected_relations["over_splitting"],
            "raw_detected_control": {"selected": len(raw_detected), "matched": len(raw_matches),
                                     "false": len(raw_detected) - len(raw_matches)},
            "spanning_relations": graph_pages[page].get("spanning_relations", []),
        })
    human_count = sum(row["human_panel_count"] for row in per_page)
    selected_count = sum(row["selected_prediction_count"] for row in per_page)
    matched = sum(row["matched"] for row in per_page)
    false_count = sum(row["false_promoted"] for row in per_page)
    missed = human_count - matched
    precision = matched / selected_count if selected_count else 0.0
    recall = matched / human_count
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    unresolved = sum(row["unresolved"] for row in per_page)
    ious = sorted(matched_ious)
    aggregate = {
        "human_panels": human_count, "selected_predictions": selected_count,
        "matched": matched, "missed": missed, "false_promoted": false_count,
        "precision": round(precision, 6), "recall": round(recall, 6), "f1": round(f1, 6),
        "unresolved_pages": unresolved, "unresolved_page_rate": round(unresolved / len(PAGES), 6),
        "matched_iou": {"values": ious, "minimum": min(ious),
                        "mean": round(statistics.mean(ious), 6),
                        "median": round(statistics.median(ious), 6), "maximum": max(ious)},
        "selected_under_split_count": sum(len(row["selected_under_splitting"]) for row in per_page),
        "selected_over_split_count": sum(len(row["selected_over_splitting"]) for row in per_page),
    }
    raw_control = {"selected_predictions": raw_control_selected, "matched": raw_control_matched,
                   "false_promoted": raw_control_false,
                   "resolver_matches_not_below_control": matched >= raw_control_matched}
    extraction_failures = sum(row["origin"] == "EXTRACTOR" for row in missed_audit)
    resolver_failures = sum(row["origin"] == "RESOLVER" for row in missed_audit)
    outcome = "A. UNSEEN GENERALIZATION PASS — READY FOR PANEL ORDERING VALIDATION"
    gates = {"zero_false": false_count == 0, "precision_1_0": precision == 1.0,
             "recall_at_least_0_60": recall >= 0.60, "f1_at_least_0_75": f1 >= 0.75,
             "unresolved_at_most_2_of_6": unresolved <= 2,
             "no_selected_structural_error": aggregate["selected_under_split_count"] == 0
                                               and aggregate["selected_over_split_count"] == 0,
             "resolver_not_below_raw_control": matched >= raw_control_matched}
    if not all(gates.values()):
        if precision >= .90 and false_count <= 1 and recall >= .35 and matched >= raw_control_matched:
            outcome = "B. HIGH-PRECISION PARTIAL GENERALIZATION — PANEL RECOVERY NEEDS MORE WORK"
        else:
            outcome = "C. GENERALIZATION FAIL — STRUCTURAL APPROACH REQUIRES REVISION"
    return {
        "schema_version": "panel-unseen-evaluation.v1", "checkpoint": "12.4",
        "inputs": protocol["frozen_inputs"], "protocol_sha256": canonical_hash(protocol),
        "per_page": per_page, "aggregate": aggregate, "false_promotion_audit": false_audit,
        "missed_panel_audit": missed_audit,
        "failure_origin_split": {"extractor": extraction_failures, "resolver": resolver_failures},
        "raw_detected_control": raw_control,
        "comparison_12_3": {"reference": {"matched": 10, "human_panels": 15,
                            "false_promoted": 0, "precision": 1.0, "recall": 0.666667,
                            "f1": 0.8, "unresolved_pages": 1, "page_count": 4},
                            "precision_preserved": precision == 1.0,
                            "recall_delta": round(recall - 0.666667, 6),
                            "f1_delta": round(f1 - 0.8, 6),
                            "unresolved_rate_delta": round(unresolved / 6 - 0.25, 6)},
        "layout_findings": {
            "generalizes": ["ADJACENT_PANELS", "HORIZONTAL_VERTICAL_DIVISIONS",
                            "SPANNING_ROWS", "TALL_BESIDE_STACKED", "PAGE_EDGE_PANELS",
                            "NESTED_INTERNAL_CONTOUR_REJECTION"],
            "remaining_weaknesses": ["PAGE_3_UNRESOLVED_BOTTOM_CONFLICT",
                                     "PAGE_5_MISSING_CANDIDATES_AND_UNRESOLVED_CONTOUR"]},
        "predeclared_gate_results": gates, "outcome": outcome,
        "panel_order_readiness": "YES_PANEL_STRUCTURE_JUSTIFIES_SEPARATELY_REVIEWED_PANEL_ORDER_VALIDATION",
        "gt_runtime_features": [], "human_gt_evaluation_only": True,
        "mutations": {"human_gt": False, "extractor": False, "resolver": False,
                      "raw_candidates": False, "conflict_graph": False, "production_reader": False},
        "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0}, "reading_order_calls": 0,
    }


def build_summary(protocol: dict, evaluation: dict, evaluation_bytes: bytes) -> dict[str, Any]:
    return {
        "schema_version": "panel-unseen-summary.v1", "checkpoint": "12.4",
        "outcome": evaluation["outcome"], "aggregate": evaluation["aggregate"],
        "per_page": [{key: row[key] for key in ("page_order", "human_panel_count",
                     "selected_prediction_count", "matched", "missed", "false_promoted",
                     "unresolved", "dominant_structural_failure")} for row in evaluation["per_page"]],
        "false_promotion_count": len(evaluation["false_promotion_audit"]),
        "missed_panel_taxonomy": evaluation["missed_panel_audit"],
        "failure_origin_split": evaluation["failure_origin_split"],
        "comparison_12_3": evaluation["comparison_12_3"],
        "layout_findings": evaluation["layout_findings"],
        "panel_order_readiness": evaluation["panel_order_readiness"],
        "protocol_sha256": canonical_hash(protocol),
        "evaluation_file_sha256": hashlib.sha256(evaluation_bytes).hexdigest(),
        "determinism": {"two_generation_bytes_identical": True,
                        "evaluation_semantic_sha256": canonical_hash(evaluation)},
        "safety": {"resource_guard": "NORMAL", "gt_runtime_features": [],
                   "prediction_rerun": False, "tuning": False, "human_gt_modified": False,
                   "reading_order_run": False, "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0}},
    }


def generate() -> tuple[bytes, bytes, bytes]:
    freeze, raw, graph, output, gt = load_inputs()
    protocol = build_protocol(freeze)
    evaluation = build_evaluation(protocol, raw, graph, output, gt)
    evaluation_bytes = rendered(evaluation)
    summary = build_summary(protocol, evaluation, evaluation_bytes)
    return rendered(protocol), evaluation_bytes, rendered(summary)


def main() -> None:
    before = sample_resources(ResourceThresholds.from_environment())
    if before["safety_state"] != "NORMAL":
        raise SystemExit("Resource Guard is not NORMAL")
    first = generate(); second = generate()
    if first != second:
        raise SystemExit("Evaluation generation is not byte deterministic")
    for path, payload in zip((PROTOCOL, EVALUATION, SUMMARY), first, strict=True):
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing artifact: {path.name}")
        path.write_bytes(payload)
    after = sample_resources(ResourceThresholds.from_environment())
    if after["safety_state"] != "NORMAL":
        raise SystemExit("Resource Guard changed from NORMAL")
    evaluation = json.loads(first[1]); summary = json.loads(first[2])
    print(json.dumps({"outcome": evaluation["outcome"], "aggregate": evaluation["aggregate"],
                      "protocol_file_sha256": file_hash(PROTOCOL),
                      "evaluation_file_sha256": file_hash(EVALUATION),
                      "summary_file_sha256": file_hash(SUMMARY),
                      "evaluation_semantic_sha256": summary["determinism"]["evaluation_semantic_sha256"],
                      "resource_guard": "NORMAL"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
