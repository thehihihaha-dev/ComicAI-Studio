#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / "backend" / ".env")
os.chdir(ROOT / "backend")

from app.database import SessionLocal  # noqa: E402
from app.models.asset import Asset  # noqa: E402
from app.models.dialogue_ground_truth import DialogueGroundTruth  # noqa: E402
from app.services.model_runtime import (  # noqa: E402
    DETERMINISTIC_BENCHMARK_OPTIONS,
    generation_options,
)
from app.services.performance import collect_performance, measure_stage  # noqa: E402
from app.services.vision_analyzer import analyze_comic_page, valid_reading_order  # noqa: E402


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def classify_failure(error: str | None, validation: dict, final_valid_order: bool) -> str | None:
    if error and "reading order" in error.lower():
        return "READING_ORDER_FAILURE"
    if error:
        return "OTHER"
    if validation.get("invalid_block_ids") or validation.get("duplicate_block_ids"):
        return "REGION_ID_FAILURE"
    if validation.get("important_missing_block_ids"):
        return "OCR_COVERAGE_FAILURE"
    if not validation.get("is_valid"):
        return "RECOVERY_FAILURE"
    if not final_valid_order:
        return "READING_ORDER_FAILURE"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Repeat deterministic Vision analysis without mutating project state.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--snapshot", default=str(ROOT / "benchmarks" / "vision_correctness.v1.json"))
    parser.add_argument("--output")
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text())

    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.project_id == args.project_id)
            .order_by(Asset.page_order, Asset.id)
            .limit(args.limit)
            .all()
        )
        ground_truth_before = db.query(DialogueGroundTruth).count()
        inputs = []
        for asset in assets:
            image_path = Path(asset.file_path)
            ocr_blocks = json.loads(asset.ocr_blocks or "[]")
            inputs.append({
                "asset_id": asset.id,
                "filename": asset.filename,
                "image_path": str(image_path),
                "image_hash": sha256_bytes(image_path.read_bytes()),
                "ocr_hash": sha256_bytes(json.dumps(ocr_blocks, ensure_ascii=False, separators=(",", ":")).encode()),
                "ocr_blocks": ocr_blocks,
            })
    finally:
        db.close()
    if len(inputs) != args.limit:
        raise SystemExit(f"Expected {args.limit} assets, found {len(inputs)}.")

    runs = []
    with generation_options(DETERMINISTIC_BENCHMARK_OPTIONS):
        for repetition in range(1, args.repetitions + 1):
            for item in inputs:
                error = None
                result = None
                with collect_performance() as collector:
                    try:
                        with measure_stage("vision_benchmark", asset_id=item["asset_id"], filename=item["filename"]):
                            result = analyze_comic_page(item["image_path"], item["ocr_blocks"])
                    except Exception as exc:
                        error = str(exc)
                validation = result.get("validation", {}) if result else {}
                vision_result = result.get("vision_result", {}) if result else {}
                regions = vision_result.get("regions", [])
                reading_order = vision_result.get("reading_order", [])
                valid_order = valid_reading_order(reading_order, regions) if regions else validation.get("page_type") == "no_dialogue"
                status = "no_dialogue" if validation.get("page_type") == "no_dialogue" else "completed" if validation.get("is_valid") and valid_order else "failed"
                expected = snapshot["pages"].get(item["filename"], {})
                snapshot_pass = (
                    status == expected.get("final_status")
                    and len(validation.get("important_missing_block_ids", [])) <= expected.get("important_missing_blocks", 0)
                    and (valid_order is True) == expected.get("reading_order_complete", True)
                )
                layout_calls = [call for call in collector.model_calls if call.get("stage") == "vision_layout"]
                runs.append({
                    "filename": item["filename"],
                    "repetition": repetition,
                    "duration_seconds": collector.wall_clock_seconds,
                    "image_hash": item["image_hash"],
                    "ocr_hash": item["ocr_hash"],
                    "prompt_hash": layout_calls[0].get("prompt_hash") if layout_calls else None,
                    "raw_response_hash": layout_calls[0].get("raw_response_hash") if layout_calls else None,
                    "region_count": len(regions),
                    "region_ids": [region.get("id") for region in regions],
                    "reading_order": reading_order,
                    "layout_supplied_valid_order": bool(layout_calls) and not any(call.get("stage") == "reading_order" for call in collector.model_calls),
                    "reading_order_fallback_calls": sum(call.get("stage") == "reading_order" for call in collector.model_calls),
                    "vision_recovery_calls": sum(call.get("stage") == "vision_recovery" for call in collector.model_calls),
                    "important_missing_block_count": len(validation.get("important_missing_block_ids", [])),
                    "validation": validation,
                    "final_status": status,
                    "snapshot_pass": snapshot_pass,
                    "failure_classification": classify_failure(error, validation, valid_order),
                    "error": error,
                })

    db = SessionLocal()
    try:
        ground_truth_after = db.query(DialogueGroundTruth).count()
    finally:
        db.close()
    pipeline_files = [
        ROOT / "backend/app/services/vision_analyzer.py",
        ROOT / "backend/app/services/ollama_vision.py",
        ROOT / "backend/app/services/model_runtime.py",
    ]
    fingerprint = {
        "model": "qwen3-vl:8b-instruct",
        "generation_options": DETERMINISTIC_BENCHMARK_OPTIONS,
        "pipeline_hash": sha256_bytes(b"".join(path.read_bytes() for path in pipeline_files)),
        "snapshot_hash": sha256_bytes(Path(args.snapshot).read_bytes()),
        "assets": [{key: item[key] for key in ("asset_id", "filename", "image_hash", "ocr_hash")} for item in inputs],
    }
    report = {
        "benchmark": "vision_stability.v1",
        "project_id": args.project_id,
        "fingerprint": fingerprint,
        "ground_truth_before": ground_truth_before,
        "ground_truth_after": ground_truth_after,
        "runs": runs,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered)
    print(rendered)


if __name__ == "__main__":
    main()
