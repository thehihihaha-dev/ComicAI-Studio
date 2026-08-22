#!/usr/bin/env python3
"""Create the read-only Day 11 machine/resource baseline artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from app.services.ollama_text import DEFAULT_TEXT_MODEL  # noqa: E402
from app.services.ollama_vision import DEFAULT_VISION_MODEL  # noqa: E402
from app.services.performance import collect_performance  # noqa: E402
from app.services.resource_safety import ResourceThresholds, sample_resources  # noqa: E402
from app.services.story_input_builder import build_story_input  # noqa: E402
from app.services.story_reliability import run_reliable_story_analysis  # noqa: E402
from benchmark_pipeline import atomic_write_json  # noqa: E402


def _command(command: list[str]) -> str | None:
    try:
        return subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=2
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _sysctl(name: str) -> str | None:
    return _command(["sysctl", "-n", name])


def dataset_snapshot(project_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.project_id == project_id)
            .order_by(Asset.page_order, Asset.id)
            .all()
        )
        ids = [asset.id for asset in assets]
        truth = (
            db.query(DialogueGroundTruth)
            .filter(DialogueGroundTruth.asset_id.in_(ids))
            .order_by(DialogueGroundTruth.asset_id, DialogueGroundTruth.region_id)
            .all()
            if ids
            else []
        )
        state = {
            "assets": [
                {
                    "id": asset.id,
                    "page_order": asset.page_order,
                    "status": asset.status,
                    "vision_status": asset.vision_status,
                    "dialogue_status": asset.dialogue_status,
                    "ocr_blocks": asset.ocr_blocks,
                    "vision_regions": asset.vision_regions,
                    "reading_order": asset.reading_order,
                    "dialogues": asset.dialogues,
                }
                for asset in assets
            ],
            "ground_truth": [
                {
                    "asset_id": row.asset_id,
                    "region_id": row.region_id,
                    "verified_text": row.verified_text,
                }
                for row in truth
            ],
        }
        encoded = json.dumps(state, ensure_ascii=False, sort_keys=True).encode()
        return {
            "page_count": len(assets),
            "ground_truth_count": len(truth),
            "state_hash": hashlib.sha256(encoded).hexdigest(),
            "page_statuses": [
                {
                    "page_order": asset.page_order,
                    "status": asset.status,
                    "vision_status": asset.vision_status,
                    "dialogue_status": asset.dialogue_status,
                }
                for asset in assets
            ],
        }
    finally:
        db.close()


def machine_info() -> dict[str, Any]:
    memory = _sysctl("hw.memsize")
    return {
        "platform": platform.system(),
        "architecture": platform.machine(),
        "cpu_model": _sysctl("machdep.cpu.brand_string"),
        "logical_cpu_count": int(value) if (value := _sysctl("hw.logicalcpu")) else None,
        "physical_cpu_count": int(value) if (value := _sysctl("hw.physicalcpu")) else None,
        "total_memory_bytes": int(memory) if memory else None,
        "hostname": None,
        "temperature_celsius": None,
        "temperature_note": "not measured: no reliable supported macOS standard-library API",
    }


def threshold_payload(thresholds: ResourceThresholds) -> dict[str, int]:
    return {
        "warning_available_bytes": thresholds.warning_available_bytes,
        "critical_available_bytes": thresholds.critical_available_bytes,
        "warning_swap_used_bytes": thresholds.warning_swap_used_bytes,
        "critical_swap_used_bytes": thresholds.critical_swap_used_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    thresholds = ResourceThresholds.from_environment()
    started = datetime.now(timezone.utc)
    idle_started = time.perf_counter()
    idle_before = sample_resources(thresholds)
    time.sleep(0.2)
    idle_after = sample_resources(thresholds)
    idle_seconds = time.perf_counter() - idle_started
    before = dataset_snapshot(args.project_id)
    if before["page_count"] == 0:
        raise SystemExit("The selected existing benchmark project has no pages.")

    story_input_started = time.perf_counter()
    story_input = build_story_input(args.project_id)
    story_input_seconds = time.perf_counter() - story_input_started
    if story_input.get("status") != "ready":
        raise SystemExit(f"Story Input is not ready: {story_input.get('issues', [])}")

    with generation_options(DETERMINISTIC_BENCHMARK_OPTIONS), collect_performance() as collector:
        result = run_reliable_story_analysis(story_input)
    performance = collector.report()
    after = dataset_snapshot(args.project_id)
    unchanged = before["state_hash"] == after["state_hash"]
    if not unchanged:
        raise RuntimeError("Persisted benchmark state changed during read-only baseline")

    call_breakdown = Counter(
        call.get("stage", "unknown") for call in performance["model_calls"]
    )
    artifact = {
        "schema_version": 1,
        "checkpoint": "11.1",
        "status": "completed",
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "machine": machine_info(),
        "models": {
            "ocr": "EasyOCR vi+en, CPU, lazy singleton in backend process",
            "vision": DEFAULT_VISION_MODEL,
            "text": DEFAULT_TEXT_MODEL,
            "ollama_endpoint": "127.0.0.1:11434",
            "heavy_model_concurrency": 1,
        },
        "thresholds": threshold_payload(thresholds),
        "dataset": {
            "name": "existing persisted benchmark project",
            "project_id_hash": hashlib.sha256(args.project_id.encode()).hexdigest(),
            "pages": before["page_count"],
            "ground_truth_records": before["ground_truth_count"],
            "page_statuses": before["page_statuses"],
            "persisted_state_unchanged": unchanged,
        },
        "idle": {
            "duration_seconds": round(idle_seconds, 6),
            "before": idle_before,
            "after": idle_after,
        },
        "stages": {
            "story_input_builder": {
                "duration_seconds": round(story_input_seconds, 6),
                "model_calls": 0,
            },
            "story_analysis": performance,
            "ocr_layout": {
                "status": "not_run_data_integrity_guard",
                "duration_seconds": None,
                "reason": "existing runner overwrites persisted asset results",
            },
            "vision_dialogue": {
                "status": "not_run_data_integrity_guard",
                "duration_seconds": None,
                "reason": "existing runner overwrites persisted asset results",
            },
        },
        "model_call_breakdown": dict(call_breakdown),
        "story_result": {
            "analysis_attempts": result.get("analysis_attempts"),
            "recovery_attempts": result.get("recovery_attempts"),
            "unresolved_regions": result.get("coverage", {}).get("unresolved_regions"),
        },
        "limitations": [
            "Process-local RSS excludes Ollama's separate process RSS.",
            "Unified GPU memory and temperature are not measured.",
            "Available memory is a reclaimable vm_stat approximation.",
            "No page stages were reprocessed because preserving persisted approved data takes priority.",
            "The guard coordinates one backend process; multiple backend workers need a future shared coordinator.",
        ],
    }
    atomic_write_json(output_path, artifact)
    print(f"Baseline complete: {output_path.resolve()}")
    print(f"Pages represented: {before['page_count']}")
    print(f"Model calls: {performance['total_model_calls']}")
    print(f"Model inference: {performance['total_model_inference_seconds']:.3f}s")
    print(f"Story wall clock: {performance['wall_clock_seconds']:.3f}s")
    print(f"Safety state: {performance['resources']['safety_state']}")


if __name__ == "__main__":
    main()
