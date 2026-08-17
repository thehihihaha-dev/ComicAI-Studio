from __future__ import annotations

import hashlib
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageOps


def _bbox(block: dict[str, Any]) -> list[int] | None:
    points = block.get("box", [])
    if not points:
        return None
    return [
        int(min(point[0] for point in points)),
        int(min(point[1] for point in points)),
        int(max(point[0] for point in points)),
        int(max(point[1] for point in points)),
    ]


def bbox_iou(first: list[int], second: list[int]) -> float:
    intersection_width = max(0, min(first[2], second[2]) - max(first[0], second[0]))
    intersection_height = max(0, min(first[3], second[3]) - max(first[1], second[1]))
    intersection = intersection_width * intersection_height
    union = (
        (first[2] - first[0]) * (first[3] - first[1])
        + (second[2] - second[0]) * (second[3] - second[1])
        - intersection
    )
    return intersection / union if union > 0 else 0.0


def _overlap_fraction(candidate: list[int], existing: list[int]) -> float:
    width = max(0, min(candidate[2], existing[2]) - max(candidate[0], existing[0]))
    height = max(0, min(candidate[3], existing[3]) - max(candidate[1], existing[1]))
    area = max(1, (candidate[2] - candidate[0]) * (candidate[3] - candidate[1]))
    return width * height / area


def merge_duplicate_candidates(
    candidates: list[dict[str, Any]], threshold: float = 0.35
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (-float(item["confidence"]), item["bbox"]),
    ):
        if any(bbox_iou(candidate["bbox"], item["bbox"]) >= threshold for item in kept):
            continue
        kept.append(candidate)
    return sorted(kept, key=lambda item: (item["bbox"][1], item["bbox"][0]))


def detect_empty_dialogue_candidates(
    image_path: str,
    ocr_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Find isolated text-like strokes without consulting OCR text or audit data."""
    started = time.perf_counter()
    if not Path(image_path).is_file():
        return {"candidates": [], "duration_seconds": 0.0, "issues": ["image_unreadable"]}
    grayscale = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if grayscale is None:
        return {"candidates": [], "duration_seconds": 0.0, "issues": ["image_unreadable"]}

    height, width = grayscale.shape
    scale = max(0.5, height / 1280.0)
    dark = (grayscale < 90).astype(np.uint8)
    kernel = np.ones((max(1, round(3 * scale)), max(1, round(5 * scale))), np.uint8)
    grouped = cv2.dilate(dark * 255, kernel, iterations=1)
    _, _, stats, _ = cv2.connectedComponentsWithStats(grouped)
    existing_boxes = [box for block in ocr_blocks if (box := _bbox(block)) is not None]
    candidates = []

    for x, y, candidate_width, candidate_height, grouped_area in stats[1:]:
        if not (
            10 * scale <= candidate_height <= 40 * scale
            and 12 * scale <= candidate_width <= 100 * scale
            and grouped_area >= 80 * scale * scale
        ):
            continue
        core = [int(x), int(y), int(x + candidate_width), int(y + candidate_height)]
        if any(_overlap_fraction(core, box) > 0.15 for box in existing_boxes):
            continue

        crop = dark[y : y + candidate_height, x : x + candidate_width]
        component_count, _, component_stats, _ = cv2.connectedComponentsWithStats(crop)
        meaningful_components = int(
            sum(
                3 * scale * scale <= area <= 200 * scale * scale
                for area in component_stats[1:, cv2.CC_STAT_AREA]
            )
        )
        density = float(crop.mean())
        padding = max(1, round(8 * scale))
        outer = dark[
            max(0, y - padding) : min(height, y + candidate_height + padding),
            max(0, x - padding) : min(width, x + candidate_width + padding),
        ]
        ring_area = max(1, outer.size - crop.size)
        ring_density = max(0.0, float(outer.sum() - crop.sum()) / ring_area)
        aspect_ratio = candidate_width / max(1, candidate_height)
        if not (
            5 <= meaningful_components <= 7
            and 0.10 <= density <= 0.22
            and ring_density <= 0.04
            and 0.75 <= aspect_ratio <= 3.5
        ):
            continue

        crop_padding = max(8, round(12 * scale))
        bbox = [
            max(0, int(x - crop_padding)),
            max(0, int(y - crop_padding)),
            min(width, int(x + candidate_width + crop_padding)),
            min(height, int(y + candidate_height + crop_padding)),
        ]
        digest = hashlib.sha256(f"{width}x{height}:{bbox}".encode()).hexdigest()[:12]
        confidence = min(
            0.90,
            0.72 + 0.02 * meaningful_components + 0.04 * (1 - ring_density / 0.04),
        )
        candidates.append(
            {
                "candidate_id": f"empty-text-{digest}",
                "bbox": bbox,
                "core_bbox": core,
                "candidate_type": "text_region",
                "confidence": round(confidence, 3),
                "evidence": [
                    "text_like_strokes",
                    "isolated_high_contrast_group",
                    "no_ocr_overlap",
                ],
                "metrics": {
                    "component_count": meaningful_components,
                    "dark_density": round(density, 4),
                    "surrounding_dark_density": round(ring_density, 4),
                },
            }
        )

    return {
        "candidates": merge_duplicate_candidates(candidates),
        "duration_seconds": round(time.perf_counter() - started, 6),
        "issues": [],
    }


def run_local_candidate_ocr(
    image_path: str,
    bbox: list[int],
    reader: Any,
) -> dict[str, Any] | None:
    with Image.open(image_path) as image:
        crop = ImageOps.autocontrast(ImageOps.grayscale(image.crop(tuple(bbox))))
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
        results = reader.readtext(np.asarray(crop), detail=1)
    usable = [item for item in results if str(item[1]).strip()]
    if not usable:
        return None
    text = " ".join(str(item[1]).strip() for item in usable)
    confidence = sum(float(item[2]) for item in usable) / len(usable)
    alphanumeric_count = sum(character.isalnum() for character in text)
    return {
        "text": text,
        "confidence": confidence,
        "usable": alphanumeric_count >= 4,
        "needs_review": alphanumeric_count < 4,
    }


def run_visual_candidate_ocr(
    image_path: str,
    bbox: list[int],
    vision_call: Callable[..., dict[str, Any]],
) -> dict[str, Any] | None:
    with Image.open(image_path) as image, tempfile.TemporaryDirectory(
        prefix="empty-dialogue-"
    ) as temporary_directory:
        crop_path = Path(temporary_directory) / "candidate.png"
        image.crop(tuple(bbox)).save(crop_path)
        result = vision_call(
            image_path=str(crop_path),
            prompt=(
                "Transcribe only the text visibly present in this small image crop. "
                "Do not infer hidden text or explain meaning. Return only JSON: "
                '{"text":"...","confidence":0.0}'
            ),
        )
    text = str(result.get("text", "")).strip()
    return {"text": text, "confidence": float(result.get("confidence", 0.0))} if text else None
