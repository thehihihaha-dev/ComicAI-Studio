#!/usr/bin/env python3
"""Freeze an unseen, page-grouped OCR validation queue before Human GT."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.logical_region_aggregation import REVISION, aggregate_fragments
from app.services.ocr_acceptance_router_experiment import signal_features

DAY = ROOT / "benchmarks" / "day11"
SOURCE = DAY / "reader-v2-scale-40p-11.10.json"
CALIBRATION = DAY / "reader-logical-region-sample-11.11.json"
OUT = DAY / "reader-router-validation-manifest-11.13.json"
HUMAN = DAY / "reader-router-validation-human-gt-11.13.json"


def _page(page: dict) -> dict:
    fragments = [{
        "region_id": region["region_id"], "bbox": region["bbox"],
        "crop_bbox": region["crop_bbox"], "region_type": region["region_type"],
        "ocr_confidence": region["ocr"]["confidence"],
        "predicted_text": region["ocr"]["text"],
        "routing_state": region["routing_state"],
        "quality_signals": region["quality_signals"],
        "ambiguity_reasons": region["ambiguity_reasons"],
    } for region in page["result"]["regions"]]
    aggregate = aggregate_fragments(fragments)
    logical = []
    by_id = {fragment["region_id"]: fragment for fragment in fragments}
    for region in aggregate["logical_regions"]:
        inputs = [by_id[value] for value in region["source_fragment_ids"]]
        features = signal_features(region, inputs)
        logical.append({**region, "prediction": features["text"], "features": features})
    return {
        "asset_id": page["asset_id"], "page_order": page["page_order"],
        "source_hash": page["source_hash"], "geometry_source": page["diagnostics"]["geometry_source"],
        "representation_version": REVISION, "representation_hash": aggregate["representation_hash"],
        "raw_fragment_count": len(fragments), "logical_region_count": len(logical),
        "logical_regions": logical,
    }


def build() -> dict:
    gate = json.loads(SOURCE.read_text())
    calibration = json.loads(CALIBRATION.read_text())
    calibration_hashes = {page["source_hash"] for page in calibration["pages"]}
    eligible = [_page(page) for page in gate["pages"] if page["source_hash"] not in calibration_hashes and page["result"]["regions"]]
    selected: dict[str, list[str]] = {}

    def take(pages: list[dict], count: int, reason: str) -> None:
        if count <= 0:
            return
        added = 0
        for page in pages:
            if page["asset_id"] in selected:
                continue
            selected[page["asset_id"]] = [reason]
            added += 1
            if added == count:
                return

    take(sorted(eligible, key=lambda p: (-sum(r["features"]["min_confidence"] >= .98 for r in p["logical_regions"]), p["page_order"])), 2, "HIGH_CONFIDENCE_SIGNAL")
    take(sorted(eligible, key=lambda p: (min((r["features"]["min_confidence"] for r in p["logical_regions"]), default=1), p["page_order"])), 2, "LOW_CONFIDENCE_SIGNAL")
    take(sorted(eligible, key=lambda p: (-sum(r["features"]["fragment_count"] > 1 for r in p["logical_regions"]), p["page_order"])), 2, "MULTI_FRAGMENT_STRUCTURE")
    take(sorted(eligible, key=lambda p: (-sum(r["features"]["boundary_clipping_warning"] for r in p["logical_regions"]), p["page_order"])), 1, "BOUNDARY_OR_UNUSUAL_GEOMETRY")
    ordinary = sorted(eligible, key=lambda p: hashlib.sha256(f"11.13:{p['source_hash']}".encode()).hexdigest())
    take(ordinary, 3, "HASH_SEEDED_ORDINARY")
    take(sorted(eligible, key=lambda p: p["page_order"]), 10 - len(selected), "DETERMINISTIC_FILL")
    pages = [{**page, "selection_reasons": selected[page["asset_id"]]} for page in eligible if page["asset_id"] in selected]
    samples = [{
        "sample_id": f"11.13:{page['source_hash'][:12]}:{region['logical_region_id']}",
        "asset_id": page["asset_id"], "page_order": page["page_order"], "source_hash": page["source_hash"],
        "representation_hash": page["representation_hash"], "logical_region_id": region["logical_region_id"],
        "bbox": region["bbox"], "source_fragment_ids": region["source_fragment_ids"],
        "prediction": region["prediction"], "features": region["features"],
    } for page in pages for region in page["logical_regions"]]
    separation = not ({page["source_hash"] for page in pages} & calibration_hashes)
    artifact = {
        "schema_version": "reader-router-validation-manifest.v1", "checkpoint": "11.13",
        "status": "HUMAN_TESTING_REQUIRED", "selection_frozen_before_human_gt": True,
        "source_artifact": SOURCE.name, "source_artifact_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "calibration_artifact": CALIBRATION.name, "calibration_artifact_sha256": hashlib.sha256(CALIBRATION.read_bytes()).hexdigest(),
        "gate_d_pages": len(gate["pages"]), "calibration_pages_excluded": len(calibration_hashes),
        "eligible_unseen_pages": len(eligible), "selected_unseen_pages": len(pages),
        "new_logical_regions": len(samples), "page_grouped": True, "source_hash_separation_passed": separation,
        "selection_method": "pre-GT deterministic strata plus SHA-256 seeded ordinary pages",
        "frozen_router": {"name": "R2", "confidence_threshold": .98, "requires_single_fragment": True, "requires_no_crop_boundary_warning": True},
        "pages": [{k: page[k] for k in ("asset_id", "page_order", "source_hash", "geometry_source", "representation_version", "representation_hash", "raw_fragment_count", "logical_region_count", "selection_reasons")} for page in pages],
        "samples": samples, "annotation_blinding": ["prediction", "confidence", "R2 state"],
        "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0},
    }
    if len(pages) != 10 or not separation:
        raise RuntimeError("11.13 selection or source separation failed")
    OUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    if not HUMAN.exists():
        HUMAN.write_text(json.dumps({"schema_version": "reader-router-validation-human-gt.v1", "checkpoint": "11.13", "status": "HUMAN_TESTING_REQUIRED", "verified_regions": 0, "unreadable_regions": 0, "samples": [], "ground_truth_source": "human-only"}, ensure_ascii=False, indent=2) + "\n")
    return artifact


if __name__ == "__main__":
    result = build()
    print(json.dumps({key: result[key] for key in ("selected_unseen_pages", "new_logical_regions", "calibration_pages_excluded", "source_hash_separation_passed")}, ensure_ascii=False))
