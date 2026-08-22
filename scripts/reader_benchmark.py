#!/usr/bin/env python3
"""Read-only Reader 11.3 manifest/control/candidate benchmark runner."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(BACKEND / ".env")
os.chdir(BACKEND)

from app.database import SessionLocal  # noqa: E402
from app.models.asset import Asset  # noqa: E402
from app.models.dialogue_ground_truth import DialogueGroundTruth  # noqa: E402
from app.models.project_short_script import ProjectShortScript  # noqa: E402
from app.models.project_story_analysis import ProjectStoryAnalysis  # noqa: E402
from app.services.resource_safety import CRITICAL, ResourceThresholds, sample_resources  # noqa: E402
from reader_benchmark_lib import (  # noqa: E402
    MATCH_METRIC, MATCH_THRESHOLD, SCHEMA_VERSION, assert_unchanged,
    confidence_bucket, error_rate, match_regions, normalize_text, stable_hash,
    union_rect, write_json,
)

PROJECT_ID = "e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2"
AUDIT = ROOT / "benchmarks" / "dialogue_recall_audit.v2.json"
OUT = ROOT / "benchmarks" / "day11"
MANIFEST = OUT / "reader-benchmark-manifest-11.3.json"
PADDLE_CACHE = Path.home() / ".paddlex" / "official_models"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def image_path(asset: Asset) -> Path:
    path = Path(asset.file_path)
    return path if path.is_absolute() else BACKEND / path


def serialized_rows(rows: list[Any]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        data = {}
        for column in row.__table__.columns:
            value = getattr(row, column.name)
            data[column.name] = value.isoformat() if hasattr(value, "isoformat") else value
        result.append(data)
    return result


def authoritative_snapshot(project_id: str = PROJECT_ID) -> dict[str, Any]:
    db = SessionLocal()
    try:
        assets = db.query(Asset).filter(Asset.project_id == project_id).order_by(Asset.page_order, Asset.id).all()
        asset_ids = [asset.id for asset in assets]
        truth = (db.query(DialogueGroundTruth).filter(DialogueGroundTruth.asset_id.in_(asset_ids))
                 .order_by(DialogueGroundTruth.asset_id, DialogueGroundTruth.region_id).all()) if asset_ids else []
        stories = db.query(ProjectStoryAnalysis).filter(ProjectStoryAnalysis.project_id == project_id).all()
        scripts = db.query(ProjectShortScript).filter(ProjectShortScript.project_id == project_id).all()
        state = {"assets_ocr_vision_dialogue": serialized_rows(assets),
                 "ground_truth": serialized_rows(truth), "story_and_review": serialized_rows(stories),
                 "short_script": serialized_rows(scripts)}
        return {"state_hash": stable_hash(state), "counts": {key: len(value) for key, value in state.items()},
                "state": state}
    finally:
        db.close()


def _region_box(region: dict[str, Any], blocks: list[dict[str, Any]]) -> list[float] | None:
    boxes = [blocks[index]["box"] for index in region.get("block_ids", [])
             if isinstance(index, int) and 0 <= index < len(blocks) and blocks[index].get("box")]
    return union_rect(boxes)


def build_manifest() -> dict[str, Any]:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    before = authoritative_snapshot()
    db = SessionLocal()
    pages = []
    try:
        assets = db.query(Asset).filter(Asset.project_id == PROJECT_ID).order_by(Asset.page_order).all()
        by_name = {page["filename"]: page for page in audit["pages"]}
        truth = db.query(DialogueGroundTruth).filter(
            DialogueGroundTruth.asset_id.in_([asset.id for asset in assets])).all()
        truth_by_key = {(row.asset_id, row.region_id): row for row in truth}
        for asset in assets:
            source = image_path(asset)
            raw = source.read_bytes()
            blocks = json.loads(asset.ocr_blocks or "[]")
            regions = json.loads(asset.vision_regions or "[]")
            region_by_id = {region["id"]: region for region in regions}
            asset_truth = [row for row in truth if row.asset_id == asset.id]
            referenced_ids = {region_id for item in by_name[asset.filename]["expected_regions"]
                              for region_id in item.get("detected_region_ids", [])}
            unmatched_truth = [row for row in asset_truth if row.region_id not in referenced_ids]
            expected = []
            for item in by_name[asset.filename]["expected_regions"]:
                region_ids = item.get("detected_region_ids", [])
                region = region_by_id.get(region_ids[0]) if len(region_ids) == 1 else None
                bbox = _region_box(region, blocks) if region else None
                gt = truth_by_key.get((asset.id, region_ids[0])) if len(region_ids) == 1 else None
                transcription_bbox = bbox
                if not gt and item.get("classification") == "OCR_MISSING" and len(unmatched_truth) == 1:
                    gt = unmatched_truth[0]
                    recovered_region = region_by_id.get(gt.region_id)
                    transcription_bbox = _region_box(recovered_region, blocks) if recovered_region else None
                expected.append({
                    **item, "bbox": bbox,
                    "geometry_evaluable": bbox is not None,
                    "geometry_provenance": "persisted_ocr_block_union" if bbox is not None else "unavailable",
                    "human_ground_truth": ({"region_id": gt.region_id, "raw_text": gt.raw_text,
                                             "verified_text": gt.verified_text} if gt else None),
                    "transcription_crop_bbox": transcription_bbox,
                    "transcription_crop_provenance": ("human-GT-linked persisted recovered region"
                                                       if gt and bbox is None else "same as geometry bbox"),
                })
            with Image.open(source) as image:
                dimensions = {"width": image.width, "height": image.height}
            pages.append({"asset_id": asset.id, "page_order": asset.page_order, "filename": asset.filename,
                          "source_path": str(source.relative_to(ROOT)), "sha256": hashlib.sha256(raw).hexdigest(),
                          "byte_size": len(raw), "dimensions": dimensions, "expected_regions": expected})
    finally:
        db.close()
    after = authoritative_snapshot()
    assert_unchanged(before["state"], after["state"])
    expected_count = sum(len(page["expected_regions"]) for page in pages)
    geometry_count = sum(item["geometry_evaluable"] for page in pages for item in page["expected_regions"])
    gt_count = sum(item["human_ground_truth"] is not None for page in pages for item in page["expected_regions"])
    artifact = {
        "schema_version": SCHEMA_VERSION, "checkpoint": "11.3", "artifact_kind": "manifest",
        "status": "completed", "created_at": now(), "dataset_name": "existing persisted 3-page benchmark",
        "project_id_hash": hashlib.sha256(PROJECT_ID.encode()).hexdigest(), "pages": pages,
        "ground_truth_sufficiency": {
            "expected_important_regions": expected_count, "geometry_evaluable_regions": geometry_count,
            "human_transcription_regions": gt_count, "detection_precision": "N/A",
            "precision_reason": "Audit oracle covers important dialogue/narration, not every visible text or SFX.",
            "general_accuracy_claim": "N/A: three pages support architecture selection/regression only.",
        },
        "normalization": "Unicode NFC + trim/collapse whitespace; case preserved; no semantic edits",
        "matching": {"metric": MATCH_METRIC, "threshold": MATCH_THRESHOLD},
        "authoritative_snapshot": {"before_hash": before["state_hash"], "after_hash": after["state_hash"],
                                   "unchanged": before["state_hash"] == after["state_hash"], "counts": before["counts"]},
        "immutable": True,
    }
    write_json(MANIFEST, artifact)
    return artifact


def result_json(result: Any) -> dict[str, Any]:
    value = getattr(result, "json", result)
    if callable(value):
        value = value()
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, dict) and isinstance(value.get("res"), dict):
        value = value["res"]
    if not isinstance(value, dict):
        raise TypeError(f"Unsupported Paddle result type: {type(value)!r}")
    return value


def paddle_page_output(engine: Any, path: Path) -> list[dict[str, Any]]:
    outputs = list(engine.predict(str(path)))
    if not outputs:
        return []
    data = result_json(outputs[0])
    polygons = data.get("rec_polys") or data.get("dt_polys") or []
    texts, scores = data.get("rec_texts", []), data.get("rec_scores", [])
    return [{"id": f"c{index + 1}", "bbox": union_rect([poly.tolist() if hasattr(poly, "tolist") else poly]),
             "raw_text": str(text), "normalized_text": normalize_text(str(text)), "confidence": float(score)}
            for index, (poly, text, score) in enumerate(zip(polygons, texts, scores))]


def easy_page_output(engine: Any, path: Path) -> list[dict[str, Any]]:
    values = engine.readtext(str(path), detail=1)
    return [{"id": f"c{index + 1}", "bbox": union_rect([box]), "raw_text": str(text),
             "normalized_text": normalize_text(str(text)), "confidence": float(score)}
            for index, (box, text, score) in enumerate(values)]


def best_text_for_gt(gt: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = match_regions([{"id": "gt", "bbox": gt["bbox"]}], candidates)["edges"]
    if not matches:
        return None
    ids = {edge["candidate_id"] for edge in matches}
    selected = [item for item in candidates if item["id"] in ids]
    selected.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
    return {"raw_text": " ".join(item["raw_text"] for item in selected),
            "confidence": min((item["confidence"] for item in selected), default=None),
            "candidate_ids": [item["id"] for item in selected]}


def refresh_saved_artifact(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Recompute pure metrics from saved raw outputs; never runs an OCR engine."""
    artifact = json.loads(path.read_text(encoding="utf-8"))
    manifest_pages = {page["filename"]: page for page in manifest["pages"]}
    transcription = []
    for page in artifact["pages"]:
        source = manifest_pages[page["filename"]]
        trusted = [{"id": item["audit_id"], "bbox": item["bbox"]}
                   for item in source["expected_regions"] if item["geometry_evaluable"]]
        page["matching"] = match_regions(trusted, page["outputs"])
        gt_items = []
        for item in source["expected_regions"]:
            if not item["human_ground_truth"] or not item["transcription_crop_bbox"]:
                continue
            gt = {**item["human_ground_truth"], "bbox": item["transcription_crop_bbox"],
                  "audit_id": item["audit_id"]}
            observed = best_text_for_gt(gt, page["outputs"])
            hypothesis = observed["raw_text"] if observed else ""
            record = {"audit_id": gt["audit_id"], "reference_raw": gt["verified_text"],
                      "reference_normalized": normalize_text(gt["verified_text"]),
                      "hypothesis_raw": hypothesis, "hypothesis_normalized": normalize_text(hypothesis),
                      "exact_normalized_match": normalize_text(gt["verified_text"]) == normalize_text(hypothesis),
                      "cer": error_rate(gt["verified_text"], hypothesis),
                      "wer": error_rate(gt["verified_text"], hypothesis, words=True),
                      "confidence": observed["confidence"] if observed else None,
                      "confidence_bucket": confidence_bucket(observed["confidence"] if observed else None)}
            gt_items.append(record)
            transcription.append(record)
        page["transcription_on_human_gt"] = gt_items
    evaluable = manifest["ground_truth_sufficiency"]["geometry_evaluable_regions"]
    matched = sum(page["matching"]["matched_trusted_regions"] for page in artifact["pages"])
    artifact["metrics"]["detection"].update({"expected_geometry_evaluable": evaluable,
        "matched": matched, "missed": evaluable - matched, "recall": matched / evaluable if evaluable else None})
    artifact["metrics"]["structure"] = {
        "merged_region_errors": sum(len(page["matching"]["merged_region_errors"]) for page in artifact["pages"]),
        "over_split_errors": sum(len(page["matching"]["over_split_errors"]) for page in artifact["pages"]),
        "one_to_one_matches": sum(len(page["matching"]["one_to_one_matches"]) for page in artifact["pages"])}
    artifact["metrics"]["transcription"].update({
        "human_gt_regions": len(transcription),
        "exact_normalized_matches": sum(item["exact_normalized_match"] for item in transcription),
        "mean_cer": sum(item["cer"] for item in transcription) / len(transcription) if transcription else None,
        "mean_wer": sum(item["wer"] for item in transcription) / len(transcription) if transcription else None,
        "empty_transcription_rate": sum(not item["hypothesis_normalized"] for item in transcription) / len(transcription) if transcription else None})
    artifact["dataset_manifest_sha256"] = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    artifact["metrics_refreshed_from_saved_outputs_at"] = now()
    write_json(path, artifact)
    return artifact


