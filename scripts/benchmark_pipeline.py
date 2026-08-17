#!/usr/bin/env python3
"""Run the real local pipeline for an existing project and print timing JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
load_dotenv(REPOSITORY_ROOT / "backend" / ".env")
os.chdir(REPOSITORY_ROOT / "backend")

from app.database import SessionLocal  # noqa: E402
from app.models.asset import Asset  # noqa: E402
from app.models.dialogue_ground_truth import DialogueGroundTruth  # noqa: E402
from app.routers.assets import process_single_asset, run_dialogue_analysis, run_layout_analysis  # noqa: E402
from app.services.performance import collect_performance, measure_stage  # noqa: E402
from app.services.model_runtime import DETERMINISTIC_BENCHMARK_OPTIONS, generation_options  # noqa: E402
from app.services.story_input_builder import build_story_input  # noqa: E402
from app.services.story_reliability import run_reliable_story_analysis  # noqa: E402


def _require_service(name: str, port: int) -> None:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return
    except OSError as error:
        raise SystemExit(
            f"{name} is unavailable on 127.0.0.1:{port}. Start it before benchmarking."
        ) from error


def _benchmark_lock(project_id: str, requested: str | None) -> tuple[Path, dict[str, Any]]:
    candidates = [Path(requested)] if requested else sorted((REPOSITORY_ROOT / "benchmarks").glob("benchmark_lock.v*.json"))
    for path in candidates:
        payload = json.loads(path.read_text())
        if payload.get("project_id") == project_id:
            return path, payload
    raise SystemExit(f"No benchmark lock matches project {project_id!r}.")


def atomic_write_json(path: str | Path, payload: dict[str, Any]) -> None:
    """Persist a complete JSON document without exposing a partial final file."""
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def format_terminal_summary(report: dict[str, Any], output_path: str | Path | None) -> str:
    story_usable = report.get("results", {}).get("story_result_usable") is True
    lines = [
        "Benchmark complete",
        f"Status: {report.get('status', 'unknown')}",
        f"Pages: {report.get('results', {}).get('page_count', 0)}",
        f"Wall clock: {report.get('wall_clock_seconds', 0.0):.2f}s",
        f"Model calls: {len(report.get('model_calls', []))}",
        f"Story usable: {'YES' if story_usable else 'NO'}",
    ]
    if output_path is not None:
        lines.append(f"Artifact: {Path(output_path).expanduser().resolve()}")
    return "\n".join(lines)


def _asset_statuses(project_id: str, selected_ids: list[str]) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Asset)
            .filter(Asset.project_id == project_id, Asset.id.in_(selected_ids))
            .order_by(Asset.page_order, Asset.id)
            .all()
        )
        return [
            {
                "asset_id": asset.id,
                "filename": asset.filename,
                "asset_status": asset.status,
                "vision_status": asset.vision_status,
                "dialogue_status": asset.dialogue_status,
            }
            for asset in rows
        ]
    finally:
        db.close()


def run_benchmark(
    project_id: str,
    selected: list[tuple[str, str]],
    *,
    deterministic: bool,
) -> dict[str, Any]:
    benchmark_error: str | None = None
    failure_stage: str | None = None
    story_input: dict[str, Any] | None = None
    story_result: dict[str, Any] | None = None
    option_context = generation_options(DETERMINISTIC_BENCHMARK_OPTIONS) if deterministic else generation_options({"num_ctx": 8192})
    with option_context, collect_performance() as collector:
        try:
            for asset_id, filename in selected:
                failure_stage = "page_pipeline"
                with measure_stage("page_total", asset_id=asset_id, filename=filename):
                    process_single_asset(asset_id)
                    run_layout_analysis(asset_id)
                    db = SessionLocal()
                    try:
                        vision_status = db.query(Asset.vision_status).filter(Asset.id == asset_id).scalar()
                    finally:
                        db.close()
                    if vision_status == "completed":
                        run_dialogue_analysis(asset_id)
            failure_stage = "story_input"
            story_input = build_story_input(project_id)
            if story_input.get("status") != "ready":
                raise RuntimeError("Story Input is not ready.")
            failure_stage = "story_reliability"
            story_result = run_reliable_story_analysis(story_input)
            failure_stage = None
        except Exception as error:
            benchmark_error = str(error)
    report = collector.report()
    failed_stages = [item["stage"] for item in report["stages"] if not item["success"]]
    if failed_stages:
        failure_stage = failed_stages[0]
    coverage = (story_result or {}).get("coverage", {})
    story_usable = bool(
        story_result
        and isinstance((story_result or {}).get("grounded_result"), dict)
        and coverage.get("unresolved_regions") == 0
    )
    report.update(
        {
            "status": "failed" if benchmark_error else "completed",
            "failure_stage": failure_stage,
            "issues": (story_input or {}).get("issues", []),
            "error": benchmark_error,
            "results": {
                "page_count": len(selected),
                "asset_statuses": _asset_statuses(project_id, [item[0] for item in selected]),
                "story_input_status": (story_input or {}).get("status", "not_reached"),
                "story_result_usable": story_usable,
            },
            "story_input_summary": (story_input or {}).get("summary"),
            "story_result_summary": {
                "analysis_attempts": (story_result or {}).get("analysis_attempts"),
                "recovery_attempts": (story_result or {}).get("recovery_attempts"),
                "coverage": coverage or None,
            },
        }
    )
    call_breakdown: dict[str, int] = {}
    for call in report["model_calls"]:
        stage = call.get("stage", "unknown")
        call_breakdown[stage] = call_breakdown.get(stage, 0) + 1
    report["summary"] = {
        "total_model_calls": report["total_model_calls"],
        "total_inference_seconds": report["total_model_inference_seconds"],
        "average_page_seconds": report["average_page_seconds"],
        "median_page_seconds": report["median_page_seconds"],
        "p95_page_seconds": report["p95_page_seconds"],
        "slowest_page": report["slowest_page"],
        "slowest_stage": report["slowest_stage"],
        "retry_count": report["retry_count"],
        "call_breakdown": call_breakdown,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--lock")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    _require_service("PostgreSQL", 5432)
    _require_service("Ollama", 11434)
    db = SessionLocal()
    try:
        query = db.query(Asset).filter(Asset.project_id == args.project_id).order_by(Asset.page_order, Asset.id)
        assets = query.limit(args.limit).all() if args.limit else query.all()
        selected = [(asset.id, asset.filename) for asset in assets]
        if args.deterministic:
            lock_path, locked = _benchmark_lock(args.project_id, args.lock)
            snapshot_path = REPOSITORY_ROOT / locked.get(
                "correctness_snapshot", "benchmarks/vision_correctness.v1.json"
            )
            pipeline_files = [
                REPOSITORY_ROOT / "backend/app/services/vision_analyzer.py",
                REPOSITORY_ROOT / "backend/app/services/ollama_vision.py",
                REPOSITORY_ROOT / "backend/app/services/model_runtime.py",
            ]
            fingerprint = {
                "project_id": args.project_id,
                "model": "qwen3-vl:8b-instruct",
                "generation_options": DETERMINISTIC_BENCHMARK_OPTIONS,
                "pipeline_hash": hashlib.sha256(b"".join(path.read_bytes() for path in pipeline_files)).hexdigest(),
                "snapshot_hash": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
                "ground_truth_count": (
                    db.query(DialogueGroundTruth)
                    .filter(DialogueGroundTruth.asset_id.in_([asset.id for asset in assets]))
                    .count()
                ),
                "assets": [
                    {
                        "asset_id": asset.id,
                        "filename": asset.filename,
                        "page_order": asset.page_order,
                        "image_hash": hashlib.sha256(Path(asset.file_path).read_bytes()).hexdigest(),
                        "ocr_hash": hashlib.sha256(json.dumps(json.loads(asset.ocr_blocks or "[]"), ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
                    }
                    for asset in assets
                ],
            }
            comparable_lock = {key: locked[key] for key in fingerprint}
            if fingerprint != comparable_lock:
                raise SystemExit("Benchmark fingerprint mismatch; inference was not started.\n" + json.dumps({"expected": comparable_lock, "actual": fingerprint}, ensure_ascii=False, indent=2))
    finally:
        db.close()
    if not selected:
        raise SystemExit(f"Project {args.project_id!r} has no assets to benchmark.")

    started_at = datetime.now(timezone.utc)
    report = run_benchmark(args.project_id, selected, deterministic=args.deterministic)
    completed_at = datetime.now(timezone.utc)
    report["benchmark_metadata"] = {
        "project_id": args.project_id,
        "model": "qwen3-vl:8b-instruct",
        "deterministic": args.deterministic,
        "generation_options": DETERMINISTIC_BENCHMARK_OPTIONS if args.deterministic else {"num_ctx": 8192},
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        **({"fingerprint": fingerprint} if args.deterministic else {}),
    }
    if args.output:
        atomic_write_json(args.output, report)
    print(format_terminal_summary(report, args.output), flush=True)
    if report["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
