from copy import deepcopy

from app.services.reader_v2_final_contract import (
    ORDER_VERSION, OfflineReaderCache, ReliabilityState, build_page_contract, cache_fingerprint,
    reliability_from_validation_features,
)


def raw(region_id=1, bbox=None, text="STAR", confidence=.999, ambiguity=None):
    return {"region_id": region_id, "bbox": bbox or [10, 10, 40, 30], "region_type": "detected_text",
            "crop_bbox": [9, 9, 41, 31], "ocr": {"engine": "easyocr", "version": "1.7.2",
            "config": {"languages": ["vi", "en"]}, "text": text, "confidence": confidence},
            "quality_signals": {"suspiciously_short": len(text.strip()) < 3, "unusual_symbol_ratio": 0},
            "ambiguity_reasons": ambiguity or []}


def test_schema_never_promotes_high_confidence_ocr():
    page = build_page_contract(page_id="p", source_hash="h", source_type="MANGA", raw_regions=[raw()])
    item = page["regions"][0]
    assert item["ocr_reliability_state"] == ReliabilityState.OBSERVED.value
    assert item["requires_repair"] is True
    assert item["authoritative"] is False
    assert item["provenance"]["human_gt_involved"] is False
    assert "human" not in item["ocr_engine"]["config"]


def test_structural_and_unreadable_states_require_repair():
    page = build_page_contract(page_id="p", source_hash="h", source_type="MANGA",
        raw_regions=[raw(1, text="", confidence=None), raw(2, [50, 10, 80, 30], ambiguity=["crop_boundary_warning"])])
    states = {x["region_id"]: x["ocr_reliability_state"] for x in page["regions"]}
    assert states == {1: "UNREADABLE_OR_UNKNOWN", 2: "STRUCTURAL_REVIEW"}
    assert all(x["requires_repair"] and not x["authoritative"] for x in page["regions"])


def test_frozen_manga_order_and_source_type_boundary():
    inputs = [raw("left", [10, 10, 30, 30]), raw("right", [60, 11, 80, 31]), raw("below", [10, 50, 30, 70])]
    manga = build_page_contract(page_id="p", source_hash="h", source_type="MANGA", raw_regions=inputs)
    webtoon = build_page_contract(page_id="p", source_hash="h", source_type="WEBTOON", raw_regions=inputs)
    assert manga["reading_order"] == ["right", "left", "below"]
    assert webtoon["reading_order"] == ["left", "right", "below"]
    assert manga["regions"][0]["algorithm_config_version"]["reading_order"] == ORDER_VERSION


def test_fingerprint_invalidation_and_determinism():
    regions = [{"id": 1, "bbox": [1, 2, 3, 4], "source_type": "detected_text"}]
    engine = {"name": "easyocr", "version": "1.7.2", "config": {"gpu": False}}
    one = cache_fingerprint(source_hash="h", source_type="MANGA", regions=regions, ocr_engine=engine)
    assert one == cache_fingerprint(source_hash="h", source_type="MANGA", regions=deepcopy(regions), ocr_engine=deepcopy(engine))
    assert one != cache_fingerprint(source_hash="h2", source_type="MANGA", regions=regions, ocr_engine=engine)
    assert one != cache_fingerprint(source_hash="h", source_type="WEBTOON", regions=regions, ocr_engine=engine)
    changed_geometry = [{"id": 1, "bbox": [1, 2, 3, 5], "source_type": "detected_text"}]
    assert one != cache_fingerprint(source_hash="h", source_type="MANGA", regions=changed_geometry, ocr_engine=engine)
    assert one != cache_fingerprint(source_hash="h", source_type="MANGA", regions=regions,
                                    ocr_engine={**engine, "config": {"gpu": True}})
    assert one != cache_fingerprint(source_hash="h", source_type="MANGA", regions=regions, ocr_engine=engine,
                                    geometry_version="logical-region-pad.v2")
    assert one != cache_fingerprint(source_hash="h", source_type="MANGA", regions=regions, ocr_engine=engine,
                                    order_version="vertical-overlap-0.60.v2")


def test_output_deterministic_and_authoritative_immutable():
    inputs = [raw(1), raw(2, [50, 10, 80, 30], text='"STAR')]
    one = build_page_contract(page_id="p", source_hash="h", source_type="MANGA", raw_regions=inputs)
    two = build_page_contract(page_id="p", source_hash="h", source_type="MANGA", raw_regions=deepcopy(inputs))
    assert one == two
    assert all(not item["authoritative"] for item in one["regions"])
    assert one["vlm_calls"] == one["ollama_calls"] == 0


def test_real_cache_path_and_validation_safety_mapping():
    cache = OfflineReaderCache(); calls = []
    first, first_status = cache.get_or_build("key", lambda: calls.append(1) or {"output_hash": "same"})
    second, second_status = cache.get_or_build("key", lambda: calls.append(2) or {"output_hash": "different"})
    assert (first_status, second_status, cache.misses, cache.hits, calls) == ("MISS", "HIT", 1, 1, [1])
    assert first is second
    assert reliability_from_validation_features({"min_confidence": .999})[0] == ReliabilityState.HARD
    assert reliability_from_validation_features({"boundary_clipping_warning": True})[0] == ReliabilityState.STRUCTURAL_REVIEW