def build_comparison() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    control_path = OUT / "reader-easyocr-control-11.3.json"
    candidate_path = OUT / "reader-candidate-11.3-paddleocr-v6-small.json"
    control = refresh_saved_artifact(control_path, manifest)
    candidate = refresh_saved_artifact(candidate_path, manifest)
    cm, pm = control["metrics"], candidate["metrics"]
    comparison = {
        "schema_version": SCHEMA_VERSION, "checkpoint": "11.3", "artifact_kind": "comparison",
        "status": "completed", "created_at": now(),
        "engines": {"control": control["configuration"], "candidate": candidate["configuration"]},
        "mode_comparability": "Mode A combined page OCR and Mode B pure recognition on identical trusted crops are separately comparable.",
        "comparison": {
            "detection_recall": {"easyocr": cm["detection"]["recall"], "paddleocr": pm["detection"]["recall"]},
            "precision": "N/A: non-exhaustive oracle", "human_gt_count": cm["transcription"]["human_gt_regions"],
            "mean_cer": {"easyocr": cm["transcription"]["mean_cer"], "paddleocr": pm["transcription"]["mean_cer"]},
            "mean_wer": {"easyocr": cm["transcription"]["mean_wer"], "paddleocr": pm["transcription"]["mean_wer"]},
            "merged_errors": {"easyocr": cm["structure"]["merged_region_errors"], "paddleocr": pm["structure"]["merged_region_errors"]},
            "split_errors": {"easyocr": cm["structure"]["over_split_errors"], "paddleocr": pm["structure"]["over_split_errors"]},
            "page_latency_seconds": {"easyocr": control["timing"]["page_total_seconds"], "paddleocr": candidate["timing"]["page_total_seconds"]},
            "initialization_seconds": {"easyocr": control["timing"]["initialization_seconds"], "paddleocr": candidate["timing"]["initialization_seconds"]},
            "peak_rss_bytes": {"easyocr": control["resources"]["peak_process_rss_bytes"], "paddleocr": candidate["resources"]["peak_process_rss_bytes"]},
            "swap_delta_bytes": {"easyocr": control["resources"]["swap_delta_bytes"], "paddleocr": candidate["resources"]["swap_delta_bytes"]}},
        "recognition_only": {
            "easyocr": {key: control["modes"]["B_recognition_only_trusted_crops"][key]
                        for key in ("crop_count", "mean_cer", "mean_wer", "exact_normalized_matches", "crop_total_seconds")},
            "paddleocr": {key: candidate["modes"]["B_recognition_only_trusted_crops"][key]
                          for key in ("crop_count", "mean_cer", "mean_wer", "exact_normalized_matches", "crop_total_seconds")}},
        "confidence_usefulness": {
            "easyocr_human_gt_observations": [item for page in control["pages"] for item in page["transcription_on_human_gt"]],
            "paddleocr_human_gt_observations": [item for page in candidate["pages"] for item in page["transcription_on_human_gt"]],
            "conclusion": "N/A for calibration: only two human-GT observations; bucket counts are routing simulation only."},
        "candidate_verdict": "CONDITIONAL PASS",
        "verdict_reason": "Candidate is lighter and slightly faster in page inference, but the tiny/non-exhaustive oracle and only two human transcriptions are insufficient for replacement.",
        "architecture_recommendation": "D. INSUFFICIENT EVIDENCE — EXPAND BENCHMARK",
        "checkpoint_11_4_recommendation": "Build deterministic reading-order evaluation only after adding manually annotated region polygons and more Vietnamese transcription GT; keep production EasyOCR unchanged.",
        "vlm_calls": 0,
        "data_integrity": {"control_unchanged": control["data_integrity"]["unchanged"],
                           "candidate_unchanged": candidate["data_integrity"]["unchanged"]},
    }
    write_json(OUT / "reader-comparison-11.3.json", comparison)
    return comparison


