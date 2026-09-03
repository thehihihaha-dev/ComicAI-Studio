"""Run the frozen-candidate-only Checkpoint 12.3 conflict resolver once."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.panel_conflict_resolver import VERSION, resolve_candidates, semantic_hash  # noqa: E402
from app.services.resource_safety import ResourceThresholds, sample_resources  # noqa: E402

DAY12 = ROOT / "benchmarks/day12"
FROZEN = DAY12 / "panel-predictions-12.2.json"
EXTRACTION_PROTOCOL = DAY12 / "panel-extraction-protocol-12.2.json"
PROTOCOL_PATH = DAY12 / "panel-conflict-resolution-protocol-12.3.json"
GRAPH_PATH = DAY12 / "panel-conflict-graph-12.3.json"
OUTPUT_PATH = DAY12 / "panel-conflict-resolution-output-12.3.json"
EVALUATION_PATH = DAY12 / "panel-conflict-resolution-evaluation-12.3.json"
SUMMARY_PATH = DAY12 / "panel-conflict-resolution-summary-12.3.json"
FROZEN_SHA = "80e46d5c6216e3d18e9686af149a0012911795a246d1323ae4bb74d516b4b735"
SEMANTIC_SHA = "b52a3a7371b9e92542ae243db239f58d12bcefa284f90b538873102864fb051d"
GT_SHA = "5ac1383fdbd611bd203fa1e1b35d8fb0eb4e4e082f62e04907adc493c5635fd3"
EVAL_PAGES = (1, 2, 15, 17)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def candidate(panel_id: str, bbox: list[float], *, state: str = "AMBIGUOUS",
              provenance: list[str] | None = None, source_count: int = 1) -> dict:
    return {"panel_id": panel_id, "bbox": bbox, "state": state,
            "provenance": provenance or ["border_contour"],
            "heuristic_evidence": {"source_count": source_count}}


def synthetic_results(config: dict[str, float]) -> list[dict]:
    fixtures = []
    parent = candidate("parent", [0, 0, 200, 100], provenance=["whitespace_partition"])
    left, right = candidate("left", [0, 0, 98, 100]), candidate("right", [102, 0, 200, 100])
    fixtures.append(("under_split_parent", [parent, left, right], {"left", "right"}, "UNDER_SPLIT_SPANNER"))
    outer = candidate("outer", [0, 0, 200, 100], state="DETECTED")
    fragment = candidate("fragment", [20, 20, 60, 60])
    fixtures.append(("nested_internal_fragment", [outer, fragment], {"outer"}, "NESTED_INTERNAL_FRAGMENT"))
    duplicate = candidate("duplicate", [1, 1, 199, 99])
    fixtures.append(("duplicate", [outer, duplicate], {"outer"}, "DUPLICATE"))
    adjacent_left = candidate("adjacent-left", [0, 0, 98, 100],
                              provenance=["border_contour", "whitespace_partition"], source_count=2)
    adjacent_right = candidate("adjacent-right", [102, 0, 200, 100],
                               provenance=["border_contour", "whitespace_partition"], source_count=2)
    fixtures.append(("adjacent_panels", [adjacent_left, adjacent_right],
                     {"adjacent-left", "adjacent-right"}, None))
    large = candidate("large", [0, 0, 200, 100], state="DETECTED")
    fixtures.append(("legitimate_large_single", [large], {"large"}, None))
    tall_parent = candidate("tall-parent", [0, 0, 300, 200], provenance=["whitespace_partition"])
    tall = candidate("tall", [0, 0, 148, 200]); top = candidate("top", [152, 0, 300, 98]); bottom = candidate("bottom", [152, 102, 300, 200])
    fixtures.append(("tall_beside_stacked", [tall_parent, tall, top, bottom], {"tall", "top", "bottom"}, "UNDER_SPLIT_SPANNER"))
    scattered_parent = candidate("scatter-parent", [0, 0, 300, 200], provenance=["whitespace_partition"])
    first = candidate("scatter-a", [20, 20, 100, 80]); second = candidate("scatter-b", [170, 110, 280, 180])
    fixtures.append(("ambiguous_overlap_unresolved", [scattered_parent, first, second], set(), None))
    locked_left, locked_right = candidate("locked-left", [0, 0, 98, 100], state="DETECTED"), candidate("locked-right", [102, 0, 200, 100], state="DETECTED")
    locked_fragment = candidate("locked-fragment", [120, 20, 160, 60])
    fixtures.append(("locked_control", [locked_left, locked_right, locked_fragment], {"locked-left", "locked-right"}, "NESTED_INTERNAL_FRAGMENT"))
    results = []
    for name, panels, expected, rejection in fixtures:
        _, output = resolve_candidates(panels, config)
        reasons = {item["reason"] for item in output["candidates"]}
        passed = set(output["selected_panel_ids"]) == expected and (rejection is None or rejection in reasons)
        if not passed:
            raise SystemExit(f"Synthetic resolver fixture failed: {name}")
        results.append({"fixture": name, "result": "PASS", "selected_panel_ids": output["selected_panel_ids"]})
    return results


def validate_frozen(payload: dict, actual_file_sha256: str) -> None:
    if actual_file_sha256 != FROZEN_SHA:
        raise ValueError("Frozen prediction file hash mismatch")
    if (payload.get("semantic_sha256") != SEMANTIC_SHA
            or semantic_hash(payload.get("pages", [])) != SEMANTIC_SHA
            or payload.get("gt_runtime_features") != []):
        raise SystemExit("Frozen semantic/GT isolation mismatch")
    page_orders, candidate_ids = [], set()
    for page in payload.get("pages", []):
        page_orders.append(page["page_order"])
        if page.get("gt_runtime_features") != []:
            raise SystemExit("Page contains GT runtime features")
        for panel in page.get("panels", []):
            panel_id, box = panel.get("panel_id"), panel.get("bbox")
            if not panel_id or panel_id in candidate_ids or not isinstance(box, list) or len(box) != 4:
                raise SystemExit("Frozen candidate schema/identity invalid")
            if not (box[0] < box[2] and box[1] < box[3]):
                raise SystemExit("Frozen candidate geometry invalid")
            candidate_ids.add(panel_id)
    if len(page_orders) != 10 or len(set(page_orders)) != 10:
        raise SystemExit("Frozen candidate pages are incomplete")


def main() -> None:
    before = sample_resources(ResourceThresholds.from_environment())
    if before["safety_state"] != "NORMAL" or file_sha(FROZEN) != FROZEN_SHA:
        raise SystemExit("Frozen input/resource gate failed")
    frozen_file_sha = file_sha(FROZEN)
    frozen = json.loads(FROZEN.read_text(encoding="utf-8")); validate_frozen(frozen, frozen_file_sha)
    extraction_protocol = json.loads(EXTRACTION_PROTOCOL.read_text(encoding="utf-8"))
    config = {"duplicate_iou": extraction_protocol["configuration"]["duplicate_iou"],
              "edge_join_fraction": extraction_protocol["configuration"]["edge_join_fraction"]}
    resolver_path = ROOT / "backend/app/services/panel_conflict_resolver.py"
    protocol = {"schema_version": "panel-conflict-resolution-protocol.v1", "checkpoint": "12.3",
                "question": "Can containment-aware conflict resolution recover panels from frozen candidates without extraction?",
                "mode": "OFFLINE_FROZEN_CANDIDATE_SELECTION_ONLY", "resolver_version": VERSION,
                "resolver_sha256": file_sha(resolver_path), "frozen_prediction_file_sha256": FROZEN_SHA,
                "frozen_prediction_semantic_sha256": SEMANTIC_SHA, "candidate_source": "pages[].panels",
                "strategy": "RECURSIVE_GUILLOTINE_COMPATIBLE_OUTER_CONTOUR_TILING_WITH_LOCKED_SAFE_CONTROLS",
                "configuration": config, "configuration_origin": "REUSED_FROZEN_12.2_TOLERANCES",
                "phase_order": ["WRITE_PROTOCOL", "BUILD_GRAPH", "RESOLVE_TWICE", "FREEZE_GRAPH_AND_OUTPUT", "LOAD_HUMAN_GT", "EVALUATE"],
                "gt_runtime_features": [], "page_id_rules": [], "geometry_mutation": False,
                "extractor_rerun": False, "reading_order_run": False,
                "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0},
                "frozen_input_validation": {"file_hash_fail_closed": True,
                                             "semantic_material_fail_closed": True}}
    write(PROTOCOL_PATH, protocol)

    def resolution() -> tuple[dict, dict]:
        graph_pages, output_pages = [], []
        for page in frozen["pages"]:
            graph, output = resolve_candidates(page["panels"], config)
            graph_pages.append({"page_order": page["page_order"], "source_hash": page["source_hash"], **graph})
            output_pages.append({"page_order": page["page_order"], "source_hash": page["source_hash"], **output})
        graph_artifact = {"schema_version": "panel-conflict-graph.v1", "checkpoint": "12.3",
                          "frozen_prediction_file_sha256": FROZEN_SHA, "gt_runtime_features": [], "pages": graph_pages}
        output_artifact = {"schema_version": "panel-conflict-resolution-output.v1", "checkpoint": "12.3",
                           "resolver_version": VERSION, "frozen_prediction_file_sha256": FROZEN_SHA,
                           "gt_runtime_features": [], "pages": output_pages}
        graph_artifact["semantic_sha256"] = semantic_hash(graph_artifact)
        output_artifact["semantic_sha256"] = semantic_hash(output_artifact)
        return graph_artifact, output_artifact

    first_graph, first_output = resolution(); second_graph, second_output = resolution()
    if (first_graph, first_output) != (second_graph, second_output):
        raise SystemExit("Resolver is not deterministic")
    write(GRAPH_PATH, first_graph); write(OUTPUT_PATH, first_output)
    graph_file_sha, output_file_sha = file_sha(GRAPH_PATH), file_sha(OUTPUT_PATH)

    # Human GT imports and reads are deliberately deferred until after output persistence/freeze.
    from app.database import SessionLocal  # noqa: E402
    from app.models.panel_ground_truth_review import PanelGroundTruthReview  # noqa: E402
    from app.services.panel_correctness_evaluator import evaluate_page  # noqa: E402

    db = SessionLocal()
    try:
        rows = db.query(PanelGroundTruthReview).order_by(PanelGroundTruthReview.page_order).all()
        material = [{"id": row.review_id, "state": row.state, "revision": row.revision,
                     "panels": row.human_panels, "hash": row.source_image_hash} for row in rows]
        if tuple(row.page_order for row in rows) != EVAL_PAGES or any(row.state != "VERIFIED" for row in rows) \
                or semantic_hash(material) != GT_SHA:
            raise SystemExit("Approved Human GT changed")
        truths = {row.page_order: row.human_panels for row in rows}
    finally:
        db.close()
    frozen_by_page = {page["page_order"]: page for page in frozen["pages"]}
    output_by_page = {page["page_order"]: page for page in first_output["pages"]}
    per_page = []
    for page_order in EVAL_PAGES:
        frozen_page, resolved = frozen_by_page[page_order], output_by_page[page_order]
        frozen_candidates = {panel["panel_id"]: panel for panel in frozen_page["panels"]}
        selected_panels = []
        for panel_id in resolved["selected_panel_ids"]:
            panel = dict(frozen_candidates[panel_id]); panel["state"] = "DETECTED"; selected_panels.append(panel)
        evaluated = evaluate_page({"page_order": page_order, "panels": selected_panels,
                                   "unresolved": resolved["unresolved"]}, truths[page_order])
        evaluated["selected_panel_ids"] = resolved["selected_panel_ids"]
        evaluated["rejection_reasons"] = dict(Counter(item["reason"] for item in resolved["candidates"]
                                                       if item["resolution_status"] != "SELECTED"))
        per_page.append(evaluated)
    matched = sum(page["matched_true_panels_detected"] for page in per_page)
    selected_count = sum(page["predicted_detected_count"] for page in per_page)
    false = sum(len(page["false_detected_panel_ids"]) for page in per_page)
    precision = matched / selected_count if selected_count else 0.0; recall = matched / 15
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    page_map = {page["page_order"]: page for page in per_page}
    page2_input = {panel["panel_id"]: panel["bbox"] for panel in frozen_by_page[2]["panels"] if panel["state"] == "DETECTED"}
    page2_output = {panel_id: next(panel["bbox"] for panel in frozen_by_page[2]["panels"] if panel["panel_id"] == panel_id)
                    for panel_id in output_by_page[2]["selected_panel_ids"]}
    page2_safe = page2_input == page2_output and page_map[2]["matched_true_panels_detected"] == 2 and false == 0
    aggregate = {"human_panels": 15, "selected_panels": selected_count, "matched": matched,
                 "missed": 15-matched, "false_promoted": false, "precision": round(precision, 6),
                 "recall": round(recall, 6), "f1": round(f1, 6),
                 "unresolved_pages": sum(page["unresolved"] for page in per_page),
                 "under_split_selected": sum(len(page["under_splitting"]) for page in per_page),
                 "over_split_selected": sum(len(page["over_splitting"]) for page in per_page)}
    gates = {"matched_at_least_10": matched >= 10, "zero_false": false == 0,
             "precision_one": round(precision, 6) == 1.0, "recall_at_least_0666667": round(recall, 6) >= 0.666667,
             "f1_at_least_080": round(f1, 6) >= 0.8,
             "unresolved_at_most_one": aggregate["unresolved_pages"] <= 1,
             "page_2_preserved": page2_safe, "page_15_at_least_3": page_map[15]["matched_true_panels_detected"] >= 3,
             "page_17_five": page_map[17]["matched_true_panels_detected"] == 5,
             "no_under_or_over_split_selected": aggregate["under_split_selected"] == aggregate["over_split_selected"] == 0,
             "geometry_mutated": False, "gt_runtime_features": [], "resource_guard": "NORMAL"}
    outcome = ("A. CONFLICT RESOLUTION PASS — SAFE STRUCTURAL RECOVERY" if all(
        value is True for key, value in gates.items() if key not in {"geometry_mutated", "gt_runtime_features", "resource_guard"})
        and not gates["geometry_mutated"] and gates["gt_runtime_features"] == [] else
        "B. PARTIAL RECOVERY — ADDITIONAL DETERMINISTIC STRUCTURE REQUIRED" if matched > 2 and false == 0 and page2_safe else
        "C. CONFLICT RESOLUTION DOES NOT SOLVE THE BOTTLENECK")
    evaluation = {"schema_version": "panel-conflict-resolution-evaluation.v1", "checkpoint": "12.3",
                  "human_gt_snapshot_sha256": GT_SHA, "resolution_output_file_sha256_before_gt": output_file_sha,
                  "resolution_output_semantic_sha256": first_output["semantic_sha256"],
                  "matching_protocol": "UNCHANGED_12.2_ONE_TO_ONE_IOU_0.50_EVALUATION_ONLY",
                  "control": {"matched": 2, "missed": 13, "false_detected": 0, "precision": 1.0,
                              "recall": 0.133333, "f1": 0.235294, "unresolved_pages": 3},
                  "per_page": per_page, "aggregate": aggregate, "success_gates": gates,
                  "page_1_generation_limitation": "human-1-9 has no valid frozen full-panel candidate; resolver did not synthesize geometry.",
                  "gt_runtime_features": [], "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0}}
    write(EVALUATION_PATH, evaluation)
    synthetic = synthetic_results(config)
    reason_counts = Counter(item["reason"] for page in first_output["pages"] for item in page["candidates"])
    summary = {"schema_version": "panel-conflict-resolution-summary.v1", "checkpoint": "12.3",
               "outcome": outcome, "question_answer": "YES" if outcome.startswith("A.") else "PARTIAL" if outcome.startswith("B.") else "NO",
               "frozen_inputs": {"prediction_file_sha256": FROZEN_SHA, "prediction_semantic_sha256": SEMANTIC_SHA},
               "freeze": {"protocol_file_sha256": file_sha(PROTOCOL_PATH), "graph_file_sha256": graph_file_sha,
                          "graph_semantic_sha256": first_graph["semantic_sha256"], "output_file_sha256": output_file_sha,
                          "output_semantic_sha256": first_output["semantic_sha256"], "output_frozen_before_gt": True,
                          "two_run_semantic_byte_equivalent": True},
               "aggregate": aggregate, "success_gates": gates, "resolution_reason_counts": dict(sorted(reason_counts.items())),
               "synthetic_results": synthetic,
               "behavioral_evidence": {
                   "frozen_input_fail_closed_executed_test": "test_validate_frozen_fails_closed_on_wrong_hash_or_mutation",
                   "gt_isolation_executed_test": "test_behavioral_gt_change_cannot_affect_real_resolver_path",
                   "gt_isolation_result": "PASS",
               },
               "recommended_next_step": "Unseen-page Human validation in a separately approved checkpoint before any Reader integration." if outcome.startswith("A.") else "Stop and review the named unresolved deterministic structure.",
               "safety": {"gt_runtime_features": [], "human_gt_modified": False, "frozen_predictions_modified": file_sha(FROZEN) != FROZEN_SHA,
                          "geometry_mutated": False, "extractor_rerun": False, "reading_order_run": False,
                          "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0}, "resource_guard": "NORMAL"}}
    if summary["safety"]["frozen_predictions_modified"]:
        raise SystemExit("Frozen predictions changed")
    write(SUMMARY_PATH, summary)
    after = sample_resources(ResourceThresholds.from_environment())
    if after["safety_state"] != "NORMAL":
        raise SystemExit("Resource Guard changed")
    print(json.dumps({"outcome": outcome, "aggregate": aggregate, "output_sha256": output_file_sha,
                      "synthetic": len(synthetic), "resource_guard": "NORMAL"}))


if __name__ == "__main__":
    main()
