from __future__ import annotations

from collections import Counter
from typing import Any, Callable


def block_bbox(block: dict[str, Any]) -> tuple[int, int, int, int] | None:
    points = block.get("box", [])
    if not points or any(not isinstance(point, list) or len(point) != 2 for point in points):
        return None
    return (
        min(int(point[0]) for point in points),
        min(int(point[1]) for point in points),
        max(int(point[0]) for point in points),
        max(int(point[1]) for point in points),
    )


def _gap(first: tuple[int, int], second: tuple[int, int]) -> int:
    return max(0, max(first[0], second[0]) - min(first[1], second[1]))


def blocks_are_neighbors(first: dict[str, Any], second: dict[str, Any]) -> bool:
    a = block_bbox(first)
    b = block_bbox(second)
    if a is None or b is None:
        return False
    horizontal_gap = _gap((a[0], a[2]), (b[0], b[2]))
    vertical_gap = _gap((a[1], a[3]), (b[1], b[3]))
    horizontal_overlap = min(a[2], b[2]) - max(a[0], b[0])
    vertical_overlap = min(a[3], b[3]) - max(a[1], b[1])
    min_width = max(1, min(a[2] - a[0], b[2] - b[0]))
    return (
        (horizontal_overlap / min_width >= 0.20 and vertical_gap <= 36)
        or (vertical_overlap >= 0 and horizontal_gap <= 45)
    )


def cluster_region_blocks(
    block_ids: list[int], ocr_blocks: list[dict[str, Any]]
) -> list[list[int]]:
    valid_ids = [block_id for block_id in block_ids if 0 <= block_id < len(ocr_blocks)]
    remaining = set(valid_ids)
    clusters = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        cluster = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            neighbors = [
                candidate
                for candidate in sorted(remaining)
                if blocks_are_neighbors(ocr_blocks[current], ocr_blocks[candidate])
            ]
            for candidate in neighbors:
                remaining.remove(candidate)
                cluster.add(candidate)
                frontier.append(candidate)
        clusters.append(sorted(cluster))
    return sorted(clusters, key=lambda item: min(item))


def valid_split(original_ids: list[int], clusters: list[list[int]]) -> bool:
    flattened = [block_id for cluster in clusters for block_id in cluster]
    return (
        len(clusters) > 1
        and all(cluster for cluster in clusters)
        and len(flattened) == len(set(flattened))
        and Counter(flattened) == Counter(original_ids)
    )


def split_merged_regions(
    vision_result: dict[str, Any], ocr_blocks: list[dict[str, Any]]
) -> dict[str, Any]:
    original_regions = vision_result.get("regions", [])
    existing_ids = [region.get("id") for region in original_regions if isinstance(region.get("id"), int)]
    next_id = max(existing_ids, default=0) + 1
    original_by_block = {
        block_id: region
        for region in original_regions
        for block_id in region.get("block_ids", [])
    }
    all_block_ids = [
        block_id for region in original_regions for block_id in region.get("block_ids", [])
    ]
    if any(
        not 0 <= block_id < len(ocr_blocks) or block_bbox(ocr_blocks[block_id]) is None
        for block_id in all_block_ids
    ):
        return vision_result
    has_split_candidate = any(
        len(cluster_region_blocks(region.get("block_ids", []), ocr_blocks)) > 1
        for region in original_regions
    )
    if not has_split_candidate:
        return {
            **vision_result,
            "regions": [
                {**region, "region_source": region.get("region_source", "original_layout")}
                for region in original_regions
            ],
        }
    clusters = cluster_region_blocks(all_block_ids, ocr_blocks)
    if not clusters or Counter(block_id for cluster in clusters for block_id in cluster) != Counter(all_block_ids):
        return vision_result
    recovered_regions = []
    used_ids = set()
    structure_changed = False
    original_sets = {region["id"]: set(region.get("block_ids", [])) for region in original_regions}
    for cluster in clusters:
        source_ids = sorted({original_by_block[block_id]["id"] for block_id in cluster})
        preferred_id = original_by_block[min(cluster)]["id"]
        region_id = preferred_id if preferred_id not in used_ids else next_id
        if region_id == next_id:
            next_id += 1
        used_ids.add(region_id)
        unchanged = len(source_ids) == 1 and set(cluster) == original_sets[source_ids[0]]
        structure_changed = structure_changed or not unchanged
        source = original_by_block[min(cluster)]
        recovered_regions.append({
            **source,
            "id": region_id,
            "block_ids": cluster,
            "region_source": "original_layout" if unchanged else "geometry_split",
            **({"split_from_region_ids": source_ids} if not unchanged else {}),
        })

    reading_order = (
        [region["id"] for region in recovered_regions]
        if structure_changed
        else vision_result.get("reading_order", [])
    )
    result = {**vision_result, "regions": recovered_regions, "reading_order": reading_order}
    all_before = [block_id for region in original_regions for block_id in region.get("block_ids", [])]
    all_after = [block_id for region in recovered_regions for block_id in region.get("block_ids", [])]
    if Counter(all_before) != Counter(all_after):
        return vision_result
    return result


