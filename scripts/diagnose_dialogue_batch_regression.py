#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.asset import Asset  # noqa: E402
from app.models.project import Project  # noqa: E402,F401
from app.services.dialogue_builder import build_dialogues  # noqa: E402
from app.services.dialogue_corrector import (  # noqa: E402
    apply_dialogue_decisions,
    calculate_correction_score,
    correct_dialogues,
    recover_uncertain_dialogues,
)
from app.services.dialogue_structure_recovery import (  # noqa: E402
    enforce_recovered_region_review,
)
from app.services.model_runtime import (  # noqa: E402
    DETERMINISTIC_BENCHMARK_OPTIONS,
    generation_options,
)
from app.services.performance import collect_performance  # noqa: E402


def atomic_json(path: Path, value: dict[str, Any]) -> None:
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


def snapshot(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "order",
        "region_id",
        "raw_text",
        "clean_text",
        "ocr_confidence",
        "confidence",
        "needs_review",
        "reason_code",
        "correction_score",
        "risky_text_change",
        "decision",
        "recovered_text",
        "recovery_confidence",
        "recovery_reason_code",
    )
    return [{field: item.get(field) for field in fields} for item in items]


def run_pipeline(
    image_path: str,
    raw_dialogues: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
    regions: list[dict[str, Any]],
) -> dict[str, Any]:
    with collect_performance() as collector:
        corrected = correct_dialogues(image_path, raw_dialogues, ocr_blocks, {})
        scored = calculate_correction_score(raw_dialogues, corrected, ocr_blocks)
        decided = apply_dialogue_decisions(scored)
        recovered = recover_uncertain_dialogues(image_path, decided, ocr_blocks)
        final = enforce_recovered_region_review(recovered, regions)
    performance = collector.report()
    return {
        "raw": snapshot(raw_dialogues),
        "corrected": snapshot(corrected),
        "scored": snapshot(scored),
        "decided": snapshot(decided),
        "recovered": snapshot(recovered),
        "final": snapshot(final),
        "performance": performance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    database = SessionLocal()
    try:
        asset = database.get(Asset, args.asset_id)
        if asset is None:
            raise SystemExit("Asset not found.")
        image_path = Path(asset.file_path)
        if not image_path.is_absolute():
            image_path = BACKEND_ROOT / image_path
        ocr_blocks = json.loads(asset.ocr_blocks or "[]")
        regions8 = json.loads(asset.vision_regions or "[]")
        order8 = json.loads(asset.reading_order or "[]")
    finally:
        database.close()

    regions7 = [region for region in regions8 if region["id"] != 8]
    order7 = [region_id for region_id in order8 if region_id != 8]
    raw7 = build_dialogues(ocr_blocks, regions7, order7)
    raw8 = build_dialogues(ocr_blocks, regions8, order8)
    raw_recovered = [item for item in raw8 if item["region_id"] == 8]

    with generation_options(DETERMINISTIC_BENCHMARK_OPTIONS):
        experiment_a = run_pipeline(str(image_path), raw7, ocr_blocks, regions7)
        experiment_b = run_pipeline(str(image_path), raw8, ocr_blocks, regions8)
        recovered_only = run_pipeline(
            str(image_path),
            raw_recovered,
            ocr_blocks,
            [region for region in regions8 if region["id"] == 8],
        )

    a_by_id = {item["region_id"]: item for item in experiment_a["final"]}
    isolated_by_id = {item["region_id"]: item for item in recovered_only["final"]}
    merged = []
    for raw in raw8:
        source = isolated_by_id if raw["region_id"] == 8 else a_by_id
        merged.append({**source[raw["region_id"]], "order": raw["order"]})
    experiment_c = {
        "normal_batch": experiment_a,
        "recovered_only": recovered_only,
        "merged_final": merged,
    }

    report = {
        "asset_id": args.asset_id,
        "deterministic_options": DETERMINISTIC_BENCHMARK_OPTIONS,
        "experiment_a_7_regions": experiment_a,
        "experiment_b_8_regions": experiment_b,
        "experiment_c_isolated_recovered": experiment_c,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(output, report)
    print(f"Dialogue regression diagnostic complete\nArtifact: {output}")


if __name__ == "__main__":
    main()
