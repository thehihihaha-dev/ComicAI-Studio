from __future__ import annotations

import hashlib
import json
from typing import Any


def clip_box(box: list[float], image_size: tuple[int, int], padding: int = 0) -> list[int]:
    width, height = image_size
    return [max(0, int(round(box[0])) - padding), max(0, int(round(box[1])) - padding),
            min(width, int(round(box[2])) + padding), min(height, int(round(box[3])) + padding)]


def proportional_box(box: list[float], image_size: tuple[int, int], fraction: float = .02) -> list[int]:
    padding = round(max(box[2] - box[0], box[3] - box[1]) * fraction)
    return clip_box(box, image_size, padding)


def adaptive_box(box: list[float], image_size: tuple[int, int]) -> list[int]:
    dimension = max(box[2] - box[0], box[3] - box[1])
    return clip_box(box, image_size, max(3, min(14, round(dimension * .04))))


def ordered_fragments(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(fragments, key=lambda item: (
        round((item["bbox"][1] + item["bbox"][3]) / 2, 3), item["bbox"][0], str(item["region_id"])))


def geometry_audit(logical_box: list[float], fragments: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = ordered_fragments(fragments)
    tags: list[str] = []
    overlaps = distant = duplicate = 0
    heights = [max(1.0, fragment["bbox"][3] - fragment["bbox"][1]) for fragment in fragments]
    median_h = sorted(heights)[len(heights) // 2] if heights else 1.0
    for index, left in enumerate(fragments):
        a = left["bbox"]
        for right in fragments[index + 1:]:
            b = right["bbox"]
            if a == b:
                duplicate += 1
            intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
            if intersection:
                overlaps += 1
            x_gap = max(0, max(a[0], b[0]) - min(a[2], b[2]))
            y_gap = max(0, max(a[1], b[1]) - min(a[3], b[3]))
            if max(x_gap, y_gap) > median_h * 2.5:
                distant += 1
    if fragments and any(abs(fragment["bbox"][axis] - logical_box[axis]) <= 1 for fragment in fragments for axis in range(4)):
        tags.append("CROP_TOO_TIGHT")
    if len(fragments) > 1:
        tags.append("MULTI_FRAGMENT")
    if [fragment["region_id"] for fragment in ordered] != [fragment["region_id"] for fragment in fragments]:
        tags.append("FRAGMENT_ORDER_CHANGED")
    if overlaps:
        tags.append("OVERLAPPING_FRAGMENTS")
    if duplicate:
        tags.append("DUPLICATED_FRAGMENTS")
    if distant:
        tags.append("AMBIGUOUS_FRAGMENT_OWNERSHIP")
    vertical = sum(ordered[index]["bbox"][1] >= ordered[index - 1]["bbox"][3] for index in range(1, len(ordered)))
    if vertical:
        tags.append("VERTICALLY_STACKED")
    return {"tags": tags or ["NO_GEOMETRY_WARNING"], "overlap_pairs": overlaps, "duplicate_pairs": duplicate,
            "distant_pairs": distant, "geometry_order": [fragment["region_id"] for fragment in ordered],
            "structural_review": bool(overlaps or duplicate or distant)}


def reconstruct_text(lines: list[dict[str, Any]]) -> str:
    return " ".join(str(line.get("text", "")).strip() for line in ordered_fragments(lines) if str(line.get("text", "")).strip())


def cache_key(source_hash: str, box: list[float], fragment_boxes: list[list[float]], candidate: str, engine_version: str) -> str:
    value = {"source_hash": source_hash, "box": box, "fragment_boxes": fragment_boxes, "candidate": candidate,
             "engine": "easyocr", "engine_version": engine_version, "languages": ["vi", "en"], "gpu": False}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
