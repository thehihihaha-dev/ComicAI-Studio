from __future__ import annotations

import hashlib
import json
import time
from enum import Enum
from typing import Any, Protocol

import numpy as np
from PIL import Image


READER_VERSION = "reader-v2.fast-pass.v1"
CROP_REVISION = "logical-region-pad.v1"
ORDER_REVISION = "tiered-panel-order.v1"
DEFAULT_PADDING = 0.02


class ReadingOrderPolicy(str, Enum):
    MANGA_RTL = "MANGA_RTL"
    WEBTOON_VERTICAL = "WEBTOON_VERTICAL"
    WESTERN_LTR = "WESTERN_LTR"


class OCRAdapter(Protocol):
    name: str
    version: str
    config: dict[str, Any]

    def read(self, crop: np.ndarray) -> list[dict[str, Any]]: ...


def bbox_rect(value: Any) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError("bbox must contain coordinates")
    if len(value) == 4 and all(isinstance(item, (int, float)) for item in value):
        box = [float(item) for item in value]
    else:
        points = [point for point in value if isinstance(point, (list, tuple)) and len(point) == 2]
        if not points:
            raise ValueError("bbox polygon is invalid")
        box = [min(float(p[0]) for p in points), min(float(p[1]) for p in points),
               max(float(p[0]) for p in points), max(float(p[1]) for p in points)]
    if box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError("bbox must have positive area")
    return box


def logical_crop_box(bbox: Any, image_size: tuple[int, int], padding: float = DEFAULT_PADDING) -> list[int]:
    if not 0 <= padding <= .10:
        raise ValueError("Reader V2 padding must remain between 0 and 10%")
    x1, y1, x2, y2 = bbox_rect(bbox)
    pixels = round(max(x2 - x1, y2 - y1) * padding)
    return [max(0, round(x1) - pixels), max(0, round(y1) - pixels),
            min(image_size[0], round(x2) + pixels), min(image_size[1], round(y2) + pixels)]


def _overlap(a: list[float], b: list[float]) -> float:
    width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return width * height


def _contains(container: list[float], item: list[float], tolerance: float = 2.0) -> bool:
    return (item[0] >= container[0] - tolerance and item[1] >= container[1] - tolerance
            and item[2] <= container[2] + tolerance and item[3] <= container[3] + tolerance)


def tiered_order(items: list[dict[str, Any]], policy: ReadingOrderPolicy) -> list[Any]:
    if policy not in ReadingOrderPolicy:
        raise ValueError("unsupported reading-order policy")
    remaining = sorted(items, key=lambda item: (bbox_rect(item["bbox"])[1], str(item["id"])))
    tiers: list[list[dict[str, Any]]] = []
    for item in remaining:
        box = bbox_rect(item["bbox"]); center = (box[1] + box[3]) / 2
        target = next((tier for tier in tiers if abs(center - sum((bbox_rect(x["bbox"])[1] + bbox_rect(x["bbox"])[3]) / 2 for x in tier) / len(tier))
                       <= max(4.0, min(box[3]-box[1], max(bbox_rect(x["bbox"])[3]-bbox_rect(x["bbox"])[1] for x in tier)) * .5)), None)
        if target is None:
            tiers.append([item])
        else:
            target.append(item)
    ordered: list[Any] = []
    for tier in tiers:
        reverse = policy == ReadingOrderPolicy.MANGA_RTL
        ordered.extend(item["id"] for item in sorted(tier, key=lambda item: (bbox_rect(item["bbox"])[0], str(item["id"])), reverse=reverse))
    return ordered


def prepare_reading_order(regions: list[dict[str, Any]], panels: list[dict[str, Any]] | None,
                          policy: ReadingOrderPolicy = ReadingOrderPolicy.MANGA_RTL) -> dict[str, Any]:
    panel_items = [{"id": p["id"], "bbox": bbox_rect(p["bbox"])} for p in (panels or [])]
    ambiguity: dict[Any, list[str]] = {region["id"]: [] for region in regions}
    groups: dict[Any, list[dict[str, Any]]] = {}
    if not panel_items:
        groups["PAGE"] = regions
        panel_order = ["PAGE"]
        source = "page_fallback_no_panel_hierarchy"
    else:
        panel_order = tiered_order(panel_items, policy); source = "supplied_panel_geometry"
        for first_index, first in enumerate(panel_items):
            for second in panel_items[first_index + 1:]:
                if _overlap(first["bbox"], second["bbox"]) > 0:
                    for region in regions:
                        if _overlap(bbox_rect(region["bbox"]), first["bbox"]) and _overlap(bbox_rect(region["bbox"]), second["bbox"]):
                            ambiguity[region["id"]].append("crosses_overlapping_panels")
        for region in regions:
            box = bbox_rect(region["bbox"]); owners = [p["id"] for p in panel_items if _contains(p["bbox"], box)]
            if len(owners) == 1:
                groups.setdefault(owners[0], []).append(region)
            elif not owners:
                groups.setdefault("ORPHAN", []).append(region); ambiguity[region["id"]].append("orphan_region")
            else:
                groups.setdefault(owners[0], []).append(region); ambiguity[region["id"]].append("multiple_panel_containment")
        if "ORPHAN" in groups: panel_order.append("ORPHAN")
    order = [region_id for panel_id in panel_order for region_id in tiered_order(groups.get(panel_id, []), policy)]
    return {"policy": policy.value, "panel_source": source, "panel_order": panel_order,
            "reading_order": order, "region_ambiguity": ambiguity}


