#!/usr/bin/env python3
"""Revalidate the persisted benchmark Story pipeline without reprocessing pages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
from app.services.performance import collect_performance  # noqa: E402
from app.services.short_script_engine import generate_short_script  # noqa: E402
from app.services.story_input_builder import build_story_input  # noqa: E402
from app.services.story_reliability import run_reliable_story_analysis  # noqa: E402
from benchmark_pipeline import atomic_write_json  # noqa: E402
from dialogue_recall_audit import aggregate_audit  # noqa: E402


MODEL = "qwen3-vl:8b-instruct"
AUDIT_ONLY_KEYS = {"audit_id", "oracle_source", "expected_text", "transcription"}


def _json(value: str | None, fallback: Any) -> Any:
    try:
        parsed = json.loads(value) if value else fallback
        return parsed
    except (json.JSONDecodeError, TypeError):
        return fallback


def persisted_state(project_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.project_id == project_id)
            .order_by(Asset.page_order, Asset.id)
            .all()
        )
        asset_ids = [asset.id for asset in assets]
        truth_rows = (
            db.query(DialogueGroundTruth)
            .filter(DialogueGroundTruth.asset_id.in_(asset_ids))
            .order_by(DialogueGroundTruth.asset_id, DialogueGroundTruth.region_id)
            .all()
            if asset_ids
            else []
        )
        truth_by_key = {(row.asset_id, row.region_id): row for row in truth_rows}
        pages: list[dict[str, Any]] = []
        review_queue: list[dict[str, Any]] = []
        verified_regions: list[dict[str, Any]] = []
        sibling_snapshot: list[dict[str, Any]] = []
        all_region_ids: list[tuple[str, int]] = []
        recovered_provenance: list[dict[str, Any]] = []
        for asset in assets:
            dialogues = _json(asset.dialogues, [])
            regions = _json(asset.vision_regions, [])
            for dialogue in dialogues if isinstance(dialogues, list) else []:
                if not isinstance(dialogue, dict):
                    continue
                region_id = dialogue.get("region_id")
                if isinstance(region_id, int):
                    all_region_ids.append((asset.id, region_id))
                decision = dialogue.get("decision")
                if decision == "needs_review":
                    review_queue.append(
                        {"asset_id": asset.id, "page_order": asset.page_order, "region_id": region_id}
                    )
                sibling_snapshot.append(
                    {
                        "asset_id": asset.id,
                        "page_order": asset.page_order,
                        "region_id": region_id,
                        "decision": decision,
                        "text": dialogue.get("verified_text")
                        or dialogue.get("recovered_text")
                        or dialogue.get("clean_text"),
                    }
                )
                truth = truth_by_key.get((asset.id, region_id))
                if decision == "verified" or dialogue.get("human_verified") is True:
                    verified_regions.append(
                        {
                            "asset_id": asset.id,
                            "page_order": asset.page_order,
                            "region_id": region_id,
                            "verified_text": dialogue.get("verified_text"),
                            "human_verified": dialogue.get("human_verified") is True,
                            "ground_truth_exists": truth is not None,
                            "ground_truth_matches": bool(
                                truth and truth.verified_text == dialogue.get("verified_text")
                            ),
                            "decision": decision,
                            "needs_review": dialogue.get("needs_review") is True,
                        }
                    )
            for region in regions if isinstance(regions, list) else []:
                if not isinstance(region, dict):
                    continue
                provenance = region.get("recovery_provenance") or region.get("provenance")
                if (
                    provenance
                    or region.get("recovered") is True
                    or "recovery_confidence" in region
                ):
                    recovered_provenance.append(
                        {
                            "asset_id": asset.id,
                            "page_order": asset.page_order,
                            "region_id": region.get("id"),
                            "provenance": provenance or "recovery_metadata_preserved",
                        }
                    )
            pages.append(
                {
                    "asset_id": asset.id,
                    "filename": asset.filename,
                    "page_order": asset.page_order,
                    "ocr_status": asset.status,
                    "vision_status": asset.vision_status,
                    "dialogue_status": asset.dialogue_status,
                    "dialogue_count": len(dialogues) if isinstance(dialogues, list) else 0,
                }
            )
        gt_snapshot = [
            {
                "asset_id": row.asset_id,
                "region_id": row.region_id,
                "verified_text": row.verified_text,
            }
            for row in truth_rows
        ]
        return {
            "pages": pages,
            "review_queue": review_queue,
            "review_queue_count": len(review_queue),
            "verified_regions": sorted(
                verified_regions, key=lambda item: (item["page_order"], item["region_id"])
            ),
            "ground_truth": gt_snapshot,
            "ground_truth_count": len(gt_snapshot),
            "sibling_snapshot": sibling_snapshot,
            "represented_regions": len(all_region_ids),
            "unique_region_references": len(set(all_region_ids)),
            "recovered_region_provenance": recovered_provenance,
        }
    finally:
        db.close()


def safety_audit(story_input: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    gt = {(item["asset_id"], item["region_id"]): item for item in state["ground_truth"]}
    represented = 0
    gt_backed = 0
    seen: set[tuple[str, int]] = set()
    for page in story_input.get("pages", []):
        asset_id = page.get("asset_id")
        for dialogue in page.get("dialogues", []):
            represented += 1
            key = (asset_id, dialogue.get("region_id"))
            if key in seen:
                issues.append(f"duplicate Story Input region {key}")
            seen.add(key)
            if dialogue.get("decision") == "needs_review":
                issues.append(f"review-gated region entered Story Input: {key}")
            if dialogue.get("decision") not in {"auto_accepted", "auto_recovered", "verified"}:
                issues.append(f"non-authoritative decision entered Story Input: {key}")
            if dialogue.get("text_source") == "verified":
                gt_row = gt.get(key)
                if not gt_row or gt_row["verified_text"] != dialogue.get("final_text"):
                    issues.append(f"verified Story Input text has no matching Ground Truth: {key}")
                else:
                    gt_backed += 1

    def inspect(value: Any, path: str = "story_input") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in AUDIT_ONLY_KEYS:
                    issues.append(f"audit-only key present at {path}.{key}")
                inspect(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                inspect(child, f"{path}[{index}]")

    inspect(story_input)
    if state["review_queue_count"]:
        issues.append("persisted review queue is not empty")
    if story_input.get("status") != "ready":
        issues.append(f"Story Input status is {story_input.get('status')!r}")
    return {
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
        "represented_regions": represented,
        "ground_truth_backed_dialogues": gt_backed,
        "unresolved_review_gated_regions": state["review_queue"],
        "audit_only_production_contamination": any("audit-only" in issue for issue in issues),
    }


def event_report(reliability: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": event.get("id"),
            "story_role": event.get("story_role"),
            "sources": event.get("sources", []),
            "claim_count": len(event.get("claims", [])) + len(event.get("unsupported_claims", [])),
            "grounded_claim_count": len(event.get("claims", [])),
            "unsupported_claim_count": len(event.get("unsupported_claims", [])),
            "script_ready": event.get("script_ready") is True,
        }
        for event in reliability.get("grounded_result", {}).get("events", [])
    ]


def correctness_invariants(state: dict[str, Any]) -> dict[str, Any]:
    snapshot_path = ROOT / "benchmarks" / "dialogue_recall_audit.v2.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    trusted = aggregate_audit(snapshot["pages"])["aggregate"]
    return {
        "expected_benchmark_regions": 22,
        "represented_regions": state["represented_regions"],
        "unique_region_references": state["unique_region_references"],
        "known_merge_errors": trusted["merge_errors"],
        "known_split_errors": trusted["split_errors"],
        "important_ocr_blocks": sum(p["important_ocr_blocks"] for p in snapshot["pages"]),
        "assigned_important_ocr_blocks": sum(
            p["assigned_important_ocr_blocks"] for p in snapshot["pages"]
        ),
        "recovered_region_provenance": state["recovered_region_provenance"],
        "audit_snapshot_hash": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
        "verification_mode": "persisted_state_plus_trusted_audit; Vision not rerun",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--checkpoint", default="10.12")
    args = parser.parse_args()
    started_at = datetime.now(timezone.utc)
    wall_started = time.perf_counter()
    report: dict[str, Any] = {
        "checkpoint": args.checkpoint,
        "status": "failed",
        "failure_stage": None,
        "issues": [],
        "metadata": {
            "project_id": args.project_id,
            "model": MODEL,
            "deterministic": True,
            "generation_options": DETERMINISTIC_BENCHMARK_OPTIONS,
            "started_at": started_at.isoformat(),
        },
    }
    before = persisted_state(args.project_id)
    story_input: dict[str, Any] = {}
    reliability: dict[str, Any] = {}
    script: dict[str, Any] | None = None
    try:
        report["precondition"] = {
            "review_queue_count": before["review_queue_count"],
            "ground_truth_count": before["ground_truth_count"],
            "page_statuses": before["pages"],
            "human_verified_regions": before["verified_regions"],
        }
        report["failure_stage"] = "precondition"
        if before["review_queue_count"] or before["ground_truth_count"] < 2:
            raise RuntimeError("Human-review prerequisite is incomplete.")
        if any(page["dialogue_status"] != "completed" for page in before["pages"]):
            raise RuntimeError("At least one benchmark page is not dialogue-completed.")

        report["failure_stage"] = "story_input"
        story_input = build_story_input(args.project_id)
        audit = safety_audit(story_input, before)
        report["story_input"] = story_input
        report["story_input_safety_audit"] = audit
        if audit["status"] != "PASS":
            raise RuntimeError("Story Input safety audit failed.")

        report["failure_stage"] = "story_pipeline"
        try:
            with generation_options(DETERMINISTIC_BENCHMARK_OPTIONS), collect_performance() as collector:
                reliability = run_reliable_story_analysis(story_input)
                events = event_report(reliability)
                coverage = reliability.get("coverage", {})
                main_ready = sum(
                    item["script_ready"] and item["story_role"] == "main_story"
                    for item in events
                )
                usable = coverage.get("unresolved_regions") == 0 and main_ready > 0
                if usable:
                    report["failure_stage"] = "short_script"
                    script = generate_short_script(reliability, "dramatic")
        finally:
            performance = collector.report()
            report["performance"] = performance
            report["model_call_breakdown"] = dict(
                Counter(call.get("stage", "unknown") for call in performance["model_calls"])
            )

        report["page_pipeline"] = {
            "reprocessed": False,
            "timing_seconds": 0.0,
            "model_calls": {
                "vision": 0,
                "vision_recovery": 0,
                "reading_order_fallback": 0,
                "dialogue_correction": 0,
                "dialogue_recovery": 0,
                "recovered_region_exception": 0,
            },
        }
        events = event_report(reliability)
        grounded = reliability.get("grounded_result", {})
        report["story_result"] = {
            "usable": usable,
            "analysis_attempts": reliability.get("analysis_attempts"),
            "structural_repair_attempts": reliability.get("analyzer_result", {}).get(
                "repair_attempts", 0
            ),
            "full_retry_attempts": max(0, (reliability.get("analysis_attempts") or 1) - 1),
            "coverage_recovery_attempts": reliability.get("recovery_attempts"),
            "events": events,
            "summary": {
                "total_events": len(events),
                "main_story_events": sum(e["story_role"] == "main_story" for e in events),
                "supporting_context_events": sum(
                    e["story_role"] == "supporting_context" for e in events
                ),
                "script_ready_main_story_events": sum(
                    e["story_role"] == "main_story" and e["script_ready"] for e in events
                ),
                "unsupported_claims": sum(e["unsupported_claim_count"] for e in events),
                "unresolved_evidence": reliability.get("coverage", {}).get(
                    "unresolved_regions"
                ),
            },
            "grounding_summary": grounded.get("summary"),
            "grounding_issues": grounded.get("issues", []),
            "coverage_before_recovery": reliability.get("coverage_before_recovery"),
            "coverage": reliability.get("coverage"),
            "coverage_recovery": reliability.get("recovery_result"),
        }
        report["short_script"] = script
        if not usable:
            raise RuntimeError("Story Result did not satisfy the production usability contract.")
        if not script or len(script.get("segments", [])) != 5:
            raise RuntimeError("Short Script smoke test did not produce five valid segments.")

        report["failure_stage"] = None
        report["status"] = "passed"
    except Exception as error:
        report["issues"].append(str(error))
    finally:
        after = persisted_state(args.project_id)
        report["ground_truth_preservation"] = {
            "unchanged": before["ground_truth"] == after["ground_truth"],
            "human_verified_unchanged": before["verified_regions"] == after["verified_regions"],
            "siblings_unchanged": before["sibling_snapshot"] == after["sibling_snapshot"],
            "duplicate_records_created": after["ground_truth_count"] != len(
                {(item["asset_id"], item["region_id"]) for item in after["ground_truth"]}
            ),
            "before_count": before["ground_truth_count"],
            "after_count": after["ground_truth_count"],
            "records": after["ground_truth"],
        }
        report["correctness_invariants"] = correctness_invariants(after)
        report["wall_clock_seconds"] = round(time.perf_counter() - wall_started, 6)
        report["metadata"]["completed_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write_json(args.output, report)

    perf = report.get("performance", {})
    print("Story revalidation complete")
    print(f"Status: {report['status']}")
    print(f"Story usable: {'YES' if report.get('story_result', {}).get('usable') else 'NO'}")
    print(f"Model calls: {perf.get('total_model_calls', 0)}")
    print(f"Wall clock: {report['wall_clock_seconds']:.2f}s")
    print(f"Artifact: {Path(args.output).expanduser().resolve()}")
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
