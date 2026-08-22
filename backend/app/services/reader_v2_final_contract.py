from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Callable

from app.services.reading_order_geometry_experiment import MANGA, WEBTOON, tier_order


CONTRACT_VERSION = "reader-v2.offline-contract.v1"
GEOMETRY_VERSION = "logical-region-pad.v1"
ORDER_VERSION = "vertical-overlap-0.50.benchmark-fitted.v1"
ORDER_RULE = "A_VERTICAL_OVERLAP"


class ReliabilityState(str, Enum):
    OBSERVED = "OBSERVED"
    HARD = "HARD"
    STRUCTURAL_REVIEW = "STRUCTURAL_REVIEW"
    UNREADABLE_OR_UNKNOWN = "UNREADABLE_OR_UNKNOWN"


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def cache_fingerprint(*, source_hash: str, source_type: str, regions: list[dict[str, Any]],
                      ocr_engine: dict[str, Any], geometry_version: str = GEOMETRY_VERSION,
                      order_version: str = ORDER_VERSION) -> str:
    return stable_hash({
        "source_hash": source_hash,
        "source_type": source_type,
        "contract_version": CONTRACT_VERSION,
        "geometry_version": geometry_version,
        "order_version": order_version,
        "order_rule": ORDER_RULE,
        "order_threshold": 0.50,
        "ocr_engine": ocr_engine,
        "regions": [{"id": item["id"], "bbox": item["bbox"], "source_type": item.get("source_type")}
                    for item in regions],
    })


class OfflineReaderCache:
    """Exact-input cache used only by the 11.17 offline runner."""

    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0

    def get_or_build(self, fingerprint: str, builder: Callable[[], dict[str, Any]]) -> tuple[dict[str, Any], str]:
        if fingerprint in self.entries:
            self.hits += 1
            return self.entries[fingerprint], "HIT"
        self.misses += 1
        value = builder()
        self.entries[fingerprint] = value
        return value, "MISS"


def reliability_from_validation_features(features: dict[str, Any]) -> tuple[ReliabilityState, list[str]]:
    """Conservative final-contract mapping; no Human label or transcription input."""
    if features.get("merge_split_warning") or features.get("boundary_clipping_warning"):
        return ReliabilityState.STRUCTURAL_REVIEW, ["structural_signal"]
    return ReliabilityState.HARD, ["day11_router_not_trusted"]


def reliability_for(raw: dict[str, Any]) -> tuple[ReliabilityState, list[str]]:
    ocr = raw.get("ocr") or {}
    text = str(ocr.get("text") or "").strip()
    signals = raw.get("quality_signals") or {}
    structural = list(raw.get("ambiguity_reasons") or [])
    if structural:
        return ReliabilityState.STRUCTURAL_REVIEW, structural
    if not text:
        return ReliabilityState.UNREADABLE_OR_UNKNOWN, ["empty_ocr_observation"]
    if signals.get("suspiciously_short") or signals.get("unusual_symbol_ratio", 0) > .30:
        return ReliabilityState.HARD, ["uncertain_recognition"]
    # Confidence is descriptive only. OBSERVED is intentionally non-authoritative.
    return ReliabilityState.OBSERVED, ["day11_ocr_not_authoritative"]


def build_page_contract(*, page_id: str, source_hash: str, source_type: str,
                        raw_regions: list[dict[str, Any]]) -> dict[str, Any]:
    if source_type not in {MANGA, WEBTOON}:
        raise ValueError("source_type must be MANGA or WEBTOON")
    geometry = [{"id": item["region_id"], "bbox": item["bbox"], "source_type": item.get("region_type", "unknown")}
                for item in raw_regions]
    if source_type == MANGA:
        order_detail = tier_order(geometry, ORDER_RULE, MANGA)
        order_state = "BENCHMARK_FITTED"
    else:
        # The frozen manga rule is deliberately not generalized to webtoon.
        order_detail = tier_order(geometry, ORDER_RULE, WEBTOON)
        order_state = "SOURCE_POLICY_ONLY_NOT_BENCHMARKED"
    positions = {region_id: index for index, region_id in enumerate(order_detail["order"])}
    regions = []
    for raw in raw_regions:
        state, reasons = reliability_for(raw)
        ocr = raw.get("ocr") or {}
        regions.append({
            "page_id": page_id, "source_hash": source_hash, "region_id": raw["region_id"],
            "bbox": raw["bbox"], "source_type": source_type,
            "predicted_group_id": "PAGE", "reading_order_index": positions[raw["region_id"]],
            "reading_order_state": order_state,
            "ocr_raw_text": ocr.get("text", ""), "ocr_confidence": ocr.get("confidence"),
            "ocr_engine": {"name": ocr.get("engine"), "version": ocr.get("version"), "config": ocr.get("config", {})},
            "ocr_structural_flags": list(raw.get("ambiguity_reasons") or []),
            "ocr_reliability_state": state.value, "requires_repair": True,
            "excluded": False, "authoritative": False,
            "provenance": {"source_page": page_id, "source_hash": source_hash,
                           "crop_bbox": raw.get("crop_bbox"), "source_region_id": raw["region_id"],
                           "ocr_engine": ocr.get("engine"), "ocr_config": ocr.get("config", {}),
                           "algorithm_version": CONTRACT_VERSION, "human_gt_involved": False,
                           "reliability_reasons": reasons},
            "algorithm_config_version": {"contract": CONTRACT_VERSION, "geometry": GEOMETRY_VERSION,
                                         "reading_order": ORDER_VERSION, "parameter_status": "BENCHMARK_FITTED"},
        })
    result = {"schema_version": "reader-v2-final-region.v1", "page_id": page_id,
              "source_hash": source_hash, "source_type": source_type,
              "reading_order": order_detail["order"], "reading_order_detail": order_detail,
              "regions": sorted(regions, key=lambda item: item["reading_order_index"]),
              "human_gt_involved": False, "vlm_calls": 0, "ollama_calls": 0}
    result["output_hash"] = stable_hash(result)
    return result
