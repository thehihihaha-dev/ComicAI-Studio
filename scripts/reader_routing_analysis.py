#!/usr/bin/env python3
"""Pure OCR routing-signal experiment for Checkpoint 11.6."""

from __future__ import annotations

import json, math, re, sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reader_benchmark_lib import edit_distance, evaluation_normalize_text  # noqa: E402

DAY11 = ROOT / "benchmarks" / "day11"
HUMAN = DAY11 / "reader-human-verified-11.6.json"
EASY = DAY11 / "reader-easyocr-verified-latest.json"
PADDLE = DAY11 / "reader-paddleocr-verified-latest.json"
SAMPLES = DAY11 / "reader-routing-samples-11.6.json"
ANALYSIS = DAY11 / "reader-routing-analysis-11.6.json"
COMPARISON = DAY11 / "reader-routing-comparison-11.6.json"
SCHEMA = "reader-routing-signals.v1"
CORRECTNESS_THRESHOLDS = (0.0, 0.05, 0.10)


def normalized_similarity(left: str, right: str) -> float:
    left, right = evaluation_normalize_text(left), evaluation_normalize_text(right)
    denominator = max(len(left), len(right))
    return 1.0 if denominator == 0 else max(0.0, 1 - edit_distance(left, right) / denominator)


def sanity_flags(text: str, other: str = "") -> list[str]:
    normalized = evaluation_normalize_text(text)
    flags = []
    if not normalized: flags.append("empty")
    if 0 < len(normalized) < 2: flags.append("suspiciously_short")
    symbols = sum(not char.isalnum() and not char.isspace() for char in normalized)
    if normalized and symbols / len(normalized) > 0.35: flags.append("unusual_symbol_ratio")
    if re.search(r"(.)\1{3,}", normalized): flags.append("repeated_character_pattern")
    if text != " ".join(text.split()): flags.append("excessive_whitespace")
    cjk = lambda value: any("CJK" in __import__("unicodedata").name(char, "") for char in value)
    if other and cjk(text) != cjk(other): flags.append("script_mismatch_between_engines")
    return flags


def language_hint(text: str) -> str:
    vietnamese = "ăâđêôơưĂÂĐÊÔƠƯàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ"
    return "vi" if any(char in vietnamese for char in text) else "unknown"


def cache_reusable(expected_key: str, result: dict[str, Any]) -> bool:
    return result.get("cache_key") == expected_key and result.get("cache_status") in {"CACHED", "reused_cached_result"}


def routing_metrics(samples: list[dict[str, Any]], accepted_ids: set[str], engine: str,
                    correctness_threshold: float) -> dict[str, Any]:
    accepted = [sample for sample in samples if sample["sample_id"] in accepted_ids]
    correct = [sample for sample in accepted if sample[engine]["normalized_cer"] <= correctness_threshold]
    all_correct = sum(sample[engine]["normalized_cer"] <= correctness_threshold for sample in samples)
    false_safe = len(accepted) - len(correct); total = len(samples)
    return {"N": total, "accepted_easy": len(accepted), "correct_easy": len(correct),
            "false_safe_count": false_safe,
            "safe_accept_rate": len(correct) / total if total else None,
            "false_safe_rate": false_safe / total if total else None,
            "hard_rate": (total - len(accepted)) / total if total else None,
            "easy_precision": len(correct) / len(accepted) if accepted else None,
            "correct_region_coverage": len(correct) / all_correct if all_correct else None}


def accept(rule: dict[str, Any], sample: dict[str, Any]) -> bool:
    kind = rule["kind"]
    if kind == "easy_confidence": return (sample["easyocr"]["confidence"] or 0) >= rule["confidence"]
    if kind == "paddle_confidence": return (sample["paddleocr"]["confidence"] or 0) >= rule["confidence"]
    if kind == "agreement": return sample["similarity"] >= rule["similarity"]
    confidence_ok = min(sample["easyocr"]["confidence"] or 0, sample["paddleocr"]["confidence"] or 0) >= rule["confidence"]
    base = sample["similarity"] >= rule["similarity"] and confidence_ok
    return base and (kind != "combined_sanity" or not sample["sanity_flags"])


