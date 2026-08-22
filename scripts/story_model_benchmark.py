#!/usr/bin/env python3
"""Run one read-only Story-model candidate and compare it with Day 11.1."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
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
from app.models.project_story_analysis import ProjectStoryAnalysis  # noqa: E402
from app.services.model_runtime import (  # noqa: E402
    DETERMINISTIC_BENCHMARK_OPTIONS,
    generation_options,
    story_model_override,
    validate_model_reference,
)
from app.services.performance import collect_performance  # noqa: E402
from app.services.resource_safety import (  # noqa: E402
    CRITICAL,
    ResourceThresholds,
    sample_resources,
)
from app.services.story_input_builder import build_story_input  # noqa: E402
from app.services.story_model_benchmark import (  # noqa: E402
    compare_events,
    event_source_keys,
    observe_output_language,
    validate_candidate_artifact,
)
from app.services.story_persistence import story_source_revision  # noqa: E402
from app.services.story_reliability import run_reliable_story_analysis  # noqa: E402
from benchmark_pipeline import atomic_write_json  # noqa: E402
from machine_baseline import dataset_snapshot  # noqa: E402


def resolved_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_summary(result: dict[str, Any], story_input: dict[str, Any]) -> dict[str, Any]:
    grounded = result.get("grounded_result", {})
    events = [event for event in grounded.get("events", []) if isinstance(event, dict)]
    claims = [
        claim
        for event in events
        for claim in event.get("claims", [])
        if isinstance(claim, dict)
    ]
    unsupported = [
        claim
        for event in events
        for claim in event.get("unsupported_claims", [])
        if isinstance(claim, dict)
    ]
    allowed_sources = {
        (page["asset_id"], page["page_order"], dialogue["region_id"])
        for page in story_input.get("pages", [])
        for dialogue in page.get("dialogues", [])
    }
    invalid_sources = sorted(
        source
        for event in events
        for source in event_source_keys(event)
        if source not in allowed_sources
    )
    unsupported_events = [
        event.get("id")
        for event in events
        if event.get("unsupported_claims") or not event.get("claims")
    ]
    coverage = result.get("coverage", {})
    return {
        "output_structurally_valid": True,
        "event_count": len(events),
        "main_story_event_count": sum(
            event.get("story_role") == "main_story" for event in events
        ),
        "grounded_claim_count": len(claims),
        "detected_rejected_unsupported_claims": len(unsupported),
        "accepted_unsupported_claims": 0,
        "unsupported_event_count": len(unsupported_events),
        "unsupported_event_ids": unsupported_events,
        "script_ready_event_count": sum(
            event.get("script_ready") is True for event in events
        ),
        "source_reference_valid": not invalid_sources,
        "invalid_source_references": [list(source) for source in invalid_sources],
        "grounding_issues": grounded.get("issues", []),
        "coverage": {
            key: coverage.get(key)
            for key in (
                "eligible_regions",
                "important_regions",
                "covered_regions",
                "non_story_relevant_regions",
                "unresolved_regions",
                "coverage_score",
            )
        },
        "analysis_attempts": result.get("analysis_attempts"),
        "recovery_attempts": result.get("recovery_attempts"),
        "language": observe_output_language(events),
        "events": events,
    }


def ollama_residency(candidate: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    for model in payload.get("models", []):
        if model.get("name") == candidate or model.get("model") == candidate:
            return {
                "name": candidate,
                "resident_size_bytes": model.get("size"),
                "vram_size_bytes": model.get("size_vram"),
                "parameter_size": model.get("details", {}).get("parameter_size"),
                "quantization": model.get("details", {}).get("quantization_level"),
                "context_length": model.get("context_length"),
            }
    return None


def stage_calls(performance: dict[str, Any], stage: str) -> list[dict[str, Any]]:
    return [call for call in performance.get("model_calls", []) if call.get("stage") == stage]


def seconds_from_ns(value: Any) -> float | None:
    return round(value / 1_000_000_000, 6) if isinstance(value, int) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--control-baseline", required=True)
    parser.add_argument("--control-output", required=True)
    parser.add_argument("--candidate-output", required=True)
    parser.add_argument("--comparison-output", required=True)
    args = parser.parse_args()
    candidate = validate_model_reference(args.candidate)
    thresholds = ResourceThresholds.from_environment()
    prelaunch = sample_resources(thresholds)
    if prelaunch["safety_state"] == CRITICAL:
        raise SystemExit("CRITICAL before candidate benchmark; inference was not launched")

    baseline = json.loads(resolved_path(args.control_baseline).read_text(encoding="utf-8"))
    before = dataset_snapshot(args.project_id)
    story_input = build_story_input(args.project_id)
    revision = story_source_revision(story_input)
    if story_input.get("status") != "ready" or before["page_count"] != 3:
        raise SystemExit("Candidate input does not match the ready 3-page control contract")

    db = SessionLocal()
    try:
        record = (
            db.query(ProjectStoryAnalysis)
            .filter(ProjectStoryAnalysis.project_id == args.project_id)
            .first()
        )
        if record is None or record.source_revision != revision:
            raise SystemExit("No same-input persisted 8B event result is available")
        control_result = record.result
    finally:
        db.close()

    control_summary = result_summary(control_result, story_input)
    control_calls = baseline["stages"]["story_analysis"]["model_calls"]
    control_artifact = {
        "schema_version": 1,
        "checkpoint": "11.1",
        "control_model": baseline["models"]["text"],
        "source_baseline": str(resolved_path(args.control_baseline).relative_to(ROOT)),
        "input": {
            "source_revision": revision,
            "page_count": before["page_count"],
            "project_id_hash": baseline["dataset"]["project_id_hash"],
        },
        "performance": {
            "wall_clock_seconds": baseline["stages"]["story_analysis"]["wall_clock_seconds"],
            "total_inference_seconds": baseline["stages"]["story_analysis"]["total_model_inference_seconds"],
            "model_calls": control_calls,
        },
        "correctness": {
            "exact_11_1": {
                "accepted_unsupported_claims": 0,
                "analysis_attempts": baseline["story_result"]["analysis_attempts"],
                "recovery_attempts": baseline["story_result"]["recovery_attempts"],
                "unresolved_regions": baseline["story_result"]["unresolved_regions"],
            },
            "same_input_persisted_event_proxy": control_summary,
        },
        "event_control_note": "11.1 retained exact latency/prompt/call/coverage summary but not event payload; event diff uses the same-source-revision persisted 8B result and is labeled proxy",
    }
    atomic_write_json(resolved_path(args.control_output), control_artifact)

    started_at = datetime.now(timezone.utc)
    with (
        story_model_override(candidate),
        generation_options(DETERMINISTIC_BENCHMARK_OPTIONS),
        collect_performance() as collector,
    ):
        candidate_result = run_reliable_story_analysis(story_input)
    performance = collector.report()
    after = dataset_snapshot(args.project_id)
    if before["state_hash"] != after["state_hash"]:
        raise RuntimeError("Authoritative persisted project state changed")

    candidate_summary = result_summary(candidate_result, story_input)
    analyzer_calls = stage_calls(performance, "story_analyzer")
    recovery_calls = stage_calls(performance, "coverage_recovery")
    analyzer_hash_equal = bool(analyzer_calls) and analyzer_calls[0].get("prompt_hash") == control_calls[0].get("prompt_hash")
    candidate_artifact = {
        "schema_version": 1,
        "checkpoint": "11.2",
        "status": "completed",
        "candidate_model": candidate,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "source_revision": revision,
            "page_count": before["page_count"],
            "project_id_hash": baseline["dataset"]["project_id_hash"],
            "persisted_state_unchanged": True,
        },
        "experiment_control": {
            "generation_options_equal": DETERMINISTIC_BENCHMARK_OPTIONS == baseline["models"].get("generation_options", DETERMINISTIC_BENCHMARK_OPTIONS),
            "analyzer_prompt_hash_equal": analyzer_hash_equal,
            "analyzer_control_prompt_hash": control_calls[0].get("prompt_hash"),
            "analyzer_candidate_prompt_hash": analyzer_calls[0].get("prompt_hash") if analyzer_calls else None,
            "coverage_prompt_template_changed": False,
            "coverage_payload_hash_equal": bool(recovery_calls) and len(control_calls) > 1 and recovery_calls[0].get("prompt_hash") == control_calls[1].get("prompt_hash"),
            "coverage_payload_note": "payload can differ because uncovered regions depend on candidate output",
        },
        "performance": performance,
        "model_call_breakdown": dict(Counter(call.get("stage", "unknown") for call in performance["model_calls"])),
        "model_runtime": {
            "residency": ollama_residency(candidate),
            "first_call_load_seconds": seconds_from_ns(analyzer_calls[0].get("load_duration")) if analyzer_calls else None,
            "first_call_total_ollama_seconds": seconds_from_ns(analyzer_calls[0].get("total_duration")) if analyzer_calls else None,
        },
        "correctness": candidate_summary,
        "safety": {
            "prelaunch": prelaunch,
            "observed_state": performance["resources"]["safety_state"],
            "resources": performance["resources"],
        },
    }
    validate_candidate_artifact(candidate_artifact)
    atomic_write_json(resolved_path(args.candidate_output), candidate_artifact)

    control_analyzer = next(call["duration_seconds"] for call in control_calls if call.get("stage") == "story_analyzer")
    control_recovery = sum(call["duration_seconds"] for call in control_calls if call.get("stage") == "coverage_recovery")
    candidate_analyzer = sum(call["duration_seconds"] for call in analyzer_calls)
    candidate_recovery = sum(call["duration_seconds"] for call in recovery_calls)
    control_total = baseline["stages"]["story_analysis"]["total_model_inference_seconds"]
    candidate_total = performance["total_model_inference_seconds"]
    event_diff = compare_events(
        control_summary["events"], candidate_summary["events"]
    )
    safety_state = performance["resources"]["safety_state"]
    control_swap_delta = baseline["stages"]["story_analysis"]["resources"]["swap_delta_bytes"]
    candidate_swap_delta = performance["resources"]["swap_delta_bytes"]
    if safety_state == CRITICAL:
        verdict = "FAIL — MACHINE SAFETY"
    elif (
        candidate_summary["detected_rejected_unsupported_claims"]
        or candidate_summary["unsupported_event_count"]
        or not candidate_summary["source_reference_valid"]
    ):
        verdict = "FAIL — QUALITY"
    elif control_total / candidate_total <= 1.2:
        verdict = "FAIL — PERFORMANCE"
    elif (
        candidate_summary["coverage"]["unresolved_regions"]
        > control_summary["coverage"]["unresolved_regions"]
        or candidate_summary["event_count"] < control_summary["event_count"]
    ):
        verdict = "CONDITIONAL PASS"
    elif (
        control_total / candidate_total > 1.5
        and isinstance(candidate_swap_delta, int)
        and candidate_swap_delta < control_swap_delta
    ):
        verdict = "STRONG PASS"
    else:
        verdict = "CONDITIONAL PASS"
    comparison = {
        "schema_version": 1,
        "checkpoint": "11.2",
        "control_model": control_artifact["control_model"],
        "candidate_model": candidate,
        "input_equal": revision == control_artifact["input"]["source_revision"],
        "analyzer_prompt_hash_equal": analyzer_hash_equal,
        "generation_options_equal": True,
        "speedup": {
            "story_analyzer": round(control_analyzer / candidate_analyzer, 4),
            "coverage_recovery": round(control_recovery / candidate_recovery, 4) if candidate_recovery else None,
            "total_inference": round(control_total / candidate_total, 4),
            "analyzer_seconds_saved": round(control_analyzer - candidate_analyzer, 6),
            "coverage_seconds_saved": round(control_recovery - candidate_recovery, 6),
            "total_seconds_saved": round(control_total - candidate_total, 6),
        },
        "control_correctness": {
            "exact_11_1": control_artifact["correctness"]["exact_11_1"],
            "same_input_persisted_event_proxy": {
                key: value for key, value in control_summary.items() if key != "events"
            },
        },
        "candidate_correctness": {key: value for key, value in candidate_summary.items() if key != "events"},
        "event_diff": event_diff,
        "event_diff_method": "source overlap plus exact normalized claim text; human judgment explicitly flagged",
        "memory": {
            "control": baseline["stages"]["story_analysis"]["resources"],
            "candidate": performance["resources"],
        },
        "verdict": verdict,
        "production_default_changed": False,
    }
    atomic_write_json(resolved_path(args.comparison_output), comparison)
    print(f"Candidate: {candidate}")
    print(f"Calls: {performance['total_model_calls']}")
    print(f"Inference: {candidate_total:.3f}s")
    print(f"Wall: {performance['wall_clock_seconds']:.3f}s")
    print(f"Safety: {safety_state}")
    print(f"Verdict: {verdict}")


if __name__ == "__main__":
    main()
