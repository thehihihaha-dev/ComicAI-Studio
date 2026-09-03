"""Pure geometry evaluation for frozen panel predictions against Human GT."""
from __future__ import annotations

from functools import lru_cache
from typing import Any


def bbox_iou(first: list[float], second: list[float]) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if intersection == 0:
        return 0.0
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    return intersection / (first_area + second_area - intersection)


def overlap_fraction(subject: list[float], other: list[float]) -> float:
    """Fraction of subject covered by other."""
    x1, y1 = max(subject[0], other[0]), max(subject[1], other[1])
    x2, y2 = min(subject[2], other[2]), min(subject[3], other[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area = (subject[2] - subject[0]) * (subject[3] - subject[1])
    return intersection / area if area > 0 else 0.0


def one_to_one_matches(predictions: list[dict[str, Any]], truths: list[dict[str, Any]],
                       threshold: float) -> list[dict[str, Any]]:
    """Maximize eligible match count, then total IoU, with stable ID tie-breaking."""
    ordered_predictions = sorted(predictions, key=lambda item: item["panel_id"])
    ordered_truths = sorted(truths, key=lambda item: item["panel_id"])
    matrix = [[bbox_iou(prediction["bbox"], truth["bbox"]) for truth in ordered_truths]
              for prediction in ordered_predictions]

    @lru_cache(maxsize=None)
    def solve(index: int, used: int) -> tuple[int, float, tuple[tuple[int, int], ...]]:
        if index == len(ordered_predictions):
            return 0, 0.0, ()
        best = solve(index + 1, used)
        for truth_index, score in enumerate(matrix[index]):
            if score < threshold or used & (1 << truth_index):
                continue
            count, total, pairs = solve(index + 1, used | (1 << truth_index))
            candidate = count + 1, total + score, ((index, truth_index),) + pairs
            if (candidate[0], round(candidate[1], 12)) > (best[0], round(best[1], 12)):
                best = candidate
            elif (candidate[0], round(candidate[1], 12)) == (best[0], round(best[1], 12)) \
                    and candidate[2] < best[2]:
                best = candidate
        return best

    pairs = solve(0, 0)[2]
    return [{"prediction_id": ordered_predictions[prediction_index]["panel_id"],
             "human_panel_id": ordered_truths[truth_index]["panel_id"],
             "iou": round(matrix[prediction_index][truth_index], 6)}
            for prediction_index, truth_index in pairs]


def split_relations(predictions: list[dict[str, Any]], truths: list[dict[str, Any]],
                    coverage_threshold: float) -> dict[str, list[dict[str, Any]]]:
    under, over = [], []
    for prediction in sorted(predictions, key=lambda item: item["panel_id"]):
        covered = sorted(truth["panel_id"] for truth in truths
                         if overlap_fraction(truth["bbox"], prediction["bbox"]) >= coverage_threshold)
        if len(covered) >= 2:
            under.append({"prediction_id": prediction["panel_id"], "human_panel_ids": covered})
    for truth in sorted(truths, key=lambda item: item["panel_id"]):
        fragments = sorted(prediction["panel_id"] for prediction in predictions
                           if overlap_fraction(prediction["bbox"], truth["bbox"]) >= coverage_threshold)
        if len(fragments) >= 2:
            over.append({"human_panel_id": truth["panel_id"], "prediction_ids": fragments})
    return {"under_splitting": under, "over_splitting": over}


def evaluate_page(prediction_page: dict[str, Any], truths: list[dict[str, Any]],
                  match_threshold: float = 0.5, relation_threshold: float = 0.5) -> dict[str, Any]:
    detected = [panel for panel in prediction_page["panels"] if panel["state"] == "DETECTED"]
    ambiguous = [panel for panel in prediction_page["panels"] if panel["state"] == "AMBIGUOUS"]
    detected_matches = one_to_one_matches(detected, truths, match_threshold)
    ambiguous_matches = one_to_one_matches(ambiguous, truths, match_threshold)
    all_relations = split_relations(detected + ambiguous, truths, relation_threshold)
    under_split_ids = {item["prediction_id"] for item in all_relations["under_splitting"]}
    ambiguous_matches = [{**match, "structurally_clean": match["prediction_id"] not in under_split_ids}
                         for match in ambiguous_matches]
    detected_ids = {match["prediction_id"] for match in detected_matches}
    detected_truth_ids = {match["human_panel_id"] for match in detected_matches}
    ambiguous_ids = {match["prediction_id"] for match in ambiguous_matches}
    ambiguous_truth_ids = {match["human_panel_id"] for match in ambiguous_matches}

    def partials(items: list[dict[str, Any]], matched_ids: set[str]) -> list[dict[str, Any]]:
        result = []
        for item in sorted(items, key=lambda value: value["panel_id"]):
            if item["panel_id"] in matched_ids:
                continue
            scores = [(truth["panel_id"], bbox_iou(item["bbox"], truth["bbox"])) for truth in truths]
            truth_id, score = max(scores, key=lambda value: (value[1], value[0]))
            if score > 0:
                result.append({"prediction_id": item["panel_id"], "best_human_panel_id": truth_id,
                               "best_iou": round(score, 6)})
        return result

    clean_ambiguous_truth_ids = {match["human_panel_id"] for match in ambiguous_matches
                                 if match["structurally_clean"]}
    return {
        "page_order": prediction_page["page_order"], "human_panel_count": len(truths),
        "predicted_detected_count": len(detected), "predicted_ambiguous_count": len(ambiguous),
        "detected_matches": detected_matches, "ambiguous_matches": ambiguous_matches,
        "matched_true_panels_detected": len(detected_truth_ids),
        "human_panels_recoverable_in_ambiguous": len(ambiguous_truth_ids - detected_truth_ids),
        "human_panels_with_structurally_clean_ambiguous_candidate": len(clean_ambiguous_truth_ids - detected_truth_ids),
        "missed_by_all_candidates": sorted(truth["panel_id"] for truth in truths
                                            if truth["panel_id"] not in detected_truth_ids | ambiguous_truth_ids),
        "missed_by_detected_and_structurally_clean_ambiguous": sorted(
            truth["panel_id"] for truth in truths
            if truth["panel_id"] not in detected_truth_ids | clean_ambiguous_truth_ids),
        "false_detected_panel_ids": sorted(panel["panel_id"] for panel in detected
                                           if panel["panel_id"] not in detected_ids),
        "unmatched_ambiguous_panel_ids": sorted(panel["panel_id"] for panel in ambiguous
                                                 if panel["panel_id"] not in ambiguous_ids),
        "partial_detected": partials(detected, detected_ids),
        "partial_ambiguous": partials(ambiguous, ambiguous_ids),
        **all_relations, "unresolved": prediction_page["unresolved"],
    }