def rule_grid() -> list[dict[str, Any]]:
    rules = []
    for confidence in (.6, .7, .8, .9, .95):
        rules += [{"kind": "easy_confidence", "engine": "easyocr", "confidence": confidence},
                  {"kind": "paddle_confidence", "engine": "paddleocr", "confidence": confidence}]
    for similarity in (.6, .7, .8, .9, .95, 1.0):
        rules.append({"kind": "agreement", "engine": "paddleocr", "similarity": similarity})
        for confidence in (.6, .8, .9):
            rules += [{"kind": "agreement_confidence", "engine": "paddleocr", "similarity": similarity, "confidence": confidence},
                      {"kind": "combined_sanity", "engine": "paddleocr", "similarity": similarity, "confidence": confidence}]
    return rules


def rule_id(rule: dict[str, Any]) -> str:
    return ":".join(f"{key}={rule[key]}" for key in sorted(rule))


def run() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    human, easy, paddle = [json.loads(path.read_text(encoding="utf-8")) for path in (HUMAN, EASY, PADDLE)]
    gt = {item["sample_id"]: item for item in human["samples"]}
    easy_by = {item["sample_id"]: item for item in easy["results"]}; paddle_by = {item["sample_id"]: item for item in paddle["results"]}
    samples = []
    for sample_id in sorted(gt):
        left, right = easy_by[sample_id], paddle_by[sample_id]
        similarity = normalized_similarity(left["hypothesis_raw"], right["hypothesis_raw"])
        flags = sorted(set(sanity_flags(left["hypothesis_raw"], right["hypothesis_raw"]) + sanity_flags(right["hypothesis_raw"], left["hypothesis_raw"])))
        samples.append({"sample_id": sample_id, "source_hash": gt[sample_id]["source_image_hash"],
                        "crop_hash": gt[sample_id]["crop_hash"], "bbox": gt[sample_id]["bbox"],
                        "language": language_hint(gt[sample_id]["ground_truth"]), "text_role": gt[sample_id]["text_role"],
                        "human_gt": gt[sample_id]["ground_truth"],
                        "easyocr": {"text": left["hypothesis_raw"], "confidence": left["confidence"], "raw_cer": left["raw_cer"], "normalized_cer": left["normalized_cer"], "cache_status": left["cache_status"]},
                        "paddleocr": {"text": right["hypothesis_raw"], "confidence": right["confidence"], "raw_cer": right["raw_cer"], "normalized_cer": right["normalized_cer"], "cache_status": right["cache_status"]},
                        "similarity": similarity, "normalized_exact_agreement": math.isclose(similarity, 1.0),
                        "sanity_flags": flags,
                        "correctness": {str(threshold): {"easyocr": left["normalized_cer"] <= threshold,
                                                         "paddleocr": right["normalized_cer"] <= threshold}
                                        for threshold in CORRECTNESS_THRESHOLDS}})
    evaluated = []
    for rule in rule_grid():
        accepted = {sample["sample_id"] for sample in samples if accept(rule, sample)}
        evaluated.append({"rule_id": rule_id(rule), "rule": rule,
                          "metrics": {str(threshold): routing_metrics(samples, accepted, rule["engine"], threshold)
                                      for threshold in CORRECTNESS_THRESHOLDS}})
    nonempty = [item for item in evaluated if item["metrics"]["0.0"]["accepted_easy"]]
    best = min(nonempty, key=lambda item: (item["metrics"]["0.0"]["false_safe_count"],
                                           -item["metrics"]["0.0"]["correct_easy"],
                                           -item["metrics"]["0.0"]["accepted_easy"], item["rule_id"])) if nonempty else None
    loo = []
    if best:
        for omitted in samples:
            subset = [sample for sample in samples if sample is not omitted]
            accepted = {sample["sample_id"] for sample in subset if accept(best["rule"], sample)}
            loo.append({"omitted_sample_id": omitted["sample_id"],
                        **routing_metrics(subset, accepted, best["rule"]["engine"], 0.0)})
    high_agreement = [sample for sample in samples if sample["similarity"] >= .9]
    outcomes = Counter()
    for sample in samples:
        ec = sample["easyocr"]["normalized_cer"] == 0; pc = sample["paddleocr"]["normalized_cer"] == 0
        outcomes["both_correct" if ec and pc else "easyocr_wins" if ec else "paddleocr_wins" if pc else "both_wrong"] += 1
    samples_artifact = {"schema_version": SCHEMA, "checkpoint": "11.6", "artifact_kind": "samples", "status": "completed", "N": len(samples), "samples": samples,
                        "input_equality": "same human-verified source/crop identity; adapter preprocessing recorded in engine artifacts", "vlm_calls": 0}
    analysis = {"schema_version": SCHEMA, "checkpoint": "11.6", "artifact_kind": "analysis", "status": "completed", "N": len(samples),
                "correctness_classes": ["CER==0", "CER<=0.05", "CER<=0.10"], "threshold_label": "BENCHMARK-FITTED",
                "engine_outcomes_exact": dict(outcomes),
                "agreement": {"mean_similarity": sum(s["similarity"] for s in samples) / len(samples),
                              "exact_agreement": sum(s["normalized_exact_agreement"] for s in samples),
                              "high_agreement_N": len(high_agreement),
                              "high_agreement_both_wrong": sum(s["easyocr"]["normalized_cer"] > 0 and s["paddleocr"]["normalized_cer"] > 0 for s in high_agreement)},
                "false_confidence": {engine: [{"sample_id": s["sample_id"], "confidence": s[engine]["confidence"], "cer": s[engine]["normalized_cer"]}
                                              for s in samples if (s[engine]["confidence"] or 0) >= .9 and s[engine]["normalized_cer"] > 0]
                                     for engine in ("easyocr", "paddleocr")},
                "sanity_flag_counts": dict(Counter(flag for sample in samples for flag in sample["sanity_flags"])),
                "routers": evaluated, "best_observed": best, "leave_one_out": loo,
                "stability": {"max_false_safe_rate": max((x["false_safe_rate"] for x in loo), default=None),
                              "accepted_easy_range": [min((x["accepted_easy"] for x in loo), default=0), max((x["accepted_easy"] for x in loo), default=0)]},
                "warning": "N=20 and all thresholds are benchmark-fitted, not production-calibrated.", "vlm_calls": 0}
    easy_time, paddle_time = easy["performance"]["warm_region_total_seconds"], paddle["performance"]["warm_region_total_seconds"]
    per_page_easy, per_page_dual = easy_time / 3, (easy_time + paddle_time) / 3
    comparison = {"schema_version": SCHEMA, "checkpoint": "11.6", "artifact_kind": "comparison", "status": "completed", "N": len(samples),
                  "accuracy": {"easyocr": easy["aggregate"], "paddleocr": paddle["aggregate"]},
                  "performance": {"easyocr": easy["performance"], "paddleocr": paddle["performance"],
                                  "dual_sequential_warm_seconds": easy_time + paddle_time,
                                  "dual_vs_easy_multiplier": (easy_time + paddle_time) / easy_time,
                                  "projections_ocr_only_seconds": {str(pages): {"easyocr": per_page_easy * pages, "dual_sequential": per_page_dual * pages} for pages in (5, 10, 20, 50)}},
                  "resources": {"easyocr": easy["resources"], "paddleocr": paddle["resources"]},
                  "architecture_decision": "D. NO SAFE ROUTER YET",
                  "decision_reason": "Line-recognizer quality on logical-region crops is too low; benchmark-fitted routing cannot justify production safety.",
                  "structural_limitation": "Routing cannot recover undetected or incorrectly merged/split bubbles; 11.6 does not evaluate panel/bubble structure.",
                  "vlm_calls": 0}
    for path, artifact in ((SAMPLES, samples_artifact), (ANALYSIS, analysis), (COMPARISON, comparison)):
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return samples_artifact, analysis, comparison


if __name__ == "__main__":
    _, analysis, comparison = run(); print(json.dumps({"N": analysis["N"], "decision": comparison["architecture_decision"]}))
