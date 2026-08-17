#!/usr/bin/env python3
"""Calculate deterministic recall metrics from a human-authored audit snapshot."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def audit_page(page: dict[str, Any]) -> dict[str, Any]:
    expected = [item for item in page["expected_regions"] if item.get("required", True)]
    detected = [item for item in expected if item.get("detected_region_ids")]
    region_usage = Counter(
        region_id
        for item in expected
        for region_id in item.get("detected_region_ids", [])
    )
    expected_total = len(expected)
    detected_total = len(detected)
    return {
        "filename": page["filename"],
        "expected_dialogue_regions": expected_total,
        "detected_expected_regions": detected_total,
        "detected_pipeline_regions": len(region_usage),
        "bubble_recall": detected_total / expected_total if expected_total else 1.0,
        "missing_dialogue_rate": (expected_total - detected_total) / expected_total if expected_total else 0.0,
        "ocr_missing": sum(item["classification"] == "OCR_MISSING" for item in expected),
        "vision_grouping_missing": sum(item["classification"] == "OCR_PRESENT_REGION_MISSING" for item in expected),
        "partial_dialogues": sum(item["classification"] == "DETECTED_PARTIAL" for item in expected),
        "dropped_later": sum(item["classification"] == "DROPPED_LATER" for item in expected),
        "complete_text": sum(item.get("text_quality") == "COMPLETE" for item in detected),
        "garbled_text": sum(item.get("text_quality") == "GARBLED" for item in detected),
        "text_completeness": sum(item.get("text_quality") == "COMPLETE" for item in detected) / detected_total if detected_total else 0.0,
        "merge_errors": sum(count > 1 for count in region_usage.values()),
        "split_errors": sum(len(item.get("detected_region_ids", [])) > 1 for item in expected),
        "reading_order": page["reading_order"],
        "important_ocr_blocks": page["important_ocr_blocks"],
        "assigned_important_ocr_blocks": page["assigned_important_ocr_blocks"],
        "ignored_meaningful_blocks": page["ignored_meaningful_blocks"],
    }


def aggregate_audit(pages: list[dict[str, Any]]) -> dict[str, Any]:
    reports = [audit_page(page) for page in pages]
    expected = sum(item["expected_dialogue_regions"] for item in reports)
    detected = sum(item["detected_expected_regions"] for item in reports)
    important = sum(item["important_ocr_blocks"] for item in reports)
    assigned = sum(item["assigned_important_ocr_blocks"] for item in reports)
    return {
        "pages": reports,
        "aggregate": {
            "total_expected_dialogue_regions": expected,
            "detected_expected_regions": detected,
            "bubble_recall": detected / expected if expected else 1.0,
            "dialogue_region_recall": detected / expected if expected else 1.0,
            "missing_dialogue_rate": (expected - detected) / expected if expected else 0.0,
            "ocr_block_coverage": assigned / important if important else 1.0,
            "ocr_missing": sum(item["ocr_missing"] for item in reports),
            "vision_grouping_missing": sum(item["vision_grouping_missing"] for item in reports),
            "partial_dialogues": sum(item["partial_dialogues"] for item in reports),
            "dropped_later": sum(item["dropped_later"] for item in reports),
            "complete_text": sum(item["complete_text"] for item in reports),
            "garbled_text": sum(item["garbled_text"] for item in reports),
            "text_completeness": sum(item["complete_text"] for item in reports) / detected if detected else 0.0,
            "merge_errors": sum(item["merge_errors"] for item in reports),
            "split_errors": sum(item["split_errors"] for item in reports),
            "reading_order_errors": sum(item["reading_order"] != "CORRECT" for item in reports),
            "ignored_meaningful_blocks": sum(item["ignored_meaningful_blocks"] for item in reports),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=str(ROOT / "benchmarks/dialogue_recall_audit.v1.json"))
    parser.add_argument("--output")
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text())
    report = aggregate_audit(snapshot["pages"])
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