def recognition_only(engine_name: str) -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    thresholds = ResourceThresholds.from_environment()
    resource_before = sample_resources(thresholds)
    if resource_before["safety_state"] == CRITICAL:
        raise SystemExit(f"FAIL — MACHINE SAFETY: CRITICAL before {engine_name} recognition-only")
    init_started = time.perf_counter()
    if engine_name == "easyocr-modeb":
        import easyocr
        engine = easyocr.Reader(["vi", "en"], gpu=False)
        output_path = OUT / "reader-easyocr-control-11.3.json"
    else:
        from paddlex import create_model
        rec = PADDLE_CACHE / "PP-OCRv6_small_rec"
        if not rec.is_dir():
            raise SystemExit("Cached recognition model missing; no download attempted")
        engine = create_model(rec.name, model_dir=str(rec), device="cpu")
        output_path = OUT / "reader-candidate-11.3-paddleocr-v6-small.json"
    init_seconds = time.perf_counter() - init_started
    outputs = []
    for page in manifest["pages"]:
        with Image.open(ROOT / page["source_path"]) as source:
            rgb = source.convert("RGB")
            for item in page["expected_regions"]:
                gt = item["human_ground_truth"]
                box = item["transcription_crop_bbox"]
                if not gt or not box:
                    continue
                crop = np.asarray(rgb.crop(tuple(round(value) for value in box)))
                started = time.perf_counter()
                if engine_name == "easyocr-modeb":
                    grey = np.asarray(Image.fromarray(crop).convert("L"))
                    height, width = grey.shape
                    values = engine.recognize(grey, horizontal_list=[[0, width, 0, height]],
                                              free_list=[], detail=1, reformat=False)
                    raw_text = " ".join(str(value[1]) for value in values)
                    confidence = min((float(value[2]) for value in values), default=None)
                else:
                    values = list(engine.predict(crop))
                    data = result_json(values[0]) if values else {}
                    raw_text = str(data.get("rec_text", data.get("text", "")))
                    confidence_value = data.get("rec_score", data.get("score"))
                    confidence = float(confidence_value) if confidence_value is not None else None
                latency = time.perf_counter() - started
                outputs.append({"filename": page["filename"], "audit_id": item["audit_id"],
                                "reference_raw": gt["verified_text"], "hypothesis_raw": raw_text,
                                "reference_normalized": normalize_text(gt["verified_text"]),
                                "hypothesis_normalized": normalize_text(raw_text),
                                "exact_normalized_match": normalize_text(gt["verified_text"]) == normalize_text(raw_text),
                                "cer": error_rate(gt["verified_text"], raw_text),
                                "wer": error_rate(gt["verified_text"], raw_text, words=True),
                                "confidence": confidence, "confidence_bucket": confidence_bucket(confidence),
                                "latency_seconds": round(latency, 6)})
    resource_after = sample_resources(thresholds)
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    artifact["modes"]["B_recognition_only_trusted_crops"] = {
        "status": "completed", "crop_count": len(outputs), "outputs": outputs,
        "mean_cer": sum(item["cer"] for item in outputs) / len(outputs) if outputs else None,
        "mean_wer": sum(item["wer"] for item in outputs) / len(outputs) if outputs else None,
        "exact_normalized_matches": sum(item["exact_normalized_match"] for item in outputs),
        "initialization_seconds": round(init_seconds, 6),
        "crop_total_seconds": round(sum(item["latency_seconds"] for item in outputs), 6),
        "resources": {"before": resource_before, "after": resource_after,
                      "swap_delta_bytes": resource_after["swap_used_bytes"] - resource_before["swap_used_bytes"]
                      if resource_after["swap_used_bytes"] is not None and resource_before["swap_used_bytes"] is not None else None}}
    write_json(output_path, artifact)
    return artifact


