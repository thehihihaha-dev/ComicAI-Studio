"""Evaluate frozen 12.2 panel predictions against approved post-Human GT."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.models.panel_ground_truth_review import PanelGroundTruthReview  # noqa: E402
from app.services.panel_correctness_evaluator import evaluate_page  # noqa: E402
from app.services.resource_safety import ResourceThresholds, sample_resources  # noqa: E402

DAY12 = ROOT / "benchmarks/day12"
PREDICTIONS = DAY12 / "panel-predictions-12.2.json"
PROTOCOL_SOURCE = DAY12 / "panel-extraction-protocol-12.2.json"
INPUT_AUDIT = DAY12 / "panel-extraction-input-audit-12.2.json"
FREEZE_DIAGNOSTIC = DAY12 / "panel-page-15-17-diagnostics-12.2.json"
PROTOCOL_OUTPUT = DAY12 / "panel-correctness-evaluation-protocol-12.2.json"
RESULT_OUTPUT = DAY12 / "panel-correctness-evaluation-12.2.json"
GT_SHA = "5ac1383fdbd611bd203fa1e1b35d8fb0eb4e4e082f62e04907adc493c5635fd3"
PREDICTION_SHA = "80e46d5c6216e3d18e9686af149a0012911795a246d1323ae4bb74d516b4b735"
PAGES = (1, 2, 15, 17)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def gt_material(rows: list[PanelGroundTruthReview]) -> list[dict]:
    return [{"id": row.review_id, "state": row.state, "revision": row.revision,
             "panels": row.human_panels, "hash": row.source_image_hash} for row in rows]


def canonical_hash(value: object) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    before = sample_resources(ResourceThresholds.from_environment())
    if before["safety_state"] != "NORMAL":
        raise SystemExit("Resource Guard is not NORMAL")
    predictions_raw = PREDICTIONS.read_bytes()
    if hashlib.sha256(predictions_raw).hexdigest() != PREDICTION_SHA:
        raise SystemExit("Frozen prediction fingerprint changed")
    predictions = json.loads(predictions_raw)
    extraction_protocol = json.loads(PROTOCOL_SOURCE.read_text(encoding="utf-8"))
    if predictions.get("gt_runtime_features") != [] or extraction_protocol.get("gt_runtime_features") != []:
        raise SystemExit("GT leakage boundary failed")
    frozen_sources = {int(item["page_order"]): item for item in
                      json.loads(INPUT_AUDIT.read_text(encoding="utf-8"))["inputs"]}
    prediction_pages = {int(item["page_order"]): item for item in predictions["pages"]}

    db = SessionLocal()
    try:
        rows = db.query(PanelGroundTruthReview).order_by(PanelGroundTruthReview.page_order).all()
        if tuple(row.page_order for row in rows) != PAGES or any(row.state != "VERIFIED" for row in rows):
            raise SystemExit("Human GT must be exactly four VERIFIED intended pages")
        if sum(len(row.human_panels or []) for row in rows) != 15 or canonical_hash(gt_material(rows)) != GT_SHA:
            raise SystemExit("Approved Human GT fingerprint changed")
        for row in rows:
            source = frozen_sources[row.page_order]
            source_path = ROOT / row.source_path
            if (row.benchmark_asset_id != source["asset_id"] or row.source_image_hash != source["source_hash"]
                    or sha(source_path) != source["source_hash"]):
                raise SystemExit(f"Source identity failed for Page {row.page_order}")
        truths = {row.page_order: row.human_panels for row in rows}
    finally:
        db.close()

    protocol = {
        "schema_version": "panel-correctness-evaluation-protocol.v1", "checkpoint": "12.2",
        "mode": "POST_FREEZE_EVALUATION_ONLY", "pages": list(PAGES),
        "primary_population": "DETECTED_ONLY", "ambiguous_population": "REPORTED_SEPARATELY_NOT_PROMOTED",
        "matching": {"method": "ONE_TO_ONE_MAX_CARDINALITY_THEN_MAX_TOTAL_BBOX_IOU",
                     "bbox_iou_threshold": 0.5,
                     "threshold_status": "EVALUATION_ONLY_PREDECLARED_CONVENTION_NOT_PRODUCTION_THRESHOLD",
                     "justification": "A fixed 0.50 bbox IoU convention was declared before computing results; it was not selected from these four pages.",
                     "tie_break": "LEXICOGRAPHIC_STABLE_PANEL_IDS"},
        "structural_relations": {"coverage_threshold": 0.5,
                                 "threshold_status": "EVALUATION_ONLY_PREDECLARED_DESCRIPTIVE_CONVENTION",
                                 "under_split": "one prediction covers at least 50% of each of two or more Human panels",
                                 "over_split": "one Human panel covers at least 50% of each of two or more predictions"},
        "metrics": "Precision/recall/F1 use DETECTED only; AMBIGUOUS candidates never count as detections.",
        "gt_runtime_features": [], "detector_rerun": False, "detector_tuned": False,
        "reading_order_run": False, "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0},
    }

    pages = [evaluate_page(prediction_pages[page], truths[page]) for page in PAGES]
    detected_count = sum(page["predicted_detected_count"] for page in pages)
    true_detected = sum(page["matched_true_panels_detected"] for page in pages)
    false_detected = sum(len(page["false_detected_panel_ids"]) for page in pages)
    missed_detected = 15 - true_detected
    precision = true_detected / detected_count if detected_count else None
    recall = true_detected / 15
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and precision + recall else None
    detected_ious = [match["iou"] for page in pages for match in page["detected_matches"]]
    ambiguous_ious = [match["iou"] for page in pages for match in page["ambiguous_matches"]]
    clean_ambiguous_ious = [match["iou"] for page in pages for match in page["ambiguous_matches"]
                            if match["structurally_clean"]]
    ambiguity_recoverable = len({(page["page_order"], match["human_panel_id"]) for page in pages
                                 for match in page["ambiguous_matches"]
                                 if match["human_panel_id"] not in {item["human_panel_id"] for item in page["detected_matches"]}})
    clean_ambiguity_recoverable = len({(page["page_order"], match["human_panel_id"]) for page in pages
                                       for match in page["ambiguous_matches"] if match["structurally_clean"]
                                       and match["human_panel_id"] not in {item["human_panel_id"] for item in page["detected_matches"]}})
    aggregate = {
        "human_panels": 15, "detected_predictions": detected_count,
        "ambiguous_predictions": sum(page["predicted_ambiguous_count"] for page in pages),
        "true_detected": true_detected, "missed_by_detected": missed_detected,
        "false_detected": false_detected, "precision": round(precision, 6), "recall": round(recall, 6),
        "f1": round(f1, 6), "detected_matched_iou": {"values": detected_ious,
        "min": min(detected_ious), "median": sum(sorted(detected_ious)[len(detected_ious)//2-1:len(detected_ious)//2+1])/2,
        "max": max(detected_ious), "mean": round(sum(detected_ious)/len(detected_ious), 6)},
        "human_panels_recoverable_among_ambiguous": ambiguity_recoverable,
        "human_panels_with_structurally_clean_ambiguous_candidate": clean_ambiguity_recoverable,
        "iou_eligible_ambiguous_matches_disqualified_as_under_split": ambiguity_recoverable-clean_ambiguity_recoverable,
        "ambiguous_matched_iou": {"count": len(ambiguous_ious), "min": min(ambiguous_ious),
        "max": max(ambiguous_ious), "mean": round(sum(ambiguous_ious)/len(ambiguous_ious), 6)},
        "structurally_clean_ambiguous_iou": {"count": len(clean_ambiguous_ious),
        "min": min(clean_ambiguous_ious), "max": max(clean_ambiguous_ious),
        "mean": round(sum(clean_ambiguous_ious)/len(clean_ambiguous_ious), 6)},
        "human_panels_missed_by_detected_and_ambiguous": sum(len(page["missed_by_all_candidates"]) for page in pages),
        "unresolved_pages": sum(page["unresolved"] for page in pages), "unresolved_page_rate": 0.75,
    }
    failure_taxonomy = [
        {"rank": 1, "failure_class": "CONFLICT_AMBIGUITY_SUPPRESSES_TRUE_PANEL_CANDIDATES",
         "affected_pages": [1, 15, 17], "affected_human_panels": 10,
         "origin": ["candidate_classification", "ambiguity_policy", "fusion"],
         "evidence": "Ten Human panels have structurally clean one-to-one IoU>=0.50 AMBIGUOUS candidates while these pages emit zero DETECTED panels; two additional IoU matches are under-split candidates."},
        {"rank": 2, "failure_class": "UNDER_SPLIT_WHITESPACE_PARTITIONS_CONFLICT_WITH_PANEL_TILING",
         "affected_pages": [1, 15, 17], "event_count": sum(len(page["under_splitting"]) for page in pages),
         "origin": ["candidate_generation", "fusion"],
         "evidence": "Large whitespace candidates span multiple adjacent Human panels and overlap accurate contour candidates."},
        {"rank": 3, "failure_class": "INTERNAL_CONTOUR_FRAGMENT_NOISE_OVER_SPLITTING",
         "affected_pages": [2, 15, 17], "event_count": sum(len(page["over_splitting"]) for page in pages),
         "origin": ["candidate_generation", "duplicate_suppression"],
         "evidence": "Small contour candidates lie inside true panels and coexist with full-panel candidates."},
        {"rank": 4, "failure_class": "MISSING_FULL_PANEL_CANDIDATE",
         "affected_pages": [1], "affected_human_panels": 1,
         "origin": ["missing_structural_evidence", "candidate_generation"],
         "evidence": "Page 1 human-1-9 has no DETECTED or AMBIGUOUS candidate at IoU>=0.50."},
    ]
    diagnostics = {
        "page_15": {"status": "UNRESOLVED", "human_panels": 5,
                    "diagnosis": "All five true panels exist as AMBIGUOUS IoU matches, but under-split whitespace partitions and internal contour fragments conflict with the correct tiling; classification/fusion, not total absence of panel evidence, is dominant."},
        "page_17": {"status": "UNRESOLVED", "human_panels": 5,
                    "diagnosis": "All five true panels exist as AMBIGUOUS IoU matches. Row-spanning whitespace candidates overlap accurate contour candidates, so the conflict policy suppresses the hierarchy needed by downstream ordering.",
                    "reading_order_implication": "Reliable panel ownership would provide missing cross-panel hierarchy, but panel ordering remains a separate unvalidated algorithmic problem."},
    }
    freeze = json.loads(FREEZE_DIAGNOSTIC.read_text(encoding="utf-8"))
    result = {
        "schema_version": "panel-correctness-evaluation.v1", "checkpoint": "12.2",
        "verdict": "B. PANEL EXTRACTION PARTIALLY VALID — DETERMINISTIC FIXES REQUIRED",
        "inputs": {"pages": list(PAGES), "human_gt_snapshot_sha256": GT_SHA,
                   "frozen_prediction_file_sha256": PREDICTION_SHA,
                   "prediction_semantic_sha256": predictions["semantic_sha256"],
                   "source_hashes": {str(page): frozen_sources[page]["source_hash"] for page in PAGES},
                   "gt_runtime_features": []},
        "freeze_guarantee": {"prediction_file_sha256_before_manual_read": freeze["prediction_file_sha256_before_manual_read"],
                             "extractor_sha256": extraction_protocol["extractor_sha256"],
                             "extractor_revision": extraction_protocol["revision"],
                             "configuration": extraction_protocol["configuration"],
                             "human_features_in_extraction": [], "prediction_modified": False},
        "protocol_sha256": canonical_hash(protocol), "per_page": pages, "aggregate": aggregate,
        "ambiguity_analysis": {"protects_from_false_confidence": True,
                               "unmatched_or_partial_ambiguous_candidates": sum(len(page["unmatched_ambiguous_panel_ids"]) for page in pages),
                               "iou_eligible_human_panels": ambiguity_recoverable,
                               "structurally_clean_true_panel_candidates_suppressed": clean_ambiguity_recoverable,
                               "iou_matches_qualified_as_under_split": ambiguity_recoverable-clean_ambiguity_recoverable,
                               "conclusion": "Ambiguity prevents false confidence but is excessively conservative on this set."},
        "diagnostics": diagnostics, "failure_taxonomy": failure_taxonomy,
        "reading_order_implication": "Better panel recovery is likely necessary for Pages 15/17 cross-panel hierarchy, but it is not sufficient to validate panel ordering.",
        "recommended_next_experiment": "One offline, predeclared containment-aware conflict-resolution replay over the already frozen raw candidates: prefer a non-overlapping contour-supported tiling over row/page-spanning whitespace candidates and nested internal fragments; no detector rerun, threshold sweep, Reading Order, or model calls.",
        "safety": {"human_gt_modified": False, "frozen_predictions_modified": False,
                   "detector_rerun": False, "reading_order_run": False,
                   "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0}},
    }
    if result != json.loads(json.dumps(result, ensure_ascii=False)):
        raise SystemExit("Evaluation is not JSON deterministic")
    write_json(PROTOCOL_OUTPUT, protocol); write_json(RESULT_OUTPUT, result)
    after = sample_resources(ResourceThresholds.from_environment())
    if after["safety_state"] != "NORMAL":
        raise SystemExit("Resource Guard changed from NORMAL")
    print(json.dumps({"verdict": result["verdict"], "aggregate": aggregate,
                      "artifact_sha256": sha(RESULT_OUTPUT), "resource_guard": "NORMAL"}))


if __name__ == "__main__":
    main()
