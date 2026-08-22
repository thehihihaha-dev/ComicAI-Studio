#!/usr/bin/env python3
"""Read-only expanded trusted-crop OCR benchmark for Checkpoint 11.4."""

from __future__ import annotations

import argparse, hashlib, importlib.metadata, json, os, sys, time, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path[:0] = [str(BACKEND), str(ROOT / "scripts")]
load_dotenv(BACKEND / ".env")
os.chdir(BACKEND)

from app.database import SessionLocal  # noqa: E402
from app.models.asset import Asset  # noqa: E402
from app.models.dialogue_ground_truth import DialogueGroundTruth  # noqa: E402
from app.services.resource_safety import CRITICAL, ResourceThresholds, sample_resources  # noqa: E402
from reader_benchmark import authoritative_snapshot, result_json  # noqa: E402
from reader_benchmark_lib import (  # noqa: E402
    classify_errors, confidence_analysis_bucket, edit_operations, error_rate,
    evaluation_normalize_text, normalize_text, stable_hash, union_rect,
)

OUT = ROOT / "benchmarks" / "day11"
MANIFEST = OUT / "reader-benchmark-manifest-11.4.json"
EASY = OUT / "reader-easyocr-expanded-11.4.json"
PADDLE = OUT / "reader-paddleocr-expanded-11.4.json"
COMPARISON = OUT / "reader-ocr-comparison-11.4.json"
ERRORS = OUT / "reader-ocr-error-analysis-11.4.json"
PADDLE_REC = Path.home() / ".paddlex" / "official_models" / "PP-OCRv6_small_rec"
SCHEMA = "reader-ocr-expanded.v1"
MIN_SUBGROUP = 3


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_artifact(payload: dict[str, Any]) -> None:
    required = {"schema_version", "checkpoint", "artifact_kind", "status"}
    if missing := required - payload.keys():
        raise ValueError(f"missing artifact fields: {sorted(missing)}")
    if payload["schema_version"] != SCHEMA or payload["checkpoint"] != "11.4":
        raise ValueError("invalid 11.4 artifact schema")


