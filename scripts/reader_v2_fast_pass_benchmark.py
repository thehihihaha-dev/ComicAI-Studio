#!/usr/bin/env python3
"""Read-only Checkpoint 11.8 benchmark for the isolated Reader V2 Fast Pass."""

from __future__ import annotations

import importlib.metadata, json, os, sys, time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]; BACKEND = ROOT / "backend"
sys.path[:0] = [str(BACKEND), str(ROOT / "scripts")]; load_dotenv(BACKEND / ".env"); os.chdir(BACKEND)
from app.services.reader_v2_fast_pass import ReaderV2FastPass, ReadingOrderPolicy  # noqa: E402
from app.services.resource_safety import CRITICAL, ResourceThresholds, sample_resources  # noqa: E402
from reader_benchmark import authoritative_snapshot  # noqa: E402
from reader_benchmark_11_4 import evaluate  # noqa: E402
from reader_benchmark_lib import stable_hash  # noqa: E402

DAY11 = ROOT / "benchmarks/day11"
HUMAN = DAY11 / "reader-human-verified-11.6.json"
BASELINE = DAY11 / "reader-line-aware-samples-11.7.json"
FAST = DAY11 / "reader-v2-fast-pass-11.8.json"
ERRORS = DAY11 / "reader-v2-fast-pass-errors-11.8.json"
ORDER = DAY11 / "reader-v2-reading-order-11.8.json"
PERFORMANCE = DAY11 / "reader-v2-performance-11.8.json"
SCHEMA = "reader-v2-fast-pass.v1"


class EasyOCRAdapter:
    name = "easyocr"
    version = importlib.metadata.version("easyocr")
    config = {"languages": ["vi", "en"], "gpu": False, "detail": 1}

    def __init__(self) -> None:
        import easyocr
        self.reader = easyocr.Reader(self.config["languages"], gpu=False)

    def read(self, crop: Any) -> list[dict[str, Any]]:
        values = self.reader.readtext(crop, detail=1)
        return [{"id": index, "bbox": [[float(point[0]), float(point[1])] for point in box],
                 "text": str(text), "confidence": float(confidence)}
                for index, (box, text, confidence) in enumerate(values)]


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    edits = Counter(); chars = sum(len(item["reference_raw"]) for item in results)
    for item in results: edits.update(item["edit_operations"])
    return {"N": len(results), "raw_exact": sum(item["raw_exact_match"] for item in results),
            "normalized_exact": sum(item["normalized_exact_match"] for item in results),
            "micro_raw_cer": sum(edits.values()) / chars if chars else None,
            "mean_normalized_cer": sum(item["normalized_cer"] for item in results) / len(results),
            "mean_wer": sum(item["wer"] for item in results) / len(results),
            "missing": sum(item["missing_text"] for item in results), "edit_counts": dict(edits)}


