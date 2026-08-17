#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.models.asset import Asset  # noqa: E402
from app.models.project import Project  # noqa: E402,F401
from app.services.dialogue_structure_recovery import recover_ocr_empty_candidate  # noqa: E402
from app.services.empty_dialogue_detector import (  # noqa: E402
    bbox_iou,
    detect_empty_dialogue_candidates,
    run_local_candidate_ocr,
    run_visual_candidate_ocr,
)
from app.services.model_runtime import (  # noqa: E402
    DETERMINISTIC_BENCHMARK_OPTIONS,
    generation_options,
)
from app.services.ocr_service import get_ocr  # noqa: E402
from app.services.ollama_vision import call_vision_model  # noqa: E402


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f"{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    database = SessionLocal()
    try:
        assets = (
            database.query(Asset)
            .filter(Asset.project_id == args.project_id)
            .order_by(Asset.page_order, Asset.id)
            .all()
        )
        inputs = [
            {
                "filename": asset.filename,
                "image_path": str(
                    Path(asset.file_path)
                    if Path(asset.file_path).is_absolute()
                    else BACKEND_ROOT / asset.file_path
                ),
                "ocr_blocks": json.loads(asset.ocr_blocks or "[]"),
            }
            for asset in assets
        ]
    finally:
        database.close()

    # Production inference finishes before the human oracle is loaded.
    pages = []
    vision_fallback_count = 0
    with generation_options(DETERMINISTIC_BENCHMARK_OPTIONS):
        for item in inputs:
            detection = detect_empty_dialogue_candidates(
                item["image_path"], item["ocr_blocks"]
            )
            reader = get_ocr() if detection["candidates"] else None
            recoveries = []
            for candidate in detection["candidates"]:
                timings = {"local_ocr_seconds": 0.0, "vision_ocr_seconds": 0.0}

                def local(path: str, bbox: list[int]):
                    started = time.perf_counter()
                    try:
                        return run_local_candidate_ocr(path, bbox, reader)
                    finally:
                        timings["local_ocr_seconds"] += time.perf_counter() - started

                def vision(path: str, bbox: list[int]):
                    nonlocal vision_fallback_count
                    if vision_fallback_count >= 1:
                        return None
                    vision_fallback_count += 1
                    started = time.perf_counter()
                    try:
                        return run_visual_candidate_ocr(path, bbox, call_vision_model)
                    finally:
                        timings["vision_ocr_seconds"] += time.perf_counter() - started

                recovered = recover_ocr_empty_candidate(
                    item["image_path"], candidate["bbox"], local, vision
                )
                recoveries.append(
                    {
                        "candidate_id": candidate["candidate_id"],
                        **recovered,
                        **{key: round(value, 6) for key, value in timings.items()},
                    }
                )
            pages.append(
                {
                    "filename": item["filename"],
                    **detection,
                    "recoveries": recoveries,
                }
            )

    audit = json.loads(Path(args.audit).read_text())
    audit_pages = {page["filename"]: page for page in audit["pages"]}
    for page in pages:
        expected = [
            region
            for region in audit_pages[page["filename"]]["expected_regions"]
            if region.get("classification") == "OCR_MISSING"
        ]
        scored = []
        for candidate in page["candidates"]:
            score = max(
                (bbox_iou(candidate["bbox"], region["approx_box"]) for region in expected),
                default=0.0,
            )
            scored.append({**candidate, "audit_iou": round(score, 6)})
        page["candidates"] = scored
        page["matched_candidates"] = sum(item["audit_iou"] > 0.05 for item in scored)
        page["false_positive_candidates"] = len(scored) - page["matched_candidates"]

    report = {
        "project_id": args.project_id,
        "audit_used_for_scoring_only": True,
        "pages": pages,
        "summary": {
            "candidate_count": sum(len(page["candidates"]) for page in pages),
            "matched_candidates": sum(page["matched_candidates"] for page in pages),
            "false_positive_candidates": sum(
                page["false_positive_candidates"] for page in pages
            ),
            "vision_fallback_calls": vision_fallback_count,
        },
    }
    output = Path(args.output)
    atomic_json(output, report)
    print(f"Detector benchmark complete\nArtifact: {output}")


if __name__ == "__main__":
    main()
