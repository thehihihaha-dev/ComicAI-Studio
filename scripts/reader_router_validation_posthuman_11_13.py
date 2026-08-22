#!/usr/bin/env python3
"""Evaluate the pre-GT frozen R2 rule on Human-completed 11.13 data."""
from __future__ import annotations

import hashlib
import json
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env")

from app.database import SessionLocal
from app.models.asset import Asset
from app.models.reader_router_validation_review import ReaderRouterValidationReview
from app.services.ocr_acceptance_router_experiment import HARD, SAFE, STRUCTURAL, route
from app.services.reader_router_validation_review import _compatible
from app.services.resource_safety import ResourceThresholds, sample_resources
from reader_benchmark import authoritative_snapshot
from reader_router_experiment_11_12 import text_error_types

PROJECT = "e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2"
DAY = ROOT / "benchmarks" / "day11"
MANIFEST = DAY / "reader-router-validation-manifest-11.13.json"
HUMAN = DAY / "reader-router-validation-human-gt-11.13.json"
RESULTS = DAY / "reader-router-validation-results-11.13.json"
ERRORS = DAY / "reader-router-validation-errors-11.13.json"
SUMMARY = DAY / "reader-router-validation-summary-11.13.json"


def norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).upper().split())


def distance(a, b) -> int:
    previous = list(range(len(b) + 1))
    for index, left in enumerate(a, 1):
        current = [index]
        for offset, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[offset] + 1, previous[offset - 1] + (left != right)))
        previous = current
    return previous[-1]


