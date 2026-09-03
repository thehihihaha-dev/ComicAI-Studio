#!/usr/bin/env python3
"""Checkpoint 12.2 offline deterministic panel extraction benchmark."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.deterministic_panel_extractor import PanelConfig, REVISION, extract_panels
from app.services.resource_safety import CRITICAL, sample_resources

DAY11 = ROOT / "benchmarks/day11"
DAY12 = ROOT / "benchmarks/day12"
UPLOADS = ROOT / "backend/uploads"
LOGICAL = DAY11 / "reader-logical-region-sample-11.11.json"
MANUAL = DAY12 / "reading-order-failure-audit-12.0.json"


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def image_index() -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for path in sorted(UPLOADS.iterdir()):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            result.setdefault(digest_bytes(path.read_bytes()), []).append(path)
    return result


def contains(panel: list[int], region: list[float]) -> bool:
    return region[0] >= panel[0] and region[1] >= panel[1] and region[2] <= panel[2] and region[3] <= panel[3]


def intersects(panel: list[int], region: list[float]) -> bool:
    return min(panel[2], region[2]) > max(panel[0], region[0]) and min(panel[3], region[3]) > max(panel[1], region[1])


def assign(regions: list[dict], panels: list[dict]) -> tuple[list[dict], Counter]:
    usable = [panel for panel in panels if panel["state"] == "DETECTED"]
    rows, counts = [], Counter()
    for region in regions:
        box = region["bbox"]
        owners = [panel["panel_id"] for panel in usable if contains(panel["bbox"], box)]
        touching = [panel["panel_id"] for panel in usable if intersects(panel["bbox"], box)]
        if len(owners) == 1:
            state = "SINGLE_PANEL_CONTAINED"
        elif len(owners) > 1:
            state = "MULTI_PANEL_CONTAINED"
        elif touching:
            state = "BOUNDARY_INTERSECTION"
        else:
            state = "UNASSIGNED"
        counts[state] += 1
        rows.append({"logical_region_id": region["logical_region_id"], "state": state,
                     "owner_panel_ids": owners, "intersecting_panel_ids": touching})
    return rows, counts


def main() -> None:
    before = sample_resources()
    if before["safety_state"] == CRITICAL:
        raise SystemExit("Resource Guard CRITICAL before deterministic extraction")
    source = json.loads(LOGICAL.read_text(encoding="utf-8"))
    index = image_index()
    config = PanelConfig()
    script_hash = digest_bytes(Path(__file__).read_bytes())
    module_path = ROOT / "backend/app/services/deterministic_panel_extractor.py"
    module_hash = digest_bytes(module_path.read_bytes())
    inputs, runtime_pages = [], []
    for page in source["pages"]:
        matches = index.get(page["source_hash"], [])
        if len(matches) != 1:
            raise RuntimeError(f"page {page['page_order']} source hash resolved to {len(matches)} files")
        path = matches[0]
        with Image.open(path) as image:
            rgb = np.asarray(image.convert("RGB"))
        inputs.append({"page_order": page["page_order"], "asset_id": page["asset_id"],
                       "source_hash": page["source_hash"], "resolved_path": str(path.relative_to(ROOT)),
                       "image_dimensions": [rgb.shape[1], rgb.shape[0]], "hash_verified": True,
                       "logical_region_count": len(page["logical_regions"])})
        runtime_pages.append((page, rgb))
    audit = {"schema_version": "panel-extraction-input-audit.v1", "checkpoint": "12.2",
             "inputs": inputs, "legitimate_extraction_inputs": ["source_page_pixels", "image_dimensions"],
             "diagnostics_only": ["persisted_logical_region_bbox", "persisted_raw_region_geometry", "system_provenance"],
             "forbidden_extraction_inputs": ["human_reading_order_gt", "human_group_or_panel_labels",
                                               "manual_page_15_17_interpretation", "human_corrected_structure"],
             "gt_runtime_features": [], "source_artifact": str(LOGICAL.relative_to(ROOT)),
             "source_artifact_sha256": digest_bytes(LOGICAL.read_bytes())}
    protocol = {"schema_version": "panel-extraction-protocol.v1", "checkpoint": "12.2",
                "revision": REVISION, "configuration": config.payload(),
                "parameter_status": "PREDECLARED_SCALE_NORMALIZED_NOT_BENCHMARK_FITTED",
                "pipeline": ["whitespace_gutter_recursive_partition", "border_contour_evidence",
                             "page_edge_completion", "candidate_fusion", "duplicate_suppression"],
                "gt_runtime_features": [], "ocr_calls": 0, "vlm_calls": 0, "ollama_calls": 0,
                "script_sha256": script_hash, "extractor_sha256": module_hash}
    audit["manifest_sha256"] = digest_bytes(canonical(audit))
    protocol["protocol_sha256"] = digest_bytes(canonical(protocol))
    write_json(DAY12 / "panel-extraction-input-audit-12.2.json", audit)
    write_json(DAY12 / "panel-extraction-protocol-12.2.json", protocol)

    def predict() -> list[dict]:
        pages = []
        for page, rgb in runtime_pages:
            result = extract_panels(rgb, config)
            pages.append({"page_order": page["page_order"], "asset_id": page["asset_id"],
                          "source_hash": page["source_hash"], **result})
        return pages

    started = time.perf_counter()
    first, second = predict(), predict()
    elapsed = time.perf_counter() - started
    first_hash, second_hash = digest_bytes(canonical(first)), digest_bytes(canonical(second))
    if first_hash != second_hash:
        raise RuntimeError("deterministic repeat mismatch")
    predictions = {"schema_version": "panel-predictions.v1", "checkpoint": "12.2",
                   "prediction_stage": "FROZEN_BEFORE_MANUAL_DIAGNOSTICS", "pages": first,
                   "semantic_sha256": first_hash, "gt_runtime_features": []}
    write_json(DAY12 / "panel-predictions-12.2.json", predictions)
    frozen_file_hash = digest_bytes((DAY12 / "panel-predictions-12.2.json").read_bytes())

    # Region geometry enters only after pixel-only predictions have been persisted and hashed.
    page_source = {page["page_order"]: page for page in source["pages"]}
    assignment_rows, aggregate = [], Counter()
    for prediction in first:
        rows, counts = assign(page_source[prediction["page_order"]]["logical_regions"], prediction["panels"])
        aggregate.update(counts)
        assignment_rows.append({"page_order": prediction["page_order"], "assignments": rows, "counts": dict(counts)})
    detected_pages = sum(page["detected_panel_count"] > 0 for page in first)
    detected_panels = sum(page["detected_panel_count"] for page in first)
    ambiguous_panels = sum(page["ambiguous_panel_count"] for page in first)
    unresolved_pages = sum(page["unresolved"] for page in first)
    adjacency_count = sum(len(page["adjacency"]) for page in first)
    usable_adjacency = sum(edge["state"] == "USABLE" for page in first for edge in page["adjacency"])
    ambiguous_adjacency = adjacency_count - usable_adjacency
    metrics = {"schema_version": "panel-structural-metrics.v1", "checkpoint": "12.2",
               "pages": len(first), "pages_with_detected_structure": detected_pages,
               "detected_panels": detected_panels, "ambiguous_panels": ambiguous_panels,
               "unresolved_pages": unresolved_pages, "page_fallback_rate": unresolved_pages / len(first),
               "logical_region_counts": dict(aggregate), "logical_region_total": sum(aggregate.values()),
               "adjacency_edges": adjacency_count, "usable_adjacency_edges": usable_adjacency,
               "ambiguous_adjacency_edges": ambiguous_adjacency,
               "raw_candidates": sum(page["raw_candidate_count"] for page in first),
               "duplicates_suppressed": sum(page["duplicate_candidates_suppressed"] for page in first),
               "panel_precision": "N/A: no independent panel GT", "panel_recall": "N/A: no independent panel GT",
               "panel_iou_accuracy": "N/A: no independent panel GT", "per_page_assignments": assignment_rows,
               "prediction_file_sha256_before_manual_diagnostics": frozen_file_hash,
               "deterministic_repeat": {"runs": 2, "run_1_sha256": first_hash, "run_2_sha256": second_hash,
                                          "semantic_byte_equivalent": True}}
    write_json(DAY12 / "panel-structural-metrics-12.2.json", metrics)

    ambiguities = {"schema_version": "panel-ambiguities.v1", "checkpoint": "12.2",
                   "pages": [{"page_order": page["page_order"], "unresolved": page["unresolved"],
                              "ambiguous_panels": [panel for panel in page["panels"] if panel["state"] == "AMBIGUOUS"]}
                             for page in first]}
    write_json(DAY12 / "panel-ambiguities-12.2.json", ambiguities)

    # This is the first read of manual evidence and occurs after prediction freeze.
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    prediction_by_page = {page["page_order"]: page for page in first}
    diagnostics = []
    for number in (15, 17):
        relevant = [case for case in manual["cases"] if case["page_order"] == number]
        panels = [panel for panel in prediction_by_page[number]["panels"] if panel["state"] == "DETECTED"]
        case_rows = []
        for case in relevant:
            owners = {}
            for region_id, region in case["regions"].items():
                owners[region_id] = [panel["panel_id"] for panel in panels if contains(panel["bbox"], region["bbox"])]
            unique = [value[0] for value in owners.values() if len(value) == 1]
            if prediction_by_page[number]["unresolved"]:
                status = "UNRESOLVED"
            elif any(len(value) != 1 for value in owners.values()):
                status = "AMBIGUOUS"
            elif len(set(unique)) == len(unique):
                status = "SEPARATED"
            else:
                status = "NOT_SEPARATED"
            case_rows.append({"failure_id": case["failure_id"], "status": status,
                              "predicted_owner_panel_ids": owners})
        statuses = [row["status"] for row in case_rows]
        overall = "UNRESOLVED" if "UNRESOLVED" in statuses else "AMBIGUOUS" if "AMBIGUOUS" in statuses else "SEPARATED" if statuses and all(x == "SEPARATED" for x in statuses) else "NOT_SEPARATED"
        diagnostics.append({"page_order": number, "status": overall, "cases": case_rows,
                            "manual_evidence_use": "POST_PREDICTION_QUALITATIVE_DIAGNOSTIC_ONLY"})
    diagnostic_artifact = {"schema_version": "panel-page-diagnostics.v1", "checkpoint": "12.2",
                           "prediction_file_sha256_before_manual_read": frozen_file_hash,
                           "reading_order_scored": False, "pages": diagnostics}
    write_json(DAY12 / "panel-page-15-17-diagnostics-12.2.json", diagnostic_artifact)

    after = sample_resources()
    guard = CRITICAL if CRITICAL in {before["safety_state"], after["safety_state"]} else after["safety_state"]
    if guard == CRITICAL:
        raise SystemExit("Resource Guard became CRITICAL")
    useful_assignments = aggregate["SINGLE_PANEL_CONTAINED"]
    if detected_pages == 0 or useful_assignments == 0:
        outcome = "C. DETERMINISTIC PANEL EXTRACTION IS INSUFFICIENT"
        human_needed = False
    else:
        outcome = "D. PANEL CORRECTNESS CANNOT BE EVALUATED YET"
        human_needed = True
    summary = {"schema_version": "panel-extraction-summary.v1", "checkpoint": "12.2", "outcome": outcome,
               "structural_result": {"pages_with_detected_structure": detected_pages, "detected_panels": detected_panels,
                                     "ambiguous_panels": ambiguous_panels, "unresolved_pages": unresolved_pages,
                                     "single_panel_contained_regions": useful_assignments,
                                     "usable_adjacency_edges": usable_adjacency,
                                     "ambiguous_adjacency_edges": ambiguous_adjacency},
               "page_15_status": diagnostics[0]["status"], "page_17_status": diagnostics[1]["status"],
               "human_panel_gt_needed_next": human_needed,
               "human_validation_if_approved": ({"minimum_pages": 4,
                   "selection": "Pages 15 and 17 plus one detected control and one unresolved/ambiguous control",
                   "marks": "panel polygons/bboxes and ambiguity only; no OCR or Reading Order labels",
                   "decision_unlocked": "panel precision/recall/IoU and whether extraction merits Reader integration"} if human_needed else None),
               "recommended_next_experiment": ("Small independently annotated four-page panel validation gate; no Reader integration yet."
                                               if human_needed else "Evaluate a more capable panel-detection approach before Reader integration."),
               "determinism": metrics["deterministic_repeat"],
               "resources": {"before": before, "after": after, "resource_guard": guard,
                             "elapsed_two_runs_seconds": elapsed},
               "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0},
               "production_changed": False, "human_gt_changed": False}
    write_json(DAY12 / "panel-extraction-summary-12.2.json", summary)
    print(json.dumps({"outcome": outcome, "detected_pages": detected_pages, "detected_panels": detected_panels,
                      "ambiguous_panels": ambiguous_panels, "unresolved_pages": unresolved_pages,
                      "contained_regions": useful_assignments, "page_15": diagnostics[0]["status"],
                      "page_17": diagnostics[1]["status"], "resource_guard": guard}))


if __name__ == "__main__":
    main()
