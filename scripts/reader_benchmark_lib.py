"""Pure, network-free metrics and validation for Reader checkpoint 11.3."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "reader-benchmark.v1"
MATCH_METRIC = "intersection_over_smaller_region"
MATCH_THRESHOLD = 0.5


def normalize_text(value: str) -> str:
    """Normalize representation only; case and semantic content are preserved."""
    return " ".join(unicodedata.normalize("NFC", value).split())


def edit_distance(left: list[str] | str, right: list[str] | str) -> int:
    previous = list(range(len(right) + 1))
    for row, lhs in enumerate(left, 1):
        current = [row]
        for column, rhs in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[column] + 1,
                               previous[column - 1] + (lhs != rhs)))
        previous = current
    return previous[-1]


def error_rate(reference: str, hypothesis: str, *, words: bool = False) -> float | None:
    reference = normalize_text(reference)
    hypothesis = normalize_text(hypothesis)
    lhs: list[str] | str = reference.split() if words else reference
    rhs: list[str] | str = hypothesis.split() if words else hypothesis
    if not lhs:
        return 0.0 if not rhs else None
    return edit_distance(lhs, rhs) / len(lhs)


def evaluation_normalize_text(value: str) -> str:
    """Evaluation normalization adds case-folding but preserves punctuation/diacritics."""
    return normalize_text(value).casefold()


def edit_operations(reference: str, hypothesis: str) -> dict[str, int]:
    """Return deterministic character insert/delete/substitute counts."""
    rows, columns = len(reference) + 1, len(hypothesis) + 1
    costs = [[0] * columns for _ in range(rows)]
    ops = [[(0, 0, 0)] * columns for _ in range(rows)]
    for row in range(1, rows):
        costs[row][0], ops[row][0] = row, (0, row, 0)
    for column in range(1, columns):
        costs[0][column], ops[0][column] = column, (column, 0, 0)
    for row in range(1, rows):
        for column in range(1, columns):
            if reference[row - 1] == hypothesis[column - 1]:
                costs[row][column], ops[row][column] = costs[row - 1][column - 1], ops[row - 1][column - 1]
                continue
            choices = [
                (costs[row][column - 1] + 1, (ops[row][column - 1][0] + 1, ops[row][column - 1][1], ops[row][column - 1][2])),
                (costs[row - 1][column] + 1, (ops[row - 1][column][0], ops[row - 1][column][1] + 1, ops[row - 1][column][2])),
                (costs[row - 1][column - 1] + 1, (ops[row - 1][column - 1][0], ops[row - 1][column - 1][1], ops[row - 1][column - 1][2] + 1)),
            ]
            costs[row][column], ops[row][column] = min(choices, key=lambda item: (item[0], item[1]))
    insertions, deletions, substitutions = ops[-1][-1]
    return {"insertions": insertions, "deletions": deletions, "substitutions": substitutions}


def confidence_analysis_bucket(value: float | None) -> str:
    if value is None:
        return "unavailable"
    if value >= 0.95:
        return "0.95-1.00"
    if value >= 0.90:
        return "0.90-0.95"
    if value >= 0.80:
        return "0.80-0.90"
    if value >= 0.60:
        return "0.60-0.80"
    return "<0.60"


def classify_errors(reference: str, hypothesis: str) -> list[str]:
    import string
    if not hypothesis:
        return ["MISSING_REGION"]
    if reference == hypothesis:
        return []
    errors: list[str] = []
    if normalize_text(reference).casefold() == normalize_text(hypothesis).casefold() and reference != hypothesis:
        errors.append("CASE_ERROR")
    strip_punctuation = lambda value: "".join(char for char in value if char not in string.punctuation)
    if evaluation_normalize_text(strip_punctuation(reference)) == evaluation_normalize_text(strip_punctuation(hypothesis)):
        errors.append("PUNCTUATION_ERROR")
    strip_marks = lambda value: "".join(char for char in unicodedata.normalize("NFD", value) if not unicodedata.combining(char))
    if evaluation_normalize_text(strip_marks(reference)) == evaluation_normalize_text(strip_marks(hypothesis)):
        errors.append("DIACRITIC_ERROR")
    if any("CJK" in unicodedata.name(char, "") for char in hypothesis) and not any("CJK" in unicodedata.name(char, "") for char in reference):
        errors.append("LANGUAGE_CONFUSION")
    operations = edit_operations(reference, hypothesis)
    if operations["substitutions"]:
        errors.append("SUBSTITUTION")
    if operations["deletions"]:
        errors.append("DELETION")
    if operations["insertions"]:
        errors.append("INSERTION")
    return list(dict.fromkeys(errors or ["OTHER"]))


def rect(points: list[list[float]] | list[float]) -> list[float]:
    if len(points) == 4 and all(isinstance(value, (int, float)) for value in points):
        return [float(value) for value in points]
    xs = [float(point[0]) for point in points]  # type: ignore[index]
    ys = [float(point[1]) for point in points]  # type: ignore[index]
    return [min(xs), min(ys), max(xs), max(ys)]


def union_rect(boxes: list[list[list[float]] | list[float]]) -> list[float] | None:
    if not boxes:
        return None
    values = [rect(box) for box in boxes]
    return [min(box[0] for box in values), min(box[1] for box in values),
            max(box[2] for box in values), max(box[3] for box in values)]


def overlap(trusted: list[float], candidate: list[float]) -> dict[str, float]:
    tx1, ty1, tx2, ty2 = rect(trusted)
    cx1, cy1, cx2, cy2 = rect(candidate)
    intersection = max(0.0, min(tx2, cx2) - max(tx1, cx1)) * max(
        0.0, min(ty2, cy2) - max(ty1, cy1)
    )
    trusted_area = max(0.0, tx2 - tx1) * max(0.0, ty2 - ty1)
    candidate_area = max(0.0, cx2 - cx1) * max(0.0, cy2 - cy1)
    union = trusted_area + candidate_area - intersection
    return {
        "intersection_over_trusted": intersection / trusted_area if trusted_area else 0.0,
        "intersection_over_smaller_region": intersection / min(trusted_area, candidate_area)
        if trusted_area and candidate_area else 0.0,
        "iou": intersection / union if union else 0.0,
    }


def match_regions(
    trusted: list[dict[str, Any]], candidates: list[dict[str, Any]],
    threshold: float = MATCH_THRESHOLD,
) -> dict[str, Any]:
    edges: list[dict[str, Any]] = []
    trusted_to_candidates = {str(item["id"]): [] for item in trusted}
    candidate_to_trusted = {str(item["id"]): [] for item in candidates}
    for expected in trusted:
        for candidate in candidates:
            scores = overlap(expected["bbox"], candidate["bbox"])
            if scores[MATCH_METRIC] >= threshold:
                tid, cid = str(expected["id"]), str(candidate["id"])
                trusted_to_candidates[tid].append(cid)
                candidate_to_trusted[cid].append(tid)
                edges.append({"trusted_id": tid, "candidate_id": cid, **scores})
    one_to_one = [edge for edge in edges if len(trusted_to_candidates[edge["trusted_id"]]) == 1
                  and len(candidate_to_trusted[edge["candidate_id"]]) == 1]
    merges = [{"candidate_id": cid, "trusted_ids": tids}
              for cid, tids in candidate_to_trusted.items() if len(tids) > 1]
    splits = [{"trusted_id": tid, "candidate_ids": cids}
              for tid, cids in trusted_to_candidates.items() if len(cids) > 1]
    misses = [tid for tid, cids in trusted_to_candidates.items() if not cids]
    orphans = [cid for cid, tids in candidate_to_trusted.items() if not tids]
    return {
        "metric": MATCH_METRIC, "threshold": threshold, "edges": edges,
        "one_to_one_matches": one_to_one, "merged_region_errors": merges,
        "over_split_errors": splits, "missed_trusted_region_ids": misses,
        "orphan_candidate_region_ids": orphans,
        "matched_trusted_regions": len(trusted) - len(misses),
    }


def confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "unavailable"
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def assert_unchanged(before: dict[str, Any], after: dict[str, Any]) -> None:
    if stable_hash(before) != stable_hash(after):
        raise RuntimeError("Authoritative persisted benchmark state changed")


def validate_artifact(value: dict[str, Any], kind: str) -> None:
    required = {"schema_version", "checkpoint", "artifact_kind", "status"}
    missing = sorted(required - value.keys())
    if missing:
        raise ValueError(f"missing artifact fields: {', '.join(missing)}")
    if value["schema_version"] != SCHEMA_VERSION or value["checkpoint"] != "11.3":
        raise ValueError("unsupported Reader benchmark schema/checkpoint")
    if value["artifact_kind"] != kind:
        raise ValueError(f"expected artifact_kind={kind!r}")


def write_json(path: Path, value: dict[str, Any]) -> None:
    validate_artifact(value, value["artifact_kind"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