def write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run() -> tuple[dict, dict, dict, dict]:
    human = json.loads(HUMAN.read_text()); baseline = json.loads(BASELINE.read_text())
    if human["sample_count"] != 20: raise RuntimeError("11.8 requires exactly 20 frozen VERIFIED samples")
    frozen = stable_hash([{"id": x["sample_id"], "gt": x["ground_truth"], "crop": x["crop_hash"]} for x in human["samples"]])
    project_ids = sorted({x["project_id"] for x in human["samples"]}); before = {x: authoritative_snapshot(x)["state_hash"] for x in project_ids}
    thresholds = ResourceThresholds.from_environment(); resources_before = sample_resources(thresholds)
    if resources_before["safety_state"] == CRITICAL: raise SystemExit("FAIL — MACHINE SAFETY before Reader V2 inference")
    init_started = time.perf_counter(); engine = EasyOCRAdapter(); init_seconds = time.perf_counter() - init_started
    runner = ReaderV2FastPass(engine, padding=.02, policy=ReadingOrderPolicy.MANGA_RTL)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list); sample_by_key = {}
    for sample in human["samples"]:
        grouped[sample["asset_id"]].append({"id": sample["region_id"], "bbox": sample["bbox"], "type": sample["text_role"]})
        sample_by_key[(sample["asset_id"], sample["region_id"])] = sample
    pages = []; benchmark_started = time.perf_counter()
    for asset_id, regions in sorted(grouped.items(), key=lambda pair: min(sample_by_key[(pair[0], x["id"])]["page_order"] for x in pair[1])):
        sample = sample_by_key[(asset_id, regions[0]["id"])]
        pages.append(runner.run(sample["source_path"], asset_id, sample["source_image_hash"], regions, panels=None))
        if sample_resources(thresholds)["safety_state"] == CRITICAL: raise SystemExit("FAIL — MACHINE SAFETY during Reader V2 benchmark")
    benchmark_seconds = time.perf_counter() - benchmark_started
    baseline_by = {x["sample_id"]: x for x in baseline["mode_b_padding_grid"]["0.02"]}
    results = []
    for page in pages:
        for region in page["regions"]:
            sample = sample_by_key[(page["asset_id"], region["region_id"])]
            measured = evaluate(sample["ground_truth"], region["ocr"]["text"], region["ocr"]["confidence"])
            prior = baseline_by[sample["sample_id"]]
            results.append({"sample_id": sample["sample_id"], "asset_id": page["asset_id"], "page_order": sample["page_order"],
                            "region_id": region["region_id"], "ground_truth_source": "human_verified_frozen_11.6",
                            "routing_state": region["routing_state"], "quality_signals": region["quality_signals"],
                            "crop_bbox": region["crop_bbox"], "ocr": region["ocr"], **measured,
                            "baseline_11_7_normalized_cer": prior["normalized_cer"],
                            "cer_delta_vs_11_7": measured["normalized_cer"] - prior["normalized_cer"],
                            "regression_vs_11_7": measured["normalized_cer"] > prior["normalized_cer"] + 1e-12})
    metrics = aggregate(results); accepts = [x for x in results if x["routing_state"] == "ACCEPT_CANDIDATE"]
    false_accepts = [x for x in accepts if not x["normalized_exact_match"]]
    resources_after = sample_resources(thresholds); after = {x: authoritative_snapshot(x)["state_hash"] for x in project_ids}
    frozen_after = stable_hash([{"id": x["sample_id"], "gt": x["ground_truth"], "crop": x["crop_hash"]} for x in json.loads(HUMAN.read_text())["samples"]])
    if before != after or frozen != frozen_after: raise RuntimeError("authoritative or frozen GT state changed")
    fast = {"schema_version": SCHEMA, "checkpoint": "11.8", "artifact_kind": "fast_pass", "status": "completed", "N": 20,
            "engine": {"name": engine.name, "version": engine.version, "config": engine.config}, "padding": .02,
            "policy": ReadingOrderPolicy.MANGA_RTL.value, "pages": pages, "results": results, "metrics": metrics,
            "routing_counts": dict(Counter(x["routing_state"] for x in results)), "vlm_calls": 0, "ollama_calls": 0}
    errors = {"schema_version": SCHEMA, "checkpoint": "11.8", "artifact_kind": "errors", "status": "completed", "N": 20,
              "incorrect": [x for x in results if not x["normalized_exact_match"]],
              "regressions_vs_11_7": [x for x in results if x["regression_vs_11_7"]],
              "false_accept_analysis": {"accepted": len(accepts), "false_accepts": len(false_accepts),
                                        "false_accept_rate": len(false_accepts)/len(accepts) if accepts else None,
                                        "note": "ACCEPT_CANDIDATE is non-authoritative; rules were not tuned on GT."}}
    order = {"schema_version": SCHEMA, "checkpoint": "11.8", "artifact_kind": "reading_order", "status": "completed", "N": 20,
             "policy": ReadingOrderPolicy.MANGA_RTL.value, "pages": [{"asset_id": p["asset_id"], "reading_order": p["reading_order"],
             "detail": p["reading_order_detail"]} for p in pages], "panel_detection": "not run; page fallback groups reuse benchmark-safe logical regions"}
    performance = {"schema_version": SCHEMA, "checkpoint": "11.8", "artifact_kind": "performance", "status": "completed", "N": 20,
                   "initialization_seconds": init_seconds, "benchmark_wall_seconds": benchmark_seconds,
                   "stage_seconds": {key: sum(p["stats"][key] for p in pages) for key in ("crop_seconds", "ocr_inference_seconds", "reading_order_seconds", "wall_clock_seconds")},
                   "resources": {"before": resources_before, "after": resources_after,
                                 "peak_rss_bytes": max(resources_before["process_peak_rss_bytes"], resources_after["process_peak_rss_bytes"]),
                                 "swap_delta_bytes": resources_after["swap_used_bytes"]-resources_before["swap_used_bytes"],
                                 "safety_state": resources_after["safety_state"]}, "model_calls": {"vlm": 0, "ollama": 0},
                   "authoritative_state_unchanged": True, "concurrency": 1}
    for path, payload in ((FAST, fast), (ERRORS, errors), (ORDER, order), (PERFORMANCE, performance)): write(path, payload)
    return fast, errors, order, performance


if __name__ == "__main__":
    fast, errors, _, _ = run()
    print(json.dumps({"metrics": fast["metrics"], "false_accept": errors["false_accept_analysis"]}, ensure_ascii=False))
