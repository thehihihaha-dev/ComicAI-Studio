#!/usr/bin/env python3
"""EasyOCR crop/line reconstruction experiment for Checkpoint 11.7."""

from __future__ import annotations

import hashlib, importlib.metadata, json, os, sys, time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]; BACKEND = ROOT / "backend"
sys.path[:0] = [str(BACKEND), str(ROOT / "scripts")]; load_dotenv(BACKEND / ".env"); os.chdir(BACKEND)
from app.database import SessionLocal  # noqa: E402
from app.models.asset import Asset  # noqa: E402
from app.services.resource_safety import CRITICAL, ResourceThresholds, sample_resources  # noqa: E402
from reader_benchmark import authoritative_snapshot  # noqa: E402
from reader_benchmark_11_4 import evaluate  # noqa: E402
from reader_benchmark_lib import stable_hash, union_rect  # noqa: E402

DAY11 = ROOT / "benchmarks/day11"
HUMAN = DAY11 / "reader-human-verified-11.6.json"; CURRENT = DAY11 / "reader-easyocr-verified-latest.json"
SAMPLES = DAY11 / "reader-line-aware-samples-11.7.json"; COMPARISON = DAY11 / "reader-line-aware-comparison-11.7.json"
DIAGNOSTICS = DAY11 / "reader-crop-diagnostics-11.7.json"; PERFORMANCE = DAY11 / "reader-line-aware-performance-11.7.json"
SCHEMA = "reader-line-aware.v1"; PADDINGS = (0.0, 0.02, 0.05, 0.08)


def padded_box(bbox: list[float], fraction: float, image_size: tuple[int, int]) -> list[int]:
    width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    padding = round(max(width, height) * fraction)
    return [max(0, round(bbox[0]) - padding), max(0, round(bbox[1]) - padding),
            min(image_size[0], round(bbox[2]) + padding), min(image_size[1], round(bbox[3]) + padding)]


def rect(box: Any) -> list[float]:
    return union_rect([box]) or [0, 0, 0, 0]


def order_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(lines, key=lambda item: (round((rect(item["bbox"])[1] + rect(item["bbox"])[3]) / 2, 3),
                                            rect(item["bbox"])[0], str(item.get("id", ""))))


def reconstruct(lines: list[dict[str, Any]]) -> str:
    return " ".join(item.get("text", "").strip() for item in order_lines(lines) if item.get("text", "").strip())


def cache_identity(source_hash: str, bbox: list[float], padding: float, version: str, mode: str, preprocessing: str) -> str:
    return stable_hash({"source_hash": source_hash, "bbox": bbox, "padding": padding, "engine": "easyocr",
                        "version": version, "mode": mode, "preprocessing": preprocessing})


def delta_class(current_cer: float, candidate_cer: float, tolerance: float = 1e-12) -> str:
    if candidate_cer < current_cer - tolerance: return "IMPROVED"
    if candidate_cer > current_cer + tolerance: return "REGRESSED"
    return "UNCHANGED"


def choose_decision(current_cer: float, logical_cer: float, line_cer: float,
                    logical_deltas: dict[str, int], line_deltas: dict[str, int]) -> str:
    """Classify whether explicit persisted-line reconstruction adds value over the logical crop."""
    logical_gain = (current_cer - logical_cer) / current_cer if current_cer else 0.0
    line_gain = (current_cer - line_cer) / current_cer if current_cer else 0.0
    line_over_logical_gain = (logical_cer - line_cer) / logical_cer if logical_cer else 0.0
    logical_consistent = logical_deltas.get("IMPROVED", 0) > logical_deltas.get("REGRESSED", 0)
    line_consistent = line_deltas.get("IMPROVED", 0) > line_deltas.get("REGRESSED", 0)
    if line_gain >= .15 and line_over_logical_gain >= .05 and line_consistent:
        return "A. LINE-AWARE RECONSTRUCTION CLEARLY HELPS"
    if logical_gain >= .15 and logical_consistent and line_over_logical_gain < .05:
        return "B. LOGICAL-REGION CROP HELPS, LINE-AWARE DOES NOT"
    if max(line_gain, logical_gain) < .10:
        return "C. CROP/RECONSTRUCTION IS NOT THE MAIN PROBLEM"
    return "D. RESULTS ARE INCONCLUSIVE"


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(results); chars = sum(len(item["reference_raw"]) for item in results); edits = Counter()
    for item in results: edits.update(item["edit_operations"])
    return {"N": n, "raw_exact": sum(item["raw_exact_match"] for item in results),
            "normalized_exact": sum(item["normalized_exact_match"] for item in results),
            "micro_raw_cer": sum(edits.values()) / chars if chars else None,
            "mean_normalized_cer": sum(item["normalized_cer"] for item in results) / n if n else None,
            "mean_wer": sum(item["wer"] for item in results) / n if n else None,
            "missing": sum(item["missing_text"] for item in results), "edit_counts": dict(edits)}