def stable_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build() -> dict:
    thresholds = ResourceThresholds.from_environment()
    before_resources = sample_resources(thresholds)
    before_authoritative = authoritative_snapshot(PROJECT)["state_hash"]
    manifest_bytes = MANIFEST.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    calibration = json.loads((DAY / "reader-logical-region-sample-11.11.json").read_text())
    calibration_hashes = {page["source_hash"] for page in calibration["pages"]}
    validation_hashes = {page["source_hash"] for page in manifest["pages"]}
    sample_by_id = {sample["sample_id"]: sample for sample in manifest["samples"]}
    db = SessionLocal()
    human_samples = []
    try:
        rows = db.query(ReaderRouterValidationReview).filter_by(project_id=PROJECT).order_by(
            ReaderRouterValidationReview.page_order, ReaderRouterValidationReview.sample_id).all()
        if len(rows) != 81:
            raise RuntimeError(f"Human queue incomplete: {len(rows)}/81 rows")
        for row in rows:
            asset = db.get(Asset, row.asset_id)
            if row.state not in {"VERIFIED", "UNREADABLE"}:
                raise RuntimeError(f"Human queue incomplete: {row.sample_id} is {row.state}")
            if not _compatible(row, asset):
                raise RuntimeError(f"Source hash invalid: {row.sample_id}")
            if row.state == "VERIFIED" and not (row.human_transcription or "").strip():
                raise RuntimeError(f"Verified transcription missing: {row.sample_id}")
            human_samples.append({
                "sample_id": row.sample_id, "asset_id": row.asset_id, "page_order": row.page_order,
                "logical_region_id": row.logical_region_id, "source_hash": row.source_image_hash,
                "representation_hash": row.representation_hash, "state": row.state,
                "human_transcription": row.human_transcription if row.state == "VERIFIED" else None,
                "provenance": row.provenance, "revision": row.revision,
            })
    finally:
        db.close()
    verified = [sample for sample in human_samples if sample["state"] == "VERIFIED"]
    unreadable = [sample for sample in human_samples if sample["state"] == "UNREADABLE"]
    if len(verified) != 71 or len(unreadable) != 10:
        raise RuntimeError(f"Human-confirmed split changed: {len(verified)} VERIFIED / {len(unreadable)} UNREADABLE")
    if calibration_hashes & validation_hashes or len(validation_hashes) != 10:
        raise RuntimeError("Calibration/validation separation failed")

    started = time.perf_counter_ns()
    evaluated = []
    totals = Counter()
    taxonomy = Counter()
    high_wrong = []
    structural_wrong = []
    char_errors = human_chars = word_errors = human_words = exact = 0
    for human in human_samples:
        frozen = sample_by_id[human["sample_id"]]
        state = route(frozen["features"], "R2")
        item = {**human, "ocr_prediction": frozen["prediction"], "source_fragment_ids": frozen["source_fragment_ids"], "features": frozen["features"], "r2_state": state}
        totals[state] += 1
        if human["state"] == "VERIFIED":
            predicted, truth = norm(frozen["prediction"]), norm(human["human_transcription"])
            item["exact"] = predicted == truth
            item["char_errors"] = distance(predicted, truth)
            item["human_chars"] = len(truth)
            item["word_errors"] = distance(predicted.split(), truth.split())
            item["human_words"] = len(truth.split())
            item["error_types"] = [] if item["exact"] else text_error_types(frozen["prediction"], human["human_transcription"])
            exact += item["exact"]
            char_errors += item["char_errors"]
            human_chars += item["human_chars"]
            word_errors += item["word_errors"]
            human_words += item["human_words"]
            for error_type in item["error_types"]:
                taxonomy[error_type] += 1
            if not item["exact"] and frozen["features"]["min_confidence"] >= .98:
                case = {key: item[key] for key in ("sample_id", "page_order", "logical_region_id", "ocr_prediction", "human_transcription", "source_fragment_ids", "features", "r2_state", "error_types")}
                case["r2_prevented_safe"] = state != SAFE
                high_wrong.append(case)
            if not item["exact"] and (frozen["features"]["merge_split_warning"] or frozen["features"]["boundary_clipping_warning"]):
                structural_wrong.append(item["sample_id"])
        else:
            item["unreadable_safe_risk"] = state == SAFE
        evaluated.append(item)
    routing_ns = time.perf_counter_ns() - started
    verified_rows = [row for row in evaluated if row["state"] == "VERIFIED"]
    verified_states = Counter(row["r2_state"] for row in verified_rows)
    safe_rows = [row for row in verified_rows if row["r2_state"] == SAFE]
    safe_correct = sum(row["exact"] for row in safe_rows)
    false_safe = len(safe_rows) - safe_correct
    unreadable_rows = [row for row in evaluated if row["state"] == "UNREADABLE"]
    unreadable_states = Counter(row["r2_state"] for row in unreadable_rows)
    unreadable_risks = [row["sample_id"] for row in unreadable_rows if row["r2_state"] == SAFE]
    multi = [row for row in verified_rows if row["features"]["fragment_count"] > 1]
    boundary = [row for row in verified_rows if row["features"]["boundary_clipping_warning"]]
    structural = [row for row in verified_rows if row["features"]["merge_split_warning"] or row["features"]["boundary_clipping_warning"]]
    structural_errors = [row for row in structural if not row["exact"]]
    structural_false = [row for row in structural_errors if row["r2_state"] == SAFE]
    metrics = {
        "verified_transcriptions": len(verified_rows), "safe_count": len(safe_rows),
        "safe_coverage": len(safe_rows) / len(verified_rows), "safe_correct": safe_correct,
        "false_safe": false_safe, "false_safe_rate": false_safe / len(safe_rows) if safe_rows else 0.0,
        "safe_precision": safe_correct / len(safe_rows) if safe_rows else None,
        "hard_count": verified_states[HARD], "hard_rate": verified_states[HARD] / len(verified_rows),
        "structural_review_count": verified_states[STRUCTURAL], "structural_review_rate": verified_states[STRUCTURAL] / len(verified_rows),
        "exact_match": {"correct": exact, "accuracy": exact / len(verified_rows)},
        "normalized_cer": char_errors / human_chars if human_chars else 0.0,
        "wer": word_errors / human_words if human_words else 0.0,
    }
    unreadable_metrics = {
        "total": len(unreadable_rows), "safe_candidate": unreadable_states[SAFE], "hard": unreadable_states[HARD],
        "structural_review": unreadable_states[STRUCTURAL], "unreadable_safe_risk": len(unreadable_risks),
        "unreadable_safe_risk_samples": unreadable_risks,
    }
    leakage = {
        "calibration_samples_excluded": len(calibration["pages"]) == 10,
        "validation_pages_unseen": not bool(calibration_hashes & validation_hashes),
        "source_hashes_unique_and_separated": len(validation_hashes) == 10 and not bool(calibration_hashes & validation_hashes),
        "human_gt_not_router_feature": all("human" not in key.lower() and "gt" not in key.lower() for sample in manifest["samples"] for key in sample["features"]),
        "annotation_payload_blinded": set(manifest["annotation_blinding"]) == {"prediction", "confidence", "R2 state"},
    }
    if false_safe:
        decision = "C. R2 GENERALIZATION FAIL"
        next_action = "11.14: improve logical crop/merge/split reconstruction on the observed false-safe and structural-review cases; keep R2 frozen and do not threshold-tune."
    elif len(safe_rows) / len(verified_rows) < .05 or unreadable_risks:
        decision = "B. R2 SAFE BUT TOO CONSERVATIVE"
        next_action = "11.14: benchmark deterministic processing for HARD/STRUCTURAL_REVIEW regions, prioritizing crop/merge/split reconstruction; preserve frozen R2 as an offline fast-path candidate."
    else:
        decision = "A. R2 VALIDATION PASS"
        next_action = "11.14: preserve frozen R2 as a fast-path candidate and benchmark the remaining HARD/STRUCTURAL_REVIEW processing."
    after_authoritative = authoritative_snapshot(PROJECT)["state_hash"]
    after_resources = sample_resources(thresholds)
    swap_delta = after_resources["swap_used_bytes"] - before_resources["swap_used_bytes"] if isinstance(after_resources["swap_used_bytes"], int) and isinstance(before_resources["swap_used_bytes"], int) else None
    human_artifact = {
        "schema_version": "reader-router-validation-human-gt.v1", "checkpoint": "11.13", "status": "HUMAN_COMPLETE",
        "total_queue": len(human_samples), "verified_regions": len(verified), "unreadable_regions": len(unreadable),
        "pending_regions": 0, "source_unavailable_regions": 0, "ground_truth_source": "human-only",
        "human_confirmation": "10 UNREADABLE labels intentional", "samples": human_samples,
    }
    results_artifact = {
        "schema_version": "reader-router-validation-results.v1", "checkpoint": "11.13", "router": "R2",
        "frozen_rule": manifest["frozen_router"], "total_human_queue": 81, "metrics_verified_only": metrics,
        "unreadable_safety": unreadable_metrics, "all_queue_routing": {"safe_candidate": totals[SAFE], "hard": totals[HARD], "structural_review": totals[STRUCTURAL]},
        "routing_nanoseconds": routing_ns, "nanoseconds_per_sample": routing_ns / len(evaluated), "samples": evaluated,
    }
    errors_artifact = {
        "schema_version": "reader-router-validation-errors.v1", "checkpoint": "11.13",
        "high_confidence_wrong_count": len(high_wrong), "high_confidence_wrong_cases": high_wrong,
        "any_high_confidence_wrong_satisfied_all_safe_conditions": any(case["r2_state"] == SAFE for case in high_wrong),
        "error_taxonomy": dict(taxonomy),
        "structural_analysis": {
            "multiple_fragment_samples": len(multi), "crop_boundary_samples": len(boundary),
            "structural_signal_samples": len(structural), "structural_error_samples": len(structural_errors),
            "structural_errors_routed_away_from_safe": len(structural_errors) - len(structural_false),
            "structural_errors_false_safe": len(structural_false),
            "structural_error_frequency_verified": len(structural_errors) / len(verified_rows),
            "merged_reconstruction_errors": sum(not row["exact"] for row in multi),
            "split_reconstruction_errors": 0,
            "note": "Persisted data identifies multi-fragment aggregation/merge warnings; it has no independent split-reconstruction label, so split count is not inferred.",
            "sample_ids": structural_wrong,
        },
        "unreadable_safe_risk_samples": unreadable_risks,
    }
    summary_artifact = {
        "schema_version": "reader-router-validation-summary.v1", "checkpoint": "11.13", "decision": decision,
        "interpretation": "OUT-OF-SAMPLE PROMISING" if not false_safe and not unreadable_risks else "NOT PRODUCTION-SAFE",
        "human_completeness": {"total": 81, "verified": 71, "unreadable": 10, "pending": 0, "source_unavailable": 0},
        "leakage_checks": leakage,
        "calibration_vs_validation": {
            "calibration_11_12": {"n": 50, "safe": 1, "safe_coverage": .02, "false_safe": 0, "safe_precision": 1.0},
            "validation_11_13_verified": {"n": 71, "safe": len(safe_rows), "safe_coverage": metrics["safe_coverage"], "false_safe": false_safe, "safe_precision": metrics["safe_precision"]},
            "combined_non_independent_descriptive": {"n": 121, "safe": 1 + len(safe_rows), "false_safe": false_safe, "note": "Excludes 10 unreadable validation samples; calibration data was used to select R2."},
        },
        "metrics_verified_only": metrics, "unreadable_safety": unreadable_metrics,
        "resource_safety": {"before": before_resources, "after": after_resources, "swap_delta_bytes": swap_delta, "ocr_inference_calls": 0, "vlm_calls": 0, "ollama_calls": 0},
        "preservation": {"manifest_unchanged": manifest_hash == hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), "manifest_sha256": manifest_hash, "authoritative_state_unchanged": before_authoritative == after_authoritative, "human_gt_mutated_by_analysis": False, "production_changes": False},
        "reading_order_deferred": "shared tier/row grouping geometry; unchanged", "recommended_11_14_experiment": next_action,
        "artifact_content_hashes": {"human_gt": stable_hash(human_artifact), "results": stable_hash(results_artifact), "errors": stable_hash(errors_artifact)},
    }
    for path, artifact in ((HUMAN, human_artifact), (RESULTS, results_artifact), (ERRORS, errors_artifact), (SUMMARY, summary_artifact)):
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    return summary_artifact


if __name__ == "__main__":
    summary = build()
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics_verified_only"], "unreadable": summary["unreadable_safety"], "leakage": summary["leakage_checks"], "resources": summary["resource_safety"]}, ensure_ascii=False))