def quality_signals(text: str, confidence: float | None) -> dict[str, Any]:
    stripped = text.strip(); symbols = sum(not char.isalnum() and not char.isspace() for char in stripped)
    return {"ocr_confidence": confidence, "confidence_is_truth": False, "empty_output": not stripped,
            "suspiciously_short": 0 < len(stripped) < 3,
            "unusual_symbol_ratio": symbols / len(stripped) if stripped else 0.0}


def routing_state(signals: dict[str, Any], ambiguity: list[str]) -> str:
    if ambiguity: return "AMBIGUOUS"
    if signals["empty_output"] or signals["suspiciously_short"] or signals["unusual_symbol_ratio"] > .30:
        return "HARD"
    return "ACCEPT_CANDIDATE"


def fast_pass_fingerprint(source_hash: str, engine: OCRAdapter, policy: ReadingOrderPolicy,
                          regions: list[dict[str, Any]], padding: float = DEFAULT_PADDING,
                          panels: list[dict[str, Any]] | None = None) -> str:
    payload = {"source_hash": source_hash, "reader": READER_VERSION, "crop": CROP_REVISION,
               "padding": padding, "engine": engine.name, "engine_version": engine.version,
               "engine_config": engine.config, "order": ORDER_REVISION, "policy": policy.value,
               "regions": [{"id": r["id"], "bbox": bbox_rect(r["bbox"]), "type": r.get("type", "unknown")} for r in regions],
               "panels": [{"id": p["id"], "bbox": bbox_rect(p["bbox"])} for p in (panels or [])]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ReaderV2FastPass:
    def __init__(self, engine: OCRAdapter, *, padding: float = DEFAULT_PADDING,
                 policy: ReadingOrderPolicy = ReadingOrderPolicy.MANGA_RTL) -> None:
        self.engine, self.padding, self.policy = engine, padding, policy

    def run(self, image_path: str, asset_id: str, source_hash: str, regions: list[dict[str, Any]],
            panels: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        started = time.perf_counter(); crop_seconds = ocr_seconds = 0.0
        with Image.open(image_path) as image:
            rgb = image.convert("RGB"); outputs = []
            order_started = time.perf_counter(); order = prepare_reading_order(regions, panels, self.policy)
            order_seconds = time.perf_counter() - order_started
            for region in regions:
                crop_started = time.perf_counter(); crop_bbox = logical_crop_box(region["bbox"], rgb.size, self.padding)
                crop = np.asarray(rgb.crop(tuple(crop_bbox))); crop_seconds += time.perf_counter() - crop_started
                ocr_started = time.perf_counter(); lines = self.engine.read(crop); ocr_seconds += time.perf_counter() - ocr_started
                lines = sorted(lines, key=lambda line: (bbox_rect(line["bbox"])[1], bbox_rect(line["bbox"])[0], str(line.get("id", ""))))
                text = " ".join(str(line.get("text", "")).strip() for line in lines if str(line.get("text", "")).strip())
                confidence = min((float(line["confidence"]) for line in lines if line.get("confidence") is not None), default=None)
                signals = quality_signals(text, confidence); ambiguity = order["region_ambiguity"][region["id"]]
                outputs.append({"region_id": region["id"], "bbox": bbox_rect(region["bbox"]), "region_type": region.get("type", "unknown"),
                                "crop_bbox": crop_bbox, "crop_dimensions": [crop_bbox[2]-crop_bbox[0], crop_bbox[3]-crop_bbox[1]],
                                "ocr": {"engine": self.engine.name, "version": self.engine.version, "config": self.engine.config,
                                        "text": text, "confidence": confidence, "lines": lines},
                                "quality_signals": signals, "ambiguity_reasons": ambiguity,
                                "routing_state": routing_state(signals, ambiguity)})
        counts = {state: sum(item["routing_state"] == state for item in outputs) for state in ("ACCEPT_CANDIDATE", "HARD", "AMBIGUOUS")}
        return {"reader_version": "v2", "implementation_revision": READER_VERSION, "asset_id": asset_id,
                "source_hash": source_hash, "fingerprint": fast_pass_fingerprint(source_hash, self.engine, self.policy, regions, self.padding, panels),
                "regions": outputs, "reading_order": order["reading_order"], "reading_order_detail": order,
                "stats": {"region_count": len(outputs), **counts, "crop_seconds": crop_seconds,
                          "ocr_inference_seconds": ocr_seconds, "reading_order_seconds": order_seconds,
                          "wall_clock_seconds": time.perf_counter()-started, "vlm_calls": 0, "ollama_calls": 0}}