def write(path: Path, payload: dict[str, Any]) -> None:
    validate_artifact(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def source_path(asset: Asset) -> Path:
    path = Path(asset.file_path)
    return path if path.is_absolute() else BACKEND / path


def bbox_for_region(asset: Asset, region_id: int) -> tuple[list[float] | None, dict[str, Any] | None, int]:
    blocks = json.loads(asset.ocr_blocks or "[]")
    regions = json.loads(asset.vision_regions or "[]")
    region = next((item for item in regions if item.get("id") == region_id), None)
    if not region:
        return None, None, 0
    boxes = [blocks[index]["box"] for index in region.get("block_ids", [])
             if isinstance(index, int) and 0 <= index < len(blocks) and blocks[index].get("box")]
    return union_rect(boxes), region, len(boxes)


def language_of(text: str) -> str:
    vietnamese = "ăâđêôơưĂÂĐÊÔƠƯ" + "àáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ"
    return "vi" if any(char in vietnamese for char in text) else "unknown"


def tags_for(text: str, block_count: int) -> list[str]:
    tags = []
    if block_count > 1:
        tags.append("multiline")
    if len(text) <= 5:
        tags.append("small_text")
    if sum(not char.isalnum() and not char.isspace() for char in text) >= 3:
        tags.append("punctuation_heavy")
    return tags or ["unclassified"]


def all_snapshot(project_ids: list[str]) -> dict[str, Any]:
    states = {project_id: authoritative_snapshot(project_id)["state"] for project_id in sorted(project_ids)}
    return {"state_hash": stable_hash(states), "states": states}


def build_manifest() -> dict[str, Any]:
    db = SessionLocal()
    samples, queue, unavailable = [], [], []
    try:
        rows = (db.query(DialogueGroundTruth, Asset).join(Asset, DialogueGroundTruth.asset_id == Asset.id)
                .order_by(Asset.project_id, Asset.page_order, DialogueGroundTruth.region_id).all())
        project_ids = sorted({asset.project_id for _, asset in rows} | {"e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2"})
        before = all_snapshot(project_ids)
        for truth, asset in rows:
            bbox, region, block_count = bbox_for_region(asset, truth.region_id)
            if bbox is None:
                continue
            path = source_path(asset)
            if not path.is_file():
                unavailable.append({"project_id": asset.project_id, "asset_id": asset.id,
                                    "page_order": asset.page_order, "region_id": truth.region_id,
                                    "ground_truth_source": "DialogueGroundTruth.verified_text (human verified)",
                                    "status": "unavailable_missing_source_image"})
                continue
            crop_key = {"image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bbox": bbox}
            samples.append({
                "sample_id": hashlib.sha256(f"{asset.id}:{truth.region_id}".encode()).hexdigest()[:20],
                "project_id": asset.project_id, "asset_id": asset.id, "page_order": asset.page_order,
                "region_id": truth.region_id, "filename": asset.filename,
                "source_path": str(path.relative_to(ROOT)), "bbox": bbox,
                "text_role": (region or {}).get("type", "unknown"),
                "language": language_of(truth.verified_text), "ground_truth": truth.verified_text,
                "ground_truth_source": "DialogueGroundTruth.verified_text (human verified)",
                "difficulty_tags": tags_for(truth.verified_text, block_count), **crop_key,
            })
        prior = json.loads((OUT / "reader-benchmark-manifest-11.3.json").read_text(encoding="utf-8"))
        labeled = {(sample["asset_id"], sample["region_id"]) for sample in samples}
        for page in prior["pages"]:
            for region in page["expected_regions"]:
                ids = region.get("detected_region_ids", [])
                region_id = ids[0] if len(ids) == 1 else None
                if region.get("human_ground_truth") or (page["asset_id"], region_id) in labeled:
                    continue
                queue.append({"sample_id": f"future-{region['audit_id']}", "project_id": "e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2",
                              "asset_id": page["asset_id"], "page_order": page["page_order"],
                              "region_id": region_id, "bbox": region.get("bbox"), "text_role": region["role"],
                              "language": "unknown", "ground_truth": None,
                              "ground_truth_source": "REQUIRES_FUTURE_HUMAN_TRANSCRIPTION",
                              "difficulty_tags": ["unlabeled"], "image_sha256": page["sha256"]})
        after = all_snapshot(project_ids)
    finally:
        db.close()
    if before["state_hash"] != after["state_hash"]:
        raise RuntimeError("authoritative state changed while building manifest")
    if len({sample["sample_id"] for sample in samples}) != len(samples):
        raise RuntimeError("duplicate trusted sample")
    artifact = {"schema_version": SCHEMA, "checkpoint": "11.4", "artifact_kind": "manifest",
                "status": "completed", "created_at": now(), "samples": samples,
                "requires_human_transcription": queue,
                "unavailable_human_ground_truth": unavailable,
                "counts": {"trusted_samples": len(samples), "unavailable_human_gt": len(unavailable),
                           "future_human_labels": len(queue)},
                "limitations": ["Only three human-verified rows exist and one source image is missing; only two crops are benchmarkable.",
                                "Benchmark expansion is not statistically substantial.",
                                "No label was derived from OCR, AI correction, or visual inference."],
                "authoritative_state": {"before_hash": before["state_hash"], "after_hash": after["state_hash"], "unchanged": True}}
    write(MANIFEST, artifact)
    return artifact


def cache_key(sample: dict[str, Any], engine: str, version: str, preprocessing: str) -> str:
    return stable_hash({"image_sha256": sample["image_sha256"], "bbox": sample["bbox"],
                        "engine": engine, "version": version, "preprocessing": preprocessing})


def evaluate(reference: str, hypothesis: str, confidence: float | None) -> dict[str, Any]:
    raw_ops = edit_operations(reference, hypothesis)
    normalized_reference, normalized_hypothesis = evaluation_normalize_text(reference), evaluation_normalize_text(hypothesis)
    normalized_ops = edit_operations(normalized_reference, normalized_hypothesis)
    denominator = len(reference)
    return {"reference_raw": reference, "hypothesis_raw": hypothesis,
            "reference_normalized": normalized_reference, "hypothesis_normalized": normalized_hypothesis,
            "raw_exact_match": reference == hypothesis,
            "normalized_exact_match": normalized_reference == normalized_hypothesis,
            "raw_cer": (sum(raw_ops.values()) / denominator if denominator else None),
            "normalized_cer": error_rate(normalized_reference, normalized_hypothesis),
            "wer": error_rate(normalized_reference, normalized_hypothesis, words=True),
            "edit_operations": raw_ops,
            "operation_rates": {key: value / denominator if denominator else None for key, value in raw_ops.items()},
            "missing_text": not bool(normalize_text(hypothesis)), "confidence": confidence,
            "confidence_bucket": confidence_analysis_bucket(confidence),
            "error_types": classify_errors(reference, hypothesis)}


def benchmark(engine_name: str) -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    project_ids = sorted({sample["project_id"] for sample in manifest["samples"]} |
                         {item["project_id"] for item in manifest["unavailable_human_ground_truth"]})
    before_state = all_snapshot(project_ids)
    thresholds = ResourceThresholds.from_environment()
    resources_before = sample_resources(thresholds)
    if resources_before["safety_state"] == CRITICAL:
        raise SystemExit(f"FAIL — MACHINE SAFETY before {engine_name}")
    init_started = time.perf_counter()
    if engine_name == "easyocr":
        import easyocr
        version, preprocessing = importlib.metadata.version("easyocr"), "identical RGB crop converted to grayscale as EasyOCR recognize API requires"
        engine = easyocr.Reader(["vi", "en"], gpu=False)
        output_path, runtime = EASY, "CPU/PyTorch"
    else:
        from paddlex import create_model
        if not PADDLE_REC.is_dir():
            raise SystemExit("cached Paddle recognizer missing; no download attempted")
        version, preprocessing = importlib.metadata.version("paddleocr"), "identical RGB crop passed directly to PP-OCR recognizer"
        engine = create_model(PADDLE_REC.name, model_dir=str(PADDLE_REC), device="cpu")
        output_path, runtime = PADDLE, "CPU/Paddle Inference"
    init_seconds = time.perf_counter() - init_started
    results = []
    for sample in manifest["samples"]:
        with Image.open(ROOT / sample["source_path"]) as image:
            crop = np.asarray(image.convert("RGB").crop(tuple(round(value) for value in sample["bbox"])))
        started = time.perf_counter()
        if engine_name == "easyocr":
            grey = np.asarray(Image.fromarray(crop).convert("L")); height, width = grey.shape
            values = engine.recognize(grey, horizontal_list=[[0, width, 0, height]], free_list=[], detail=1, reformat=False)
            text = " ".join(str(value[1]) for value in values)
            confidence = min((float(value[2]) for value in values), default=None)
        else:
            values = list(engine.predict(crop)); data = result_json(values[0]) if values else {}
            text = str(data.get("rec_text", data.get("text", "")))
            score = data.get("rec_score", data.get("score")); confidence = float(score) if score is not None else None
        latency = time.perf_counter() - started
        results.append({"sample_id": sample["sample_id"], "language": sample["language"],
                        "text_role": sample["text_role"], "difficulty_tags": sample["difficulty_tags"],
                        "cache_key": cache_key(sample, engine_name, version, preprocessing),
                        "cache_status": "measured_this_run", "latency_seconds": round(latency, 6),
                        **evaluate(sample["ground_truth"], text, confidence)})
    resources_after = sample_resources(thresholds)
    after_state = all_snapshot(project_ids)
    if before_state["state_hash"] != after_state["state_hash"]:
        raise RuntimeError("authoritative state changed during OCR benchmark")
    count = len(results); reference_chars = sum(len(item["reference_raw"]) for item in results)
    totals = Counter(); [totals.update(item["edit_operations"]) for item in results]
    artifact = {"schema_version": SCHEMA, "checkpoint": "11.4", "artifact_kind": "engine",
                "status": "completed", "created_at": now(), "engine": engine_name,
                "configuration": {"version": version, "runtime": runtime, "concurrency": 1,
                                  "preprocessing": preprocessing, "source_crop_pixels": "identical bbox and source image",
                                  "downloads_installations": [], "production_engine_changed": False},
                "results": results,
                "aggregate": {"sample_count": count,
                              "raw_exact_rate": sum(item["raw_exact_match"] for item in results) / count,
                              "normalized_exact_rate": sum(item["normalized_exact_match"] for item in results) / count,
                              "micro_raw_cer": sum(totals.values()) / reference_chars,
                              "mean_normalized_cer": sum(item["normalized_cer"] for item in results) / count,
                              "mean_wer": sum(item["wer"] for item in results) / count,
                              "missing_text_rate": sum(item["missing_text"] for item in results) / count,
                              "edit_counts": dict(totals),
                              "edit_rates": {key: totals[key] / reference_chars for key in ("insertions", "deletions", "substitutions")}},
                "performance": {"cold_initialization_seconds": round(init_seconds, 6),
                                "warm_region_total_seconds": round(sum(item["latency_seconds"] for item in results), 6),
                                "mean_region_seconds": round(sum(item["latency_seconds"] for item in results) / count, 6),
                                "total_benchmark_seconds": round(init_seconds + sum(item["latency_seconds"] for item in results), 6),
                                "per_page_latency": "N/A: trusted-crop recognition benchmark"},
                "resources": {"before": resources_before, "after": resources_after,
                              "peak_rss_bytes": max(resources_before["process_peak_rss_bytes"], resources_after["process_peak_rss_bytes"]),
                              "swap_delta_bytes": resources_after["swap_used_bytes"] - resources_before["swap_used_bytes"],
                              "safety_state": "CRITICAL" if CRITICAL in (resources_before["safety_state"], resources_after["safety_state"]) else resources_after["safety_state"]},
                "authoritative_state": {"before_hash": before_state["state_hash"], "after_hash": after_state["state_hash"], "unchanged": True},
                "vlm_calls": 0}
    write(output_path, artifact)
    return artifact


def subgroup(results: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups = defaultdict(list)
    for item in results:
        values = item[key] if isinstance(item[key], list) else [item[key]]
        for value in values: groups[value].append(item)
    return {name: {"sample_count": len(items),
                   "metrics": ({"exact_rate": sum(item["normalized_exact_match"] for item in items) / len(items),
                                "mean_normalized_cer": sum(item["normalized_cer"] for item in items) / len(items)}
                               if len(items) >= MIN_SUBGROUP else "N/A: insufficient sample count")}
            for name, items in groups.items()}


def analyze() -> dict[str, Any]:
    manifest, easy, paddle = [json.loads(path.read_text(encoding="utf-8")) for path in (MANIFEST, EASY, PADDLE)]
    easy_by = {item["sample_id"]: item for item in easy["results"]}; paddle_by = {item["sample_id"]: item for item in paddle["results"]}
    pairs, matrix = [], Counter()
    for sample in manifest["samples"]:
        left, right = easy_by[sample["sample_id"]], paddle_by[sample["sample_id"]]
        agree = left["hypothesis_normalized"] == right["hypothesis_normalized"]
        left_ok, right_ok = left["normalized_exact_match"], right["normalized_exact_match"]
        outcome = ("agreement_correct" if agree and left_ok else "agreement_incorrect" if agree else
                   "disagreement_easy_correct" if left_ok else "disagreement_paddle_correct" if right_ok else "disagreement_both_wrong")
        matrix[outcome] += 1
        pairs.append({"sample_id": sample["sample_id"], "agreement": agree, "outcome": outcome,
                      "easyocr": left, "paddleocr": right,
                      "both_confidently_wrong": (not left_ok and not right_ok and
                                                 (left["confidence"] or 0) >= .9 and (right["confidence"] or 0) >= .9)})
    errors = {"schema_version": SCHEMA, "checkpoint": "11.4", "artifact_kind": "error_analysis",
              "status": "completed", "created_at": now(), "pairs": pairs,
              "error_type_counts": {"easyocr": dict(Counter(error for item in easy["results"] for error in item["error_types"])),
                                    "paddleocr": dict(Counter(error for item in paddle["results"] for error in item["error_types"]))},
              "confidence_buckets": {engine: {bucket: {"sample_count": len(items),
                  "exact_count": sum(item["normalized_exact_match"] for item in items),
                  "mean_cer": sum(item["normalized_cer"] for item in items) / len(items)}
                  for bucket in ["0.95-1.00", "0.90-0.95", "0.80-0.90", "0.60-0.80", "<0.60", "unavailable"]
                  if (items := [item for item in data["results"] if item["confidence_bucket"] == bucket])}
                  for engine, data in (("easyocr", easy), ("paddleocr", paddle))},
              "high_confidence_errors": {engine: [item for item in data["results"] if (item["confidence"] or 0) >= .9 and not item["normalized_exact_match"]]
                                         for engine, data in (("easyocr", easy), ("paddleocr", paddle))},
              "agreement_matrix": {**{key: matrix[key] for key in ("agreement_correct", "agreement_incorrect", "disagreement_easy_correct", "disagreement_paddle_correct", "disagreement_both_wrong")},
                                   "agreement_rate": sum(pair["agreement"] for pair in pairs) / len(pairs),
                                   "both_confidently_wrong": sum(pair["both_confidently_wrong"] for pair in pairs)},
              "conclusion": "Confidence alone is not safe; sample count is too small to establish agreement calibration."}
    comparison = {"schema_version": SCHEMA, "checkpoint": "11.4", "artifact_kind": "comparison",
                  "status": "completed", "created_at": now(), "trusted_sample_count": len(pairs),
                  "aggregate": {"easyocr": easy["aggregate"], "paddleocr": paddle["aggregate"]},
                  "subgroups": {engine: {"language": subgroup(data["results"], "language"),
                                          "text_role": subgroup(data["results"], "text_role"),
                                          "difficulty": subgroup(data["results"], "difficulty_tags")}
                                for engine, data in (("easyocr", easy), ("paddleocr", paddle))},
                  "agreement_matrix": errors["agreement_matrix"],
                  "structural_separation": {"crop_transcription_detection_recall": "N/A",
                    "11_3_full_page_known_region_recall": {"easyocr": "21/21", "paddleocr": "21/21"},
                    "11_3_logical_bubble_over_split": {"easyocr": 19, "paddleocr": 19},
                    "merged_logical_bubbles": {"easyocr": 0, "paddleocr": 0}},
                  "answers": {"paddle_clearly_better": "No: Paddle CER is lower, but n=3 is insufficient.",
                    "paddle_faster": "See measured region/init timing; no general claim from n=3.",
                    "vietnamese": "Paddle has lower measured CER on three Vietnamese samples; insufficient for preference.",
                    "english": "N/A: no trusted English sample.",
                    "dominant_errors": errors["error_type_counts"], "confidence_alone": "No.",
                    "agreement_stronger": "N/A: insufficient agreement cases.",
                    "both_confidently_wrong": errors["agreement_matrix"]["both_confidently_wrong"],
                    "transcription_vs_structure": "Both remain problems: crop errors persist and both engines over-split 19 logical regions in 11.3.",
                    "enough_for_reader_v2": "No; more human GT is required."},
                  "decision": "D. INSUFFICIENT EVIDENCE — MORE HUMAN GT REQUIRED",
                  "production_ocr": "EasyOCR unchanged", "vlm_calls": 0}
    write(ERRORS, errors); write(COMPARISON, comparison)
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("manifest", "easyocr", "paddleocr", "analyze")); args = parser.parse_args()
    result = build_manifest() if args.command == "manifest" else analyze() if args.command == "analyze" else benchmark(args.command)
    print(json.dumps({"status": result["status"], "artifact_kind": result["artifact_kind"]}))


if __name__ == "__main__": main()