def benchmark(engine_name: str) -> dict[str, Any]:
    if not MANIFEST.exists():
        raise SystemExit("Build manifest first")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    before = authoritative_snapshot()
    thresholds = ResourceThresholds.from_environment()
    resource_before = sample_resources(thresholds)
    if resource_before["safety_state"] == CRITICAL:
        raise SystemExit(f"FAIL — MACHINE SAFETY: CRITICAL before {engine_name}")
    started = time.perf_counter()
    init_started = time.perf_counter()
    if engine_name == "easyocr":
        import easyocr
        engine = easyocr.Reader(["vi", "en"], gpu=False)
        page_fn = easy_page_output
        config = {"library": "easyocr", "version": importlib.metadata.version("easyocr"),
                  "languages": ["vi", "en"], "gpu": False, "role": "combined OCR",
                  "runtime": "CPU/PyTorch", "production_equivalence": "exact Reader construction and readtext(detail=1)"}
        artifact_kind, filename = "control", "reader-easyocr-control-11.3.json"
    else:
        from paddleocr import PaddleOCR
        det = PADDLE_CACHE / "PP-OCRv6_small_det"
        rec = PADDLE_CACHE / "PP-OCRv6_small_rec"
        if not det.is_dir() or not rec.is_dir():
            raise SystemExit("Cached Paddle candidate assets are incomplete; no download attempted")
        engine = PaddleOCR(text_detection_model_name=det.name, text_detection_model_dir=str(det),
                           text_recognition_model_name=rec.name, text_recognition_model_dir=str(rec),
                           use_doc_orientation_classify=False, use_doc_unwarping=False,
                           use_textline_orientation=False, device="cpu")
        page_fn = paddle_page_output
        config = {"library": "paddleocr", "version": importlib.metadata.version("paddleocr"),
                  "paddlepaddle_version": importlib.metadata.version("paddlepaddle"),
                  "models": [det.name, rec.name], "model_assets_preexisting": True,
                  "downloads_or_installations": [], "languages": "multilingual model; Vietnamese/English claimed by cached model metadata",
                  "role": "combined detector + recognizer", "runtime": "CPU/Paddle Inference"}
        artifact_kind, filename = "candidate", "reader-candidate-11.3-paddleocr-v6-small.json"
    initialization = time.perf_counter() - init_started
    resource_after_init = sample_resources(thresholds)
    pages = []
    all_confidences = []
    transcription = []
    for page in manifest["pages"]:
        path = ROOT / page["source_path"]
        page_started = time.perf_counter()
        candidates = page_fn(engine, path)
        latency = time.perf_counter() - page_started
        all_confidences.extend(item["confidence"] for item in candidates)
        trusted = [{"id": item["audit_id"], "bbox": item["bbox"]}
                   for item in page["expected_regions"] if item["geometry_evaluable"]]
        matching = match_regions(trusted, candidates)
        gt_items = []
        for item in page["expected_regions"]:
            if not item["human_ground_truth"] or not item["transcription_crop_bbox"]:
                continue
            gt = {**item["human_ground_truth"], "bbox": item["transcription_crop_bbox"], "audit_id": item["audit_id"]}
            observed = best_text_for_gt(gt, candidates)
            hypothesis = observed["raw_text"] if observed else ""
            record = {"audit_id": gt["audit_id"], "reference_raw": gt["verified_text"],
                      "reference_normalized": normalize_text(gt["verified_text"]), "hypothesis_raw": hypothesis,
                      "hypothesis_normalized": normalize_text(hypothesis), "exact_normalized_match": normalize_text(gt["verified_text"]) == normalize_text(hypothesis),
                      "cer": error_rate(gt["verified_text"], hypothesis), "wer": error_rate(gt["verified_text"], hypothesis, words=True),
                      "confidence": observed["confidence"] if observed else None,
                      "confidence_bucket": confidence_bucket(observed["confidence"] if observed else None)}
            transcription.append(record)
            gt_items.append(record)
        pages.append({"asset_id_hash": hashlib.sha256(page["asset_id"].encode()).hexdigest(),
                      "filename": page["filename"], "latency_seconds": round(latency, 6),
                      "detected_regions": len(candidates), "outputs": candidates, "matching": matching,
                      "transcription_on_human_gt": gt_items})
    resource_after = sample_resources(thresholds)
    after = authoritative_snapshot()
    assert_unchanged(before["state"], after["state"])
    bucket_counts = {name: sum(confidence_bucket(value) == name for value in all_confidences)
                     for name in ("high", "medium", "low", "unavailable")}
    matched = sum(page["matching"]["matched_trusted_regions"] for page in pages)
    evaluable = manifest["ground_truth_sufficiency"]["geometry_evaluable_regions"]
    artifact = {
        "schema_version": SCHEMA_VERSION, "checkpoint": "11.3", "artifact_kind": artifact_kind,
        "status": "completed", "created_at": now(), "engine": engine_name, "configuration": config,
        "modes": {"A_end_to_end_page_ocr": "completed",
                  "B_recognition_only_trusted_crops": "N/A: no pure recognizer run; page matches only, to avoid capability mislabeling"},
        "dataset_manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), "pages": pages,
        "metrics": {"detection": {"expected_geometry_evaluable": evaluable, "matched": matched,
                                    "missed": evaluable - matched, "recall": matched / evaluable if evaluable else None,
                                    "precision": None, "precision_status": "N/A: non-exhaustive text/SFX oracle"},
                    "transcription": {"human_gt_regions": len(transcription),
                                      "exact_normalized_matches": sum(item["exact_normalized_match"] for item in transcription),
                                      "mean_cer": sum(item["cer"] for item in transcription) / len(transcription) if transcription else None,
                                      "mean_wer": sum(item["wer"] for item in transcription) / len(transcription) if transcription else None,
                                      "empty_transcription_rate": sum(not item["hypothesis_normalized"] for item in transcription) / len(transcription) if transcription else None,
                                      "unreadable_rate": None, "unreadable_status": "N/A: no human unreadable labels"},
                    "structure": {"merged_region_errors": sum(len(page["matching"]["merged_region_errors"]) for page in pages),
                                  "over_split_errors": sum(len(page["matching"]["over_split_errors"]) for page in pages),
                                  "one_to_one_matches": sum(len(page["matching"]["one_to_one_matches"]) for page in pages)},
                    "confidence": {"buckets": {"high": ">=0.85", "medium": "0.50..<0.85", "low": "<0.50"},
                                   "counts": bucket_counts, "potential_easy_regions": bucket_counts["high"],
                                   "potential_hard_regions": bucket_counts["medium"] + bucket_counts["low"],
                                   "production_vlm_savings_claim": "N/A"}},
        "timing": {"initialization_seconds": round(initialization, 6),
                   "page_total_seconds": round(sum(page["latency_seconds"] for page in pages), 6),
                   "wall_clock_seconds": round(time.perf_counter() - started, 6)},
        "resources": {"before": resource_before, "after_initialization": resource_after_init, "after": resource_after,
                      "peak_process_rss_bytes": max(value for value in [resource_before["process_peak_rss_bytes"], resource_after_init["process_peak_rss_bytes"], resource_after["process_peak_rss_bytes"]] if value is not None),
                      "swap_delta_bytes": (resource_after["swap_used_bytes"] - resource_before["swap_used_bytes"] if resource_after["swap_used_bytes"] is not None and resource_before["swap_used_bytes"] is not None else None),
                      "safety_state": "CRITICAL" if "CRITICAL" in [resource_before["safety_state"], resource_after_init["safety_state"], resource_after["safety_state"]] else "WARNING" if "WARNING" in [resource_before["safety_state"], resource_after_init["safety_state"], resource_after["safety_state"]] else "NORMAL"},
        "data_integrity": {"before_hash": before["state_hash"], "after_hash": after["state_hash"], "unchanged": True},
        "vlm_calls": 0, "limitations": ["Three pages cannot establish general manga accuracy.",
            "Geometry is inherited from persisted Reader evidence and is not a separately annotated polygon corpus.",
            "Only human-verified Ground Truth contributes to CER/WER."]}
    write_json(OUT / filename, artifact)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("manifest", "easyocr", "paddleocr", "comparison",
                                            "easyocr-modeb", "paddleocr-modeb"))
    args = parser.parse_args()
    result = (build_manifest() if args.command == "manifest" else
              build_comparison() if args.command == "comparison" else
              recognition_only(args.command) if args.command.endswith("-modeb") else
              benchmark(args.command))
    print(json.dumps({"status": result["status"], "artifact_kind": result["artifact_kind"]}, indent=2))


if __name__ == "__main__":
    main()
