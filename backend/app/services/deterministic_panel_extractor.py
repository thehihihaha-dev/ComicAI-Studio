"""Offline deterministic manga-panel proposals; no OCR or model inference."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np


REVISION = "deterministic-panel-hybrid.v1"


@dataclass(frozen=True)
class PanelConfig:
    # Scale-normalized, synthetic/domain-derived constants; none are benchmark fitted.
    white_level: int = 245
    gutter_white_fraction: float = 0.985
    min_gutter_fraction: float = 0.008
    min_panel_area_fraction: float = 0.025
    max_panel_area_fraction: float = 0.94
    min_side_fraction: float = 0.08
    contour_rectangularity: float = 0.72
    duplicate_iou: float = 0.82
    conflict_iou: float = 0.10
    edge_terminal_fraction: float = 0.015
    edge_join_fraction: float = 0.02
    max_partition_depth: int = 4

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(mask.tolist() + [False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            result.append((start, index))
            start = None
    return result


def _iou(a: list[int], b: list[int]) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union else 0.0


def _area(box: list[int]) -> int:
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def _trim_white(gray: np.ndarray, box: list[int], config: PanelConfig) -> list[int]:
    x1, y1, x2, y2 = box
    crop = gray[y1:y2, x1:x2]
    ink_rows = np.where(np.mean(crop < config.white_level, axis=1) > .002)[0]
    ink_cols = np.where(np.mean(crop < config.white_level, axis=0) > .002)[0]
    if not len(ink_rows) or not len(ink_cols):
        return box
    return [x1 + int(ink_cols[0]), y1 + int(ink_rows[0]),
            x1 + int(ink_cols[-1]) + 1, y1 + int(ink_rows[-1]) + 1]


def _partition(gray: np.ndarray, box: list[int], config: PanelConfig, depth: int = 0) -> list[list[int]]:
    if depth >= config.max_partition_depth:
        return [_trim_white(gray, box, config)]
    x1, y1, x2, y2 = box
    crop = gray[y1:y2, x1:x2]
    height, width = crop.shape
    if min(height, width) < 12:
        return [box]
    row_white = np.mean(crop >= config.white_level, axis=1) >= config.gutter_white_fraction
    col_white = np.mean(crop >= config.white_level, axis=0) >= config.gutter_white_fraction
    min_row = max(2, round(gray.shape[0] * config.min_gutter_fraction))
    min_col = max(2, round(gray.shape[1] * config.min_gutter_fraction))
    row_runs = [(a, b) for a, b in _runs(row_white) if b - a >= min_row and a > 0 and b < height]
    col_runs = [(a, b) for a, b in _runs(col_white) if b - a >= min_col and a > 0 and b < width]
    choices: list[tuple[float, str, int, int]] = []
    choices += [((b-a) / height, "h", a, b) for a, b in row_runs]
    choices += [((b-a) / width, "v", a, b) for a, b in col_runs]
    if not choices:
        return [_trim_white(gray, box, config)]
    _, axis, start, end = max(choices, key=lambda item: (item[0], item[1], -item[2]))
    if axis == "h":
        children = [[x1, y1, x2, y1 + start], [x1, y1 + end, x2, y2]]
    else:
        children = [[x1, y1, x1 + start, y2], [x1 + end, y1, x2, y2]]
    return [leaf for child in children if _area(child) for leaf in _partition(gray, child, config, depth + 1)]


def _contours(gray: np.ndarray, config: PanelConfig) -> list[dict[str, Any]]:
    height, width = gray.shape
    dark = cv2.threshold(gray, 90, 255, cv2.THRESH_BINARY_INV)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    joined = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(joined, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    result = []
    page_area = width * height
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        box = [x, y, x + w, y + h]
        area_fraction = _area(box) / page_area
        if not (config.min_panel_area_fraction <= area_fraction <= config.max_panel_area_fraction):
            continue
        if w < width * config.min_side_fraction or h < height * config.min_side_fraction:
            continue
        contour_area = cv2.contourArea(contour)
        rectangularity = contour_area / max(1, w * h)
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, .02 * perimeter, True)
        if rectangularity < config.contour_rectangularity or len(approx) > 8:
            continue
        result.append({"bbox": box, "source": "border_contour", "rectangularity": round(rectangularity, 6),
                       "polygon": [[int(point[0][0]), int(point[0][1])] for point in approx]})
    return result


def _line_segments(mask: np.ndarray, horizontal: bool, minimum: int) -> list[list[int]]:
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (minimum, 1) if horizontal else (1, minimum))
    lines = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    segments = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if (width if horizontal else height) >= minimum:
            segments.append([x, y, x + width, y + height])
    return sorted(segments)


def _edge_completions(gray: np.ndarray, config: PanelConfig) -> list[dict[str, Any]]:
    """Complete exactly one page-facing side when the other three borders agree."""
    height, width = gray.shape
    dark = cv2.threshold(gray, 90, 255, cv2.THRESH_BINARY_INV)[1]
    horizontals = _line_segments(dark, True, max(8, round(width * config.min_side_fraction)))
    verticals = _line_segments(dark, False, max(8, round(height * config.min_side_fraction)))
    edge_x = max(2, round(width * config.edge_terminal_fraction))
    edge_y = max(2, round(height * config.edge_terminal_fraction))
    join_x = max(3, round(width * config.edge_join_fraction))
    join_y = max(3, round(height * config.edge_join_fraction))
    candidates: list[dict[str, Any]] = []

    def add(box: list[int], missing: str, evidence: list[list[int]]) -> None:
        if _valid(box, gray.shape, config) and box not in [item["bbox"] for item in candidates]:
            candidates.append({"bbox": box, "source": "page_edge_completion", "completed_edge": missing,
                               "supporting_border_segments": evidence})

    # Missing LEFT/RIGHT: two horizontal borders terminate at the page edge and
    # meet one opposing vertical border at consistent top/bottom endpoints.
    for vertical in verticals:
        vx = round((vertical[0] + vertical[2]) / 2)
        vy1, vy2 = vertical[1], vertical[3]
        top_left = [line for line in horizontals if line[0] <= edge_x and abs(line[1] - vy1) <= join_y
                    and abs(line[2] - vx) <= join_x]
        bottom_left = [line for line in horizontals if line[0] <= edge_x and abs(line[3] - vy2) <= join_y
                       and abs(line[2] - vx) <= join_x]
        for top in top_left:
            for bottom in bottom_left:
                if bottom[1] > top[1] + join_y:
                    add([0, min(top[1], vy1), min(width, max(vertical[2], top[2], bottom[2])),
                         min(height, max(bottom[3], vy2))], "LEFT", [top, vertical, bottom])
        top_right = [line for line in horizontals if line[2] >= width - edge_x and abs(line[1] - vy1) <= join_y
                     and abs(line[0] - vx) <= join_x]
        bottom_right = [line for line in horizontals if line[2] >= width - edge_x and abs(line[3] - vy2) <= join_y
                        and abs(line[0] - vx) <= join_x]
        for top in top_right:
            for bottom in bottom_right:
                if bottom[1] > top[1] + join_y:
                    add([max(0, min(vertical[0], top[0], bottom[0])), min(top[1], vy1), width,
                         min(height, max(bottom[3], vy2))], "RIGHT", [top, vertical, bottom])

    # Missing TOP/BOTTOM: two vertical borders terminate at the page edge and
    # meet one opposing horizontal border at consistent left/right endpoints.
    for horizontal in horizontals:
        hy = round((horizontal[1] + horizontal[3]) / 2)
        hx1, hx2 = horizontal[0], horizontal[2]
        left_top = [line for line in verticals if line[1] <= edge_y and abs(line[0] - hx1) <= join_x
                    and abs(line[3] - hy) <= join_y]
        right_top = [line for line in verticals if line[1] <= edge_y and abs(line[2] - hx2) <= join_x
                     and abs(line[3] - hy) <= join_y]
        for left in left_top:
            for right in right_top:
                if right[0] > left[0] + join_x:
                    add([min(left[0], hx1), 0, min(width, max(right[2], hx2)),
                         min(height, max(horizontal[3], left[3], right[3]))], "TOP", [left, horizontal, right])
        left_bottom = [line for line in verticals if line[3] >= height - edge_y and abs(line[0] - hx1) <= join_x
                       and abs(line[1] - hy) <= join_y]
        right_bottom = [line for line in verticals if line[3] >= height - edge_y and abs(line[2] - hx2) <= join_x
                        and abs(line[1] - hy) <= join_y]
        for left in left_bottom:
            for right in right_bottom:
                if right[0] > left[0] + join_x:
                    add([min(left[0], hx1), max(0, min(horizontal[1], left[1], right[1])),
                         min(width, max(right[2], hx2)), height], "BOTTOM", [left, horizontal, right])
    return candidates


def _valid(box: list[int], shape: tuple[int, int], config: PanelConfig) -> bool:
    height, width = shape
    fraction = _area(box) / (width * height)
    return (config.min_panel_area_fraction <= fraction <= config.max_panel_area_fraction
            and box[2] - box[0] >= width * config.min_side_fraction
            and box[3] - box[1] >= height * config.min_side_fraction)


def extract_panels(image: np.ndarray, config: PanelConfig | None = None) -> dict[str, Any]:
    """Extract panels from pixels alone. Text/Human geometry is not accepted."""
    config = config or PanelConfig()
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    elif image.ndim == 2:
        gray = image.astype(np.uint8, copy=False)
    else:
        raise ValueError("image must be grayscale or RGB pixels")
    height, width = gray.shape
    partitions = [{"bbox": box, "source": "whitespace_partition"}
                  for box in _partition(gray, [0, 0, width, height], config) if _valid(box, gray.shape, config)]
    raw = partitions + _contours(gray, config) + _edge_completions(gray, config)
    raw.sort(key=lambda item: (-_area(item["bbox"]), item["bbox"], item["source"]))
    kept: list[dict[str, Any]] = []
    suppressed = 0
    for candidate in raw:
        duplicate = next((item for item in kept if _iou(candidate["bbox"], item["bbox"]) >= config.duplicate_iou), None)
        if duplicate:
            duplicate.setdefault("sources", [duplicate.pop("source", duplicate.get("sources", [""])[0])])
            if candidate["source"] not in duplicate["sources"]:
                duplicate["sources"].append(candidate["source"])
            duplicate["sources"].sort()
            if candidate.get("polygon") and not duplicate.get("polygon"):
                duplicate["polygon"] = candidate["polygon"]
            duplicate["rectangularity"] = max(duplicate.get("rectangularity", 0), candidate.get("rectangularity", 0))
            if candidate.get("completed_edge"):
                duplicate["completed_edge"] = candidate["completed_edge"]
                duplicate["supporting_border_segments"] = candidate["supporting_border_segments"]
            suppressed += 1
        else:
            kept.append(dict(candidate))
    kept.sort(key=lambda item: (item["bbox"][1], item["bbox"][0], item["bbox"][3], item["bbox"][2]))
    panels = []
    for item in kept:
        sources = item.get("sources", [item.get("source")])
        conflicts = [index for index, other in enumerate(kept) if other is not item
                     and config.conflict_iou < _iou(item["bbox"], other["bbox"]) < config.duplicate_iou]
        state = "DETECTED" if ("page_edge_completion" in sources or len(sources) > 1
                               or (sources == ["whitespace_partition"] and len(partitions) > 1)) else "AMBIGUOUS"
        if conflicts:
            state = "AMBIGUOUS"
        identity = {"revision": REVISION, "bbox": item["bbox"], "sources": sources}
        panel_id = "PN_" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]
        x1, y1, x2, y2 = item["bbox"]
        panel = {"panel_id": panel_id, "bbox": item["bbox"],
                 "bbox_normalized": [round(x1/width, 6), round(y1/height, 6), round(x2/width, 6), round(y2/height, 6)],
                 "state": state, "provenance": sources,
                 "heuristic_evidence": {"score_kind": "UNCALIBRATED_STRUCTURAL_HEURISTIC",
                                        "source_count": len(sources), "rectangularity": item.get("rectangularity")},
                 "touches_page_edge": [name for name, value in (("LEFT", x1 == 0), ("TOP", y1 == 0),
                                                                  ("RIGHT", x2 == width), ("BOTTOM", y2 == height)) if value],
                 "overlap_conflict_indices": conflicts}
        if item.get("completed_edge"):
            panel["page_edge_completion"] = {"completed_edge": item["completed_edge"],
                                              "condition": "three agreeing straight borders terminate at page edge",
                                              "supporting_border_segments": item["supporting_border_segments"]}
        if item.get("polygon"):
            panel["polygon"] = item["polygon"]
        panels.append(panel)
    for panel in panels:
        panel["overlap_conflict_panel_ids"] = [panels[index]["panel_id"] for index in panel.pop("overlap_conflict_indices")]
    adjacency = []
    for index, first in enumerate(panels):
        for second in panels[index + 1:]:
            a, b = first["bbox"], second["bbox"]
            horizontal_overlap = max(0, min(a[2], b[2]) - max(a[0], b[0]))
            vertical_overlap = max(0, min(a[3], b[3]) - max(a[1], b[1]))
            relation = None
            if vertical_overlap and a[2] <= b[0]: relation = "LEFT_OF"
            elif vertical_overlap and b[2] <= a[0]: relation = "RIGHT_OF"
            elif horizontal_overlap and a[3] <= b[1]: relation = "ABOVE"
            elif horizontal_overlap and b[3] <= a[1]: relation = "BELOW"
            if relation:
                adjacency.append({"from": first["panel_id"], "to": second["panel_id"], "relation": relation,
                                  "state": ("USABLE" if first["state"] == second["state"] == "DETECTED"
                                            else "AMBIGUOUS")})
    detected = sum(panel["state"] == "DETECTED" for panel in panels)
    ambiguous = len(panels) - detected
    return {"revision": REVISION, "image_dimensions": [width, height], "panels": panels,
            "detected_panel_count": detected, "ambiguous_panel_count": ambiguous,
            "unresolved": detected == 0, "page_fallback": detected == 0,
            "adjacency": adjacency, "raw_candidate_count": len(raw),
            "duplicate_candidates_suppressed": suppressed,
            "config": config.payload(), "gt_runtime_features": []}