def run() -> tuple[dict, dict, dict, dict]:
    human = json.loads(HUMAN.read_text(encoding="utf-8")); current = json.loads(CURRENT.read_text(encoding="utf-8"))
    if human["sample_count"] != 20: raise RuntimeError("11.7 requires exactly 20 compatible VERIFIED samples")
    frozen_hash = stable_hash([{"sample_id": s["sample_id"], "ground_truth": s["ground_truth"], "crop_hash": s["crop_hash"]} for s in human["samples"]])
    projects = sorted({s["project_id"] for s in human["samples"]}); before = {p: authoritative_snapshot(p)["state_hash"] for p in projects}
    db = SessionLocal(); geometry, diagnostics = {}, []
    try:
        for sample in human["samples"]:
            asset = db.get(Asset, sample["asset_id"]); blocks = json.loads(asset.ocr_blocks or "[]"); regions = json.loads(asset.vision_regions or "[]")
            region = next((r for r in regions if r.get("id") == sample["region_id"]), None)
            line_ids = region.get("block_ids", []) if region else []
            lines = [{"id": block_id, "bbox": blocks[block_id]["box"], "persisted_text": blocks[block_id].get("text", "")}
                     for block_id in line_ids if isinstance(block_id, int) and 0 <= block_id < len(blocks)]
            ordered_ids = [x["id"] for x in order_lines(lines)]; tags = []
            if len(lines) > 1: tags.append("MULTILINE_FRAGMENTATION")
            if ordered_ids != line_ids: tags.append("LINE_ORDER_ERROR")
            if lines: tags.append("CROP_TOO_TIGHT")  # region bbox is the exact union of line boxes: zero text-edge margin
            if not lines: tags.append("TEXT_DETECTION_MISS")
            geometry[sample["sample_id"]] = {"asset_path": sample["source_path"], "logical_bbox": sample["bbox"], "lines": lines}
            diagnostics.append({"sample_id": sample["sample_id"], "logical_bbox": sample["bbox"],
                                "crop_dimensions": [sample["bbox"][2]-sample["bbox"][0], sample["bbox"][3]-sample["bbox"][1]],
                                "detected_lines": len(lines), "persisted_line_order": line_ids,
                                "geometry_line_order": ordered_ids, "diagnostic_tags": tags or ["UNKNOWN"]})
    finally: db.close()
    thresholds = ResourceThresholds.from_environment(); resource_before = sample_resources(thresholds)
    if resource_before["safety_state"] == CRITICAL: raise SystemExit("FAIL — MACHINE SAFETY before 11.7 OCR")
    import easyocr
    init = time.perf_counter(); reader = easyocr.Reader(["vi", "en"], gpu=False); init_seconds = time.perf_counter()-init
    version = importlib.metadata.version("easyocr"); current_by = {r["sample_id"]: r for r in current["results"]}
    mode_a, mode_b_grid = [], {str(p): [] for p in PADDINGS}; latencies = {"mode_a_cached": 0.0, **{f"mode_b_{p}": 0.0 for p in PADDINGS}}
    for sample in human["samples"]:
        old = current_by[sample["sample_id"]]; mode_a.append({"sample_id": sample["sample_id"], "cache_status": "CACHED_11.6", **{k: old[k] for k in ("reference_raw","hypothesis_raw","raw_exact_match","normalized_exact_match","raw_cer","normalized_cer","wer","edit_operations","missing_text")}})
        with Image.open(geometry[sample["sample_id"]]["asset_path"]) as image:
            rgb=image.convert("RGB"); size=rgb.size
            for padding in PADDINGS:
                box=padded_box(sample["bbox"],padding,size); started=time.perf_counter(); values=reader.readtext(np.asarray(rgb.crop(tuple(box))),detail=1); latency=time.perf_counter()-started
                lines=[{"id": i,"bbox":[[float(point[0]),float(point[1])] for point in value[0]],"text":str(value[1]),"confidence":float(value[2])} for i,value in enumerate(values)]
                text=reconstruct(lines); result=evaluate(sample["ground_truth"],text,min((x["confidence"] for x in lines),default=None))
                mode_b_grid[str(padding)].append({"sample_id":sample["sample_id"],"crop_bbox":box,"padding":padding,
                    "line_boxes":[x["bbox"] for x in order_lines(lines)],"line_order":[x["id"] for x in order_lines(lines)],
                    "raw_line_outputs":[x["text"] for x in order_lines(lines)],"cache_status":"MEASURED_THIS_RUN","latency_seconds":round(latency,6),
                    "cache_key":cache_identity(sample["source_image_hash"],sample["bbox"],padding,version,"logical_crop_readtext","RGB crop"),**result})
                latencies[f"mode_b_{padding}"] += latency
    b_metrics={padding:aggregate(results) for padding,results in mode_b_grid.items()}
    winning_padding=min(b_metrics,key=lambda p:(b_metrics[p]["mean_normalized_cer"],-b_metrics[p]["normalized_exact"],b_metrics[p]["missing"],float(p)))
    mode_c=[]; line_latency=0.0
    for sample in human["samples"]:
        geo=geometry[sample["sample_id"]]
        with Image.open(geo["asset_path"]) as image:
            rgb=image.convert("RGB"); recognized=[]
            for line in order_lines(geo["lines"]):
                box=padded_box(rect(line["bbox"]),float(winning_padding),rgb.size); crop=np.asarray(rgb.crop(tuple(box)).convert("L")); h,w=crop.shape
                started=time.perf_counter(); values=reader.recognize(crop,horizontal_list=[[0,w,0,h]],free_list=[],detail=1,reformat=False); line_latency += time.perf_counter()-started
                recognized.append({"id":line["id"],"bbox":line["bbox"],"crop_bbox":box,"text":" ".join(str(v[1]) for v in values),"confidence":min((float(v[2]) for v in values),default=None)})
        text=reconstruct(recognized); result=evaluate(sample["ground_truth"],text,min((x["confidence"] for x in recognized),default=None))
        mode_c.append({"sample_id":sample["sample_id"],"padding":float(winning_padding),"logical_bbox":sample["bbox"],
                       "line_bboxes":[x["bbox"] for x in order_lines(recognized)],"line_crop_bboxes":[x["crop_bbox"] for x in order_lines(recognized)],
                       "line_order":[x["id"] for x in order_lines(recognized)],"raw_line_outputs":[x["text"] for x in order_lines(recognized)],
                       "final_reconstruction":text,"cache_status":"MEASURED_THIS_RUN",
                       "cache_key":cache_identity(sample["source_image_hash"],sample["bbox"],float(winning_padding),version,"persisted_line_reconstruction","grayscale line crops"),**result})
    resource_after=sample_resources(thresholds); after={p:authoritative_snapshot(p)["state_hash"] for p in projects}
    if before != after: raise RuntimeError("authoritative state changed")
    if frozen_hash != stable_hash([{"sample_id": s["sample_id"], "ground_truth": s["ground_truth"], "crop_hash": s["crop_hash"]} for s in json.loads(HUMAN.read_text())["samples"]]): raise RuntimeError("frozen GT changed")
    a_metrics,c_metrics=aggregate(mode_a),aggregate(mode_c); b_best=b_metrics[winning_padding]
    a_by={x["sample_id"]:x for x in mode_a}; b_by={x["sample_id"]:x for x in mode_b_grid[winning_padding]}; c_by={x["sample_id"]:x for x in mode_c}
    deltas=[]
    for sid in sorted(a_by):
        deltas.append({"sample_id":sid,"current_cer":a_by[sid]["normalized_cer"],"logical_crop_cer":b_by[sid]["normalized_cer"],"line_aware_cer":c_by[sid]["normalized_cer"],
                       "logical_crop_delta":delta_class(a_by[sid]["normalized_cer"],b_by[sid]["normalized_cer"]),
                       "line_aware_delta":delta_class(a_by[sid]["normalized_cer"],c_by[sid]["normalized_cer"])})
    attribution=Counter()
    for d in deltas:
        if d["current_cer"] == 0: attribution["insufficient_evidence_or_no_failure"]+=1
        elif d["line_aware_cer"] + .1 < min(d["current_cer"],d["logical_crop_cer"]): attribution["line_reconstruction_order"]+=1
        elif d["logical_crop_cer"] + .1 < d["current_cer"]: attribution["crop_geometry"]+=1
        elif min(d["logical_crop_cer"],d["line_aware_cer"]) > .1: attribution["ocr_recognition"]+=1
        else: attribution["unknown"]+=1
    sample_art={"schema_version":SCHEMA,"checkpoint":"11.7","artifact_kind":"samples","status":"completed","N":20,
                "engine":{"name":"easyocr","version":version,"languages":["vi","en"],"runtime":"CPU"},"mode_a":mode_a,"mode_b_padding_grid":mode_b_grid,"mode_c":mode_c,"per_sample_deltas":deltas,"vlm_calls":0}
    diagnostics_art={"schema_version":SCHEMA,"checkpoint":"11.7","artifact_kind":"diagnostics","status":"completed","N":20,"samples":diagnostics,"failure_attribution":dict(attribution),"attribution_note":"Observed evidence suggests; not causal proof."}
    comparison={"schema_version":SCHEMA,"checkpoint":"11.7","artifact_kind":"comparison","status":"completed","N":20,"winning_padding":float(winning_padding),
                "metrics":{"current":a_metrics,"logical_crop":b_best,"line_aware":c_metrics,"padding_grid":b_metrics},
                "improvement":{"logical_absolute_cer_reduction":a_metrics["mean_normalized_cer"]-b_best["mean_normalized_cer"],"logical_relative_cer_reduction":(a_metrics["mean_normalized_cer"]-b_best["mean_normalized_cer"])/a_metrics["mean_normalized_cer"],
                               "line_absolute_cer_reduction":a_metrics["mean_normalized_cer"]-c_metrics["mean_normalized_cer"],"line_relative_cer_reduction":(a_metrics["mean_normalized_cer"]-c_metrics["mean_normalized_cer"])/a_metrics["mean_normalized_cer"],
                               "logical_deltas":dict(Counter(d["logical_crop_delta"] for d in deltas)),"line_deltas":dict(Counter(d["line_aware_delta"] for d in deltas))},
                "decision":None,"vlm_calls":0}
    # Evidence-based decision is filled after all measured effects are known.
    comparison["decision"] = choose_decision(
        a_metrics["mean_normalized_cer"], b_best["mean_normalized_cer"], c_metrics["mean_normalized_cer"],
        comparison["improvement"]["logical_deltas"], comparison["improvement"]["line_deltas"],
    )
    performance={"schema_version":SCHEMA,"checkpoint":"11.7","artifact_kind":"performance","status":"completed","N":20,"initialization_seconds":round(init_seconds,6),
                 "latency_seconds":{"mode_a_current":0.0,"mode_a_cache_status":"CACHED_11.6","mode_b_padding_grid":{p:round(latencies[f'mode_b_{float(p)}'],6) for p in b_metrics},"mode_b_winner":round(latencies[f'mode_b_{float(winning_padding)}'],6),"mode_c_line_aware":round(line_latency,6)},
                 "resources":{"before":resource_before,"after":resource_after,"peak_rss_bytes":max(resource_before["process_peak_rss_bytes"],resource_after["process_peak_rss_bytes"]),"swap_delta_bytes":resource_after["swap_used_bytes"]-resource_before["swap_used_bytes"],"safety_state":"CRITICAL" if CRITICAL in (resource_before["safety_state"],resource_after["safety_state"]) else resource_after["safety_state"]},"concurrency":1,"vlm_calls":0,"authoritative_state_unchanged":True}
    for path,data in ((SAMPLES,sample_art),(DIAGNOSTICS,diagnostics_art),(COMPARISON,comparison),(PERFORMANCE,performance)):
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return sample_art,diagnostics_art,comparison,performance


if __name__ == "__main__":
    *_, comparison, = run()[:3]
    print(json.dumps({"decision":comparison["decision"],"winning_padding":comparison["winning_padding"]}))