def recover_ocr_empty_candidate(
    image_path: str,
    bbox: list[int],
    local_ocr: Callable[[str, list[int]], dict[str, Any] | None],
    vision_ocr: Callable[[str, list[int]], dict[str, Any] | None] | None = None,
    review_threshold: float = 0.90,
) -> dict[str, Any]:
    """Resolve a pre-detected empty dialogue candidate without inventing text.

    Candidate detection is deliberately outside this function: callers must supply
    image-space evidence (a four-coordinate bbox). Local OCR is always attempted
    first; the optional small-crop Vision fallback is called at most once.
    """
    if (
        len(bbox) != 4
        or any(not isinstance(value, int) for value in bbox)
        or bbox[0] >= bbox[2]
        or bbox[1] >= bbox[3]
    ):
        return {
            "resolved": False,
            "bbox": bbox,
            "region_source": "unresolved_visual_candidate",
            "issues": ["invalid_candidate_bbox"],
        }

    attempts = [("local_ocr_recovery", local_ocr)]
    if vision_ocr is not None:
        attempts.append(("vision_ocr_recovery", vision_ocr))
    issues = []
    attempt_results = []
    for source, resolver in attempts:
        result = resolver(image_path, bbox) or {}
        text = str(result.get("text", "")).strip()
        if not text:
            issues.append(f"{source}_empty")
            attempt_results.append({"source": source, "text": "", "usable": False})
            continue
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
        usable = result.get("usable") is not False
        attempt_results.append(
            {
                "source": source,
                "text": text,
                "confidence": confidence,
                "usable": usable,
            }
        )
        if not usable:
            issues.append(f"{source}_unusable")
            continue
        return {
            "resolved": True,
            "bbox": bbox,
            "text": text,
            "confidence": confidence,
            "needs_review": bool(result.get("needs_review"))
            or confidence < review_threshold,
            "region_source": source,
            "issues": issues,
            "attempts": attempt_results,
        }

    return {
        "resolved": False,
        "bbox": bbox,
        "region_source": "unresolved_visual_candidate",
        "issues": issues or ["no_recovery_result"],
        "attempts": attempt_results,
    }


def insert_recovered_region(
    vision_result: dict[str, Any],
    ocr_blocks: list[dict[str, Any]],
    recovered: dict[str, Any],
) -> dict[str, Any]:
    regions = list(vision_result.get("regions", []))
    block_id = len(ocr_blocks)
    bbox = recovered["bbox"]
    ocr_blocks.append(
        {
            "text": recovered["text"],
            "confidence": recovered["confidence"],
            "box": [
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
                [bbox[2], bbox[3]],
                [bbox[0], bbox[3]],
            ],
            "source": recovered["region_source"],
            "needs_review": recovered["needs_review"],
            "candidate_id": recovered.get("candidate_id"),
        }
    )
    region_id = max((int(region["id"]) for region in regions), default=0) + 1
    new_region = {
        "id": region_id,
        "type": "speech_bubble",
        "block_ids": [block_id],
        "region_source": recovered["region_source"],
        "candidate_id": recovered.get("candidate_id"),
        "recovery_confidence": recovered["confidence"],
        "needs_review": recovered["needs_review"],
    }
    order = list(vision_result.get("reading_order", []))
    insertion_index = len(order)
    candidate_center_y = (bbox[1] + bbox[3]) / 2
    candidate_center_x = (bbox[0] + bbox[2]) / 2
    region_by_id = {region["id"]: region for region in regions}
    for index, existing_id in enumerate(order):
        existing = region_by_id.get(existing_id, {})
        boxes = [
            block_bbox(ocr_blocks[item])
            for item in existing.get("block_ids", [])
            if 0 <= item < block_id
        ]
        boxes = [box for box in boxes if box is not None]
        if not boxes:
            continue
        existing_center_y = (min(box[1] for box in boxes) + max(box[3] for box in boxes)) / 2
        existing_center_x = (min(box[0] for box in boxes) + max(box[2] for box in boxes)) / 2
        same_row = abs(candidate_center_y - existing_center_y) <= max(
            40, (bbox[3] - bbox[1]) * 1.5
        )
        if candidate_center_y < existing_center_y - 40 or (
            same_row and candidate_center_x < existing_center_x
        ):
            insertion_index = index
            break
    order.insert(insertion_index, region_id)
    return {**vision_result, "regions": [*regions, new_region], "reading_order": order}


def enforce_recovered_region_review(
    dialogues: list[dict[str, Any]], regions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    review_region_ids = {
        region.get("id")
        for region in regions
        if region.get("needs_review") is True
        and region.get("region_source") in {"local_ocr_recovery", "vision_ocr_recovery"}
    }
    return [
        (
            {
                **dialogue,
                "needs_review": True,
                "decision": "needs_review",
                "reason_code": "recovered_visual_text_requires_review",
                "reason": "Recovered OCR-empty visual text requires human review.",
            }
            if dialogue.get("region_id") in review_region_ids
            and dialogue.get("decision") != "verified"
            and dialogue.get("human_verified") is not True
            else dialogue
        )
        for dialogue in dialogues
    ]
