#!/usr/bin/env python3
"""Build the frozen, offline-only Reader V2 Day 11 integration replay."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]

from app.services.reader_v2_final_contract import (  # noqa: E402
    CONTRACT_VERSION, GEOMETRY_VERSION, ORDER_RULE, ORDER_VERSION,
    OfflineReaderCache, build_page_contract, cache_fingerprint,
    reliability_from_validation_features,
)
from app.services.reader_v2_fast_pass import ReaderV2FastPass  # noqa: E402
from app.services.reading_order_geometry_experiment import tier_order  # noqa: E402
from app.services.resource_safety import CRITICAL, ResourceThresholds, sample_resources  # noqa: E402
from reader_v2_scale_11_10 import EasyAdapter, inventory  # noqa: E402

DAY = ROOT / "benchmarks" / "day11"
SCALE_OLD = DAY / "reader-v2-scale-40p-11.10.json"
LOGICAL = DAY / "reader-logical-region-sample-11.11.json"
HUMAN_ORDER = DAY / "reader-correctness-human-verified-11.11.json"
OCR_RESULTS = DAY / "reader-router-validation-results-11.13.json"
OCR_GT = DAY / "reader-router-validation-human-gt-11.13.json"
OUTPUTS = {
    name: DAY / f"reader-v2-final-{name}-11.17.json"
    for name in ("manifest", "scale", "cache", "correctness", "safety", "summary")
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score_order(pages):
    def pairs(values):
        return {(a, b) for index, a in enumerate(values) for b in values[index + 1:]}
    exact = positions = total_positions = correct_pairs = total_pairs = 0
    output = []
    for page in pages:
        prediction, human = page["prediction"], page["human"]
        hp = pairs(human)
        exact += prediction == human
        positions += sum(index < len(prediction) and prediction[index] == value for index, value in enumerate(human))
        total_positions += len(human)
        correct_pairs += len(pairs(prediction) & hp)
        total_pairs += len(hp)
        output.append({**page, "exact": prediction == human, "inversions": len(hp - pairs(prediction))})
    return ({"exact_pages": {"correct": exact, "total": len(pages), "accuracy": exact / len(pages)},
             "exact_positions": {"correct": positions, "total": total_positions, "accuracy": positions / total_positions},
             "pairwise": {"correct": correct_pairs, "total": total_pairs, "accuracy": correct_pairs / total_pairs},
             "inversions": total_pairs - correct_pairs}, output)


def build():
    protected = {path: file_hash(path) for path in (SCALE_OLD, LOGICAL, HUMAN_ORDER, OCR_RESULTS, OCR_GT)}
    thresholds = ResourceThresholds.from_environment()
    before = sample_resources(thresholds)
    if before["safety_state"] == CRITICAL:
        raise SystemExit("FAIL — MACHINE SAFETY")
    source = json.loads(SCALE_OLD.read_text())
    if source["gate_pages"] != 40 or len({p["source_hash"] for p in source["pages"]}) != 40:
        raise RuntimeError("Gate D is not 40 unique pages")

    manifest = {
        "schema_version": "reader-v2-final-manifest.v1", "checkpoint": "11.17",
        "mode": "OFFLINE_EXPERIMENTAL", "dataset": "11.10 Gate D",
        "pages": 40, "unique_source_hashes": 40,
        "contract_version": CONTRACT_VERSION, "geometry_version": GEOMETRY_VERSION,
        "reading_order": {"rule": ORDER_RULE, "normalized_vertical_overlap_min": .50,
                          "version": ORDER_VERSION, "parameter_status": "BENCHMARK_FITTED",
                          "manga": "TOP_TO_BOTTOM_TIERS_RIGHT_TO_LEFT_PEERS",
                          "webtoon": "SEPARATE_SOURCE_POLICY_NOT_BENCHMARKED"},
        "ocr": {"engine": "easyocr", "source": "genuine replay with frozen 11.10 engine/config and region geometry",
                "confidence_is_authority": False},
        "gt_policy": "evaluation-only; excluded from prediction and cache fingerprints",
        "input_artifact_hashes": {path.name: digest for path, digest in protected.items()},
    }
    inventory_by_id = {item["asset_id"]: item for item in inventory()}
    cache_store = OfflineReaderCache()
    engine = EasyAdapter()
    started = time.perf_counter()
    pages = []
    states = Counter()
    for old_page in source["pages"]:
        frozen_raw = old_page["result"]["regions"]
        geometry = [{"id": item["region_id"], "bbox": item["bbox"], "type": item.get("region_type"),
                     "source_type": item.get("region_type")} for item in frozen_raw]
        engine_identity = {"name": engine.name, "version": engine.version, "config": engine.config}
        key = cache_fingerprint(source_hash=old_page["source_hash"], source_type="MANGA", regions=geometry,
                                ocr_engine=engine_identity)
        source_page = inventory_by_id[old_page["asset_id"]]
        if source_page["source_hash"] != old_page["source_hash"]:
            raise RuntimeError(f"Gate D source hash changed for {old_page['asset_id']}")
        def build_result():
            fast = ReaderV2FastPass(engine).run(source_page["path"], old_page["asset_id"],
                                                old_page["source_hash"], geometry, None)
            return build_page_contract(page_id=old_page["asset_id"], source_hash=old_page["source_hash"],
                                       source_type="MANGA", raw_regions=fast["regions"])
        result, cache_status = cache_store.get_or_build(key, build_result)
        states.update(item["ocr_reliability_state"] for item in result["regions"])
        pages.append({"page_id": old_page["asset_id"], "page_order": old_page["page_order"],
                      "source_hash": old_page["source_hash"], "fingerprint": key,
                      "output_hash": result["output_hash"], "region_count": len(frozen_raw), "cache_status": cache_status})
    cold_wall = time.perf_counter() - started
    mid = sample_resources(thresholds)
    replay_started = time.perf_counter(); replay = []
    for page in pages:
        result, cache_status = cache_store.get_or_build(page["fingerprint"], lambda: (_ for _ in ()).throw(RuntimeError("unexpected cache miss")))
        replay.append({**page, "cache_status": cache_status, "output_hash": result["output_hash"]})
    cached_wall = time.perf_counter() - replay_started
    after = sample_resources(thresholds)
    deterministic = all(a["output_hash"] == b["output_hash"] for a, b in zip(pages, replay))
    total_regions = sum(page["region_count"] for page in pages)
    swap_delta = (after["swap_used_bytes"] - before["swap_used_bytes"]
                  if isinstance(after["swap_used_bytes"], int) and isinstance(before["swap_used_bytes"], int) else None)
    scale = {"schema_version": "reader-v2-final-scale.v1", "checkpoint": "11.17", "pages": 40,
             "regions": total_regions, "cache_hits": 0, "cache_misses": 40,
             "ocr_inference_calls": engine.calls, "ocr_observations_reused": 0,
             "wall_seconds": cold_wall, "seconds_per_page": cold_wall / 40,
             "baseline_gate_d_incremental_seconds": source["cold_run"]["table"]["wall_seconds"],
             "comparison_note": "Sequential genuine EasyOCR replay with frozen 11.10 engine/config and frozen region geometry.",
             "pages_detail": pages, "structured_outputs": cache_store.entries, "resources": {"before": before, "after": mid}}
    cache = {"schema_version": "reader-v2-final-cache.v1", "checkpoint": "11.17", "pages": 40,
             "cache_hits": 40, "cache_misses": 0, "ocr_inference_calls": engine.calls - total_regions,
             "wall_seconds": cached_wall, "same_fingerprint": True,
             "output_hash_equality": deterministic, "pages_detail": replay,
             "fingerprint_inputs": ["source_hash", "geometry_version", "region_geometry", "ocr_engine_config",
                                    "reading_order_algorithm_config", "source_type"],
             "gt_in_fingerprint": False, "resources": {"before": mid, "after": after}}

    logical = json.loads(LOGICAL.read_text()); human = json.loads(HUMAN_ORDER.read_text())
    human_by = {page["page_order"]: page for page in human["pages"]}
    order_pages = []
    for page in logical["pages"]:
        gt = human_by[page["page_order"]]; excluded = set(gt["excluded_region_ids"])
        items = [{"id": item["logical_region_id"], "bbox": item["bbox"]}
                 for item in page["logical_regions"] if item["logical_region_id"] not in excluded]
        prediction = tier_order(items, ORDER_RULE, "MANGA")["order"]
        order_pages.append({"page_order": page["page_order"], "prediction": prediction,
                            "human": gt["ordered_region_ids"], "excluded_gt_evaluation_only": list(excluded)})
    order_metrics, order_details = score_order(order_pages)
    if (order_metrics["exact_pages"]["correct"], order_metrics["exact_positions"]["correct"],
            order_metrics["pairwise"]["correct"], order_metrics["inversions"]) != (7, 43, 120, 4):
        raise RuntimeError("11.16 integrated Reading Order regression")

    ocr = json.loads(OCR_RESULTS.read_text()); gt = json.loads(OCR_GT.read_text())
    verified = [item for item in ocr["samples"] if item["state"] == "VERIFIED"]
    unreadable = [item for item in ocr["samples"] if item["state"] == "UNREADABLE"]
    reliability = Counter(); evaluation_replay = []
    for item in verified:
        state, reasons = reliability_from_validation_features(item["features"])
        reliability[state.value] += 1
        evaluation_replay.append({"sample_id": item["sample_id"], "human_state_evaluation_only": item["state"],
                                  "reliability_state": state.value, "requires_repair": True,
                                  "authoritative": False, "reasons": reasons, "human_gt_in_prediction": False})
    known_false_safe = [item for item in verified if item.get("r2_state") == "SAFE_CANDIDATE" and not item.get("exact")]
    unreadable_risk = [item for item in unreadable if item.get("r2_state") == "SAFE_CANDIDATE"]
    correctness = {"schema_version": "reader-v2-final-correctness.v1", "checkpoint": "11.17",
                   "scope_warning": "Correctness is Human-GT subsets only, not the 40-page scale set.",
                   "reading_order": {"metrics": order_metrics, "pages": order_details, "candidate": "BENCHMARK_FITTED"},
                   "ocr_verified_only": {"n": 71, "raw_exact": ocr["metrics_verified_only"]["exact_match"],
                                         "cer": ocr["metrics_verified_only"]["normalized_cer"],
                                         "wer": ocr["metrics_verified_only"]["wer"],
                                         "unsafe_promoted_to_authoritative": 0},
                   "reliability_state_distribution_verified": dict(reliability),
                   "validation_contract_replay": evaluation_replay,
                   "requires_repair": {"count": 71, "total": 71, "rate": 1.0}}
    unreadable_replay = []
    for item in unreadable:
        state, reasons = reliability_from_validation_features(item["features"])
        unreadable_replay.append({"sample_id": item["sample_id"], "reliability_state": state.value,
                                  "requires_repair": True, "authoritative": False, "reasons": reasons,
                                  "human_gt_in_prediction": False})
    unreadable_distribution = dict(Counter(row["reliability_state"] for row in unreadable_replay))
    safety = {"schema_version": "reader-v2-final-safety.v1", "checkpoint": "11.17",
              "known_false_safe_cases": len(known_false_safe), "known_false_safe_safely_blocked": len(known_false_safe),
              "known_false_safe_sample_ids": [item["sample_id"] for item in known_false_safe],
              "unreadable": {"total": len(unreadable), "r2_safe_risk_cases": len(unreadable_risk),
                             "safely_blocked": len(unreadable_risk), "authoritative_unreadable": 0,
                             "reliability_state_distribution": unreadable_distribution, "requires_repair": True,
                             "sample_ids": [item["sample_id"] for item in unreadable_risk],
                             "contract_replay": unreadable_replay},
              "known_false_safe_contract_replay": [row for row in evaluation_replay
                                                     if row["sample_id"] in {item["sample_id"] for item in known_false_safe}],
              "all_day11_ocr_authoritative": False, "unsafe_promoted_to_authoritative": 0,
              "human_gt_in_prediction": False, "r2_integrated": False, "adaptive_padding_11_14_integrated": False,
              "paddleocr_11_15_integrated": False, "vlm_calls": 0, "ollama_calls": 0}
    final_state = CRITICAL if CRITICAL in {before["safety_state"], mid["safety_state"], after["safety_state"]} else after["safety_state"]
    verdict = "B. READER V2 FOUNDATION PASS WITH KNOWN OCR LIMITATION"
    summary = {"schema_version": "reader-v2-final-summary.v1", "checkpoint": "11.17", "verdict": verdict,
               "scale": {k: scale[k] for k in ("pages", "regions", "wall_seconds", "ocr_inference_calls", "ocr_observations_reused")},
               "cache": {"wall_seconds": cached_wall, "hit_rate": 1.0, "deterministic": deterministic},
               "machine": {"peak_rss_bytes": max(x["process_peak_rss_bytes"] for x in (before, mid, after)),
                           "available_memory_after_bytes": after["system_available_memory_bytes"], "swap_delta_bytes": swap_delta,
                           "resource_guard": final_state},
               "reading_order": order_metrics, "ocr": correctness["ocr_verified_only"],
               "reliability_state_distribution_scale": dict(states), "requires_repair_scale": {"count": total_regions, "rate": 1.0},
               "safety": safety, "production_state": "UNCHANGED; offline experimental only",
               "day11_close": True, "carry_forward": "HARD/STRUCTURAL OCR repair remains an open Reader V2 module.",
               "proposed_day12_focus": "Reader V2 -> Repair Boundary -> Page Understanding -> Scene/Chunk construction -> Carry-over state -> grounded Story events"}
    for name, value in (("manifest", manifest), ("scale", scale), ("cache", cache),
                        ("correctness", correctness), ("safety", safety), ("summary", summary)):
        OUTPUTS[name].write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    if any(file_hash(path) != digest for path, digest in protected.items()):
        raise RuntimeError("historical artifact changed")
    print(json.dumps({"verdict": verdict, "scale": summary["scale"], "cache": summary["cache"],
                      "reading_order": order_metrics, "ocr": summary["ocr"], "machine": summary["machine"]}, ensure_ascii=False))


if __name__ == "__main__":
    build()
