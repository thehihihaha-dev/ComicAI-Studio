import json
import re
import tempfile
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image

from app.services.ollama_text import call_text_model
from app.services.ollama_vision import call_vision_model
from app.services.performance import model_call_context, timed_stage
from app.services.model_runtime import generation_option_overrides


SUSPICIOUS_OCR = re.compile(r"[#<>_|\\]|\d(?=[A-Za-zÀ-ỹ])|(?<=[A-Za-zÀ-ỹ])\d")
DIALOGUE_NUM_PREDICT = 512
REASON_CODES = {
    "unchanged", "ocr_typo", "low_confidence", "ambiguous_visual",
    "proper_name_uncertain", "fragmented_ocr", "needs_review",
}
REVIEW_REASON_CODES = {
    "low_confidence", "ambiguous_visual", "proper_name_uncertain",
    "fragmented_ocr", "needs_review",
}
RECOVERED_REGION_SOURCES = {"local_ocr_recovery", "vision_ocr_recovery"}


def parse_compact_corrections(
    originals: list[dict[str, Any]], response: dict[str, Any]
) -> list[dict[str, Any]]:
    items = response.get("items")
    if not isinstance(items, list):
        raise ValueError("Compact correction response must contain items.")
    original_map = {item["region_id"]: item for item in originals}
    seen = set()
    results = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Compact correction item must be an object.")
        region_id = item.get("region_id")
        if region_id not in original_map or region_id in seen:
            raise ValueError("Compact correction has unknown or duplicate region_id.")
        seen.add(region_id)
        action = item.get("action")
        decision = item.get("decision")
        reason_code = item.get("reason_code")
        confidence = item.get("confidence")
        if action not in {"unchanged", "changed"} or decision not in {"accept", "review"}:
            raise ValueError("Compact correction action/decision is invalid.")
        if reason_code not in REASON_CODES:
            raise ValueError("Compact correction reason_code is not allowlisted.")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
            raise ValueError("Compact correction confidence is invalid.")
        raw_text = original_map[region_id]["raw_text"]
        clean_text = raw_text if action == "unchanged" else item.get("clean_text")
        if not isinstance(clean_text, str) or not clean_text.strip():
            raise ValueError("Changed compact correction requires clean_text.")
        original = original_map[region_id]
        results.append({
            **original,
            "clean_text": clean_text.strip(),
            "confidence": float(confidence),
            "needs_review": decision == "review" or reason_code in REVIEW_REASON_CODES,
            "reason_code": reason_code,
            "reason": reason_code,
        })
    if seen != set(original_map):
        raise ValueError("Compact correction omitted a region_id.")
    return results


def _safe_review_corrections(originals: list[dict[str, Any]], reason_code: str) -> list[dict[str, Any]]:
    return [{**item, "clean_text": item["raw_text"], "confidence": 0.0, "needs_review": True, "reason_code": reason_code, "reason": reason_code} for item in originals]


def screen_dialogues(
    dialogues: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
    verified_text_by_region: dict[int, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted = []
    uncertain = []
    verified = verified_text_by_region or {}
    for dialogue in dialogues:
        region_id = dialogue.get("region_id")
        if isinstance(verified.get(region_id), str) and verified[region_id].strip():
            text = verified[region_id].strip()
            accepted.append({**dialogue, "clean_text": text, "verified_text": text, "confidence": 1.0, "needs_review": False, "decision": "verified", "human_verified": True, "correction_path": "ground_truth"})
            continue
        confidences = [
            float(ocr_blocks[index].get("confidence", 0.0))
            for index in dialogue.get("block_ids", [])
            if isinstance(index, int) and 0 <= index < len(ocr_blocks)
        ]
        raw_text = dialogue.get("raw_text", "")
        clean = (
            bool(confidences)
            and min(confidences) >= 0.92
            and len(raw_text.strip()) >= 2
            and not SUSPICIOUS_OCR.search(raw_text)
            and raw_text.count('"') % 2 == 0
        )
        if clean:
            accepted.append({**dialogue, "clean_text": raw_text, "confidence": min(confidences), "needs_review": False, "reason": "Deterministic high-confidence unchanged OCR fast path.", "correction_path": "fast_path"})
        else:
            uncertain.append(dialogue)
    return accepted, uncertain


def _normalize_corrections(
    originals: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidate_map = {item.get("region_id"): item for item in candidates if isinstance(item, dict)}
    return [
        {
            **candidate_map.get(item["region_id"], {}),
            "order": item["order"],
            "region_id": item["region_id"],
            "raw_text": item["raw_text"],
        }
        for item in originals
        if item["region_id"] in candidate_map
    ]


def correct_dialogues_text_first(dialogues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt = f"""Correct OCR errors in ONLY these comic dialogues. Preserve language, names,
meaning, order, region_id and raw_text. Do not invent. Set needs_visual=true for
proper-name ambiguity, visually ambiguous characters, or uncertain reconstruction.
Return JSON {{\"dialogues\":[{{\"order\":1,\"region_id\":1,\"raw_text\":\"...\",\"clean_text\":\"...\",\"confidence\":0.0,\"needs_review\":true,\"needs_visual\":true,\"reason\":\"...\"}}]}}.
INPUT:
{json.dumps(dialogues, ensure_ascii=False, indent=2)}"""
    with model_call_context("dialogue_correction_text"):
        result = call_text_model(prompt)
    candidates = result.get("dialogues", [])
    return _normalize_corrections(dialogues, candidates if isinstance(candidates, list) else [])


def _combined_dialogue_crop(
    image_path: str, dialogues: list[dict[str, Any]], ocr_blocks: list[dict[str, Any]]
) -> str | None:
    crops = []
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        for dialogue in dialogues:
            points = [
                point
                for index in dialogue.get("block_ids", [])
                if isinstance(index, int) and 0 <= index < len(ocr_blocks)
                for point in ocr_blocks[index].get("box", [])
                if isinstance(point, list) and len(point) == 2
            ]
            if not points:
                continue
            margin = 32
            left = max(0, min(point[0] for point in points) - margin)
            top = max(0, min(point[1] for point in points) - margin)
            right = min(image.width, max(point[0] for point in points) + margin)
            bottom = min(image.height, max(point[1] for point in points) + margin)
            if right > left and bottom > top:
                crops.append(image.crop((left, top, right, bottom)))
        if not crops:
            return None
        width = max(crop.width for crop in crops)
        height = sum(crop.height for crop in crops) + 8 * (len(crops) - 1)
        montage = Image.new("RGB", (width, height), "white")
        y = 0
        for crop in crops:
            montage.paste(crop, (0, y))
            y += crop.height + 8
        handle = tempfile.NamedTemporaryFile(prefix="comicai-dialogue-", suffix=".jpg", delete=False)
        handle.close()
        montage.save(handle.name, format="JPEG", quality=95)
        return handle.name


@timed_stage("dialogue_correction")
def correct_dialogues(
    image_path: str,
    dialogues: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]] | None = None,
    verified_text_by_region: dict[int, str] | None = None,
) -> list[dict[str, Any]]:

    if ocr_blocks is not None:
        accepted, uncertain = screen_dialogues(dialogues, ocr_blocks, verified_text_by_region)
        if not uncertain:
            return sorted(accepted, key=lambda item: item["order"])
        visual_result = _correct_dialogues_vision(image_path, uncertain, None)
        return sorted([*accepted, *visual_result], key=lambda item: item["order"])

    return _correct_dialogues_vision(image_path, dialogues, None)


def _correct_dialogues_vision(
    image_path: str,
    dialogues: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:

    dialogue_json = json.dumps(
        [{"region_id": item["region_id"], "text": item["raw_text"]} for item in dialogues],
        ensure_ascii=False,
        separators=(",", ":"),
    )

    prompt = f"""
You are correcting OCR errors from a comic page.

Correct OCR using the image. Preserve language, names and meaning. Never
translate, summarize or invent. Return every supplied region_id exactly once.
Use action "unchanged" and omit clean_text when input is already correct.
Use action "changed" and include clean_text only when correction is needed.
decision is "review" whenever evidence is uncertain. confidence is 0..1.
reason_code must be one of: {sorted(REASON_CODES)}. No prose explanations.

INPUT:{dialogue_json}

Return only compact JSON:
{{"items":[{{"region_id":1,"action":"unchanged|changed","clean_text":"only if changed","confidence":0.95,"decision":"accept|review","reason_code":"ocr_typo"}}]}}
"""

    crop_path = _combined_dialogue_crop(image_path, dialogues, ocr_blocks) if ocr_blocks is not None else None
    try:
        with generation_option_overrides({"num_predict": DIALOGUE_NUM_PREDICT}):
            with model_call_context("dialogue_correction"):
                result = call_vision_model(image_path=crop_path or image_path, prompt=prompt, json_mode=True)
        try:
            normalized = parse_compact_corrections(dialogues, result)
        except ValueError:
            normalized = _safe_review_corrections(dialogues, "needs_review")
        if validate_corrected_dialogues(dialogues, normalized)["is_valid"]:
            path = "vision_crop" if crop_path else "vision_full_page"
            return [{**item, "correction_path": path} for item in normalized]
        if crop_path:
            with model_call_context("dialogue_correction_full_fallback"):
                fallback = call_vision_model(image_path=image_path, prompt=prompt, json_mode=True)
            try:
                return parse_compact_corrections(dialogues, fallback)
            except ValueError:
                return _safe_review_corrections(dialogues, "needs_review")
        return normalized
    except Exception:
        if not crop_path:
            raise
        with model_call_context("dialogue_correction_full_fallback"):
            fallback = call_vision_model(image_path=image_path, prompt=prompt, json_mode=True)
        try:
            return parse_compact_corrections(dialogues, fallback)
        except ValueError:
            return _safe_review_corrections(dialogues, "needs_review")
    finally:
        if crop_path:
            Path(crop_path).unlink(missing_ok=True)
def validate_corrected_dialogues(
    original_dialogues: list[dict[str, Any]],
    corrected_dialogues: list[dict[str, Any]],
) -> dict[str, Any]:

    original_map = {
        dialogue["region_id"]: dialogue
        for dialogue in original_dialogues
    }

    corrected_region_ids = [
        dialogue.get("region_id")
        for dialogue in corrected_dialogues
    ]
    duplicate_region_ids = sorted(
        region_id
        for region_id, count in Counter(corrected_region_ids).items()
        if count > 1 and region_id is not None
    )

    corrected_map = {
        dialogue.get("region_id"): dialogue
        for dialogue in corrected_dialogues
    }

    missing_region_ids = []
    invalid_region_ids = []
    order_mismatches = []
    raw_text_mismatches = []
    empty_clean_text = []
    invalid_confidence_region_ids = []

    # Region mà AI tự bịa thêm
    for region_id in corrected_map:
        if region_id not in original_map:
            invalid_region_ids.append(region_id)

    # Kiểm tra từng dialogue gốc
    for region_id, original in original_map.items():
        corrected = corrected_map.get(region_id)

        if corrected is None:
            missing_region_ids.append(region_id)
            continue

        if corrected.get("order") != original.get("order"):
            order_mismatches.append(
                {
                    "region_id": region_id,
                    "expected": original.get("order"),
                    "actual": corrected.get("order"),
                }
            )

        if corrected.get("raw_text") != original.get("raw_text"):
            raw_text_mismatches.append(region_id)

        clean_text = corrected.get("clean_text", "")

        if not isinstance(clean_text, str) or not clean_text.strip():
            empty_clean_text.append(region_id)

        confidence = corrected.get("confidence")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0.0 <= float(confidence) <= 1.0
        ):
            invalid_confidence_region_ids.append(region_id)

    is_valid = (
        len(corrected_dialogues) == len(original_dialogues)
        and not missing_region_ids
        and not invalid_region_ids
        and not duplicate_region_ids
        and not order_mismatches
        and not raw_text_mismatches
        and not empty_clean_text
        and not invalid_confidence_region_ids
    )

    return {
        "is_valid": is_valid,
        "total_original": len(original_dialogues),
        "total_corrected": len(corrected_dialogues),
        "missing_region_ids": missing_region_ids,
        "invalid_region_ids": invalid_region_ids,
        "duplicate_region_ids": duplicate_region_ids,
        "order_mismatches": order_mismatches,
        "raw_text_mismatches": raw_text_mismatches,
        "empty_clean_text": empty_clean_text,
        "invalid_confidence_region_ids": invalid_confidence_region_ids,
    }
def evaluate_correction_safety(
    corrected_dialogues: list[dict[str, Any]],
    review_threshold: float = 0.90,
) -> dict[str, Any]:

    review_region_ids = []
    review_items = []

    for dialogue in corrected_dialogues:
        region_id = dialogue.get("region_id")
        confidence = dialogue.get("confidence", 0.0)
        model_needs_review = dialogue.get(
            "needs_review",
            False,
        )

        should_review = (
            model_needs_review is True
            or confidence < review_threshold
        )

        if should_review:
            review_region_ids.append(region_id)

            review_items.append(
                {
                    "region_id": region_id,
                    "confidence": confidence,
                    "reason": dialogue.get(
                        "reason",
                        "",
                    ),
                }
            )

    return {
        "safe": len(review_region_ids) == 0,
        "review_region_ids": review_region_ids,
        "review_count": len(review_region_ids),
        "review_items": review_items,
    }
def calculate_correction_score(
    original_dialogues: list[dict[str, Any]],
    corrected_dialogues: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    corrected_map = {
        dialogue["region_id"]: dialogue
        for dialogue in corrected_dialogues
    }

    results = []

    for original in original_dialogues:
        region_id = original["region_id"]
        corrected = corrected_map.get(region_id)

        if not corrected:
            continue

        block_ids = original.get("block_ids", [])

        block_confidences = [
            float(ocr_blocks[block_id].get("confidence", 0.0))
            for block_id in block_ids
            if 0 <= block_id < len(ocr_blocks)
        ]

        avg_ocr_confidence = (
            sum(block_confidences) / len(block_confidences)
            if block_confidences
            else 0.0
        )

        raw_text = original.get("raw_text", "")
        clean_text = corrected.get("clean_text", "")

        similarity = SequenceMatcher(
            None,
            raw_text.lower(),
            clean_text.lower(),
        ).ratio()

        model_needs_review = corrected.get(
            "needs_review",
            False,
        )

        model_confidence = float(
            corrected.get("confidence", 0.0)
        )

        score = (
            avg_ocr_confidence * 0.45
            + similarity * 0.35
            + model_confidence * 0.20
        )

        if model_needs_review:
            score -= 0.15

        score = max(
            0.0,
            min(1.0, score),
        )

        results.append(
            {
                **corrected,
                "ocr_confidence": round(
                    avg_ocr_confidence,
                    3,
                ),
                "text_similarity": round(
                    similarity,
                    3,
                ),
                "correction_score": round(
                    score,
                    3,
                ),
                "needs_review": (
                    model_needs_review
                    or score < 0.75
                ),
            }
        )

    return results
def has_risky_text_change(
    raw_text: str,
    clean_text: str,
) -> bool:
    raw_words = raw_text.upper().split()
    clean_words = clean_text.upper().split()

    if raw_words == clean_words:
        return False

    # Nếu số từ thay đổi thì coi là đáng kiểm tra hơn
    if len(raw_words) != len(clean_words):
        return True

    changed_words = 0

    for raw_word, clean_word in zip(
        raw_words,
        clean_words,
    ):
        if raw_word != clean_word:
            changed_words += 1

    # Một câu rất ngắn mà AI đổi từ
    # thì không nên auto-accept quá dễ dàng.
    if len(raw_words) <= 12 and changed_words >= 1:
        return True

    # Câu dài: nếu AI thay nhiều từ thì recovery
    if changed_words >= 2:
        return True

    return False


def is_safe_tiny_ocr_typo(dialogue: dict[str, Any]) -> bool:
    raw_text = dialogue.get("raw_text", "")
    clean_text = dialogue.get("clean_text", "")
    reason_code = dialogue.get("reason_code")
    similarity = float(dialogue.get("text_similarity", 0.0))
    ocr_confidence = float(dialogue.get("ocr_confidence", 0.0))
    correction_confidence = float(dialogue.get("confidence", 0.0))
    if reason_code not in {"ocr_typo", "unchanged"}:
        return False
    if similarity < 0.96 or ocr_confidence < 0.60 or correction_confidence < 0.97:
        return False
    if len(raw_text.split()) != len(clean_text.split()):
        return False
    raw_names = {value.strip().upper() for value in re.findall(r'"([^"\n]+)"', raw_text)}
    clean_names = {value.strip().upper() for value in re.findall(r'"([^"\n]+)"', clean_text)}
    return raw_names <= clean_names


def correction_recovery_agree(
    dialogue: dict[str, Any], recovery: dict[str, Any] | None
) -> bool:
    if not isinstance(recovery, dict):
        return False
    recovered_text = recovery.get("recovered_text")
    if not isinstance(recovered_text, str) or recovered_text.strip() != dialogue.get("clean_text", "").strip():
        return False
    correction_reason = dialogue.get("reason_code")
    recovery_reason = recovery.get("reason_code")
    if correction_reason in {"proper_name_uncertain", "ambiguous_visual", "needs_review"}:
        return False
    if recovery_reason in {"proper_name_uncertain", "ambiguous_visual", "needs_review"}:
        return False
    correction_confidence = float(dialogue.get("confidence", 0.0))
    recovery_confidence = float(recovery.get("confidence", 0.0))
    similarity = float(dialogue.get("text_similarity", 0.0))
    ocr_confidence = float(dialogue.get("ocr_confidence", 0.0))
    if correction_reason == "fragmented_ocr" or recovery_reason == "fragmented_ocr":
        return (
            correction_confidence >= 0.98
            and recovery_confidence >= 0.98
            and similarity >= 0.97
            and ocr_confidence >= 0.80
        )
    return (
        correction_confidence >= 0.95
        and recovery_confidence >= 0.95
        and similarity >= 0.94
        and ocr_confidence >= 0.60
    )
def decide_dialogue_action(
    dialogue: dict[str, Any],
) -> dict[str, Any]:
    score = float(
        dialogue.get("correction_score", 0.0)
    )

    ocr_confidence = float(
        dialogue.get("ocr_confidence", 0.0)
    )

    model_needs_review = dialogue.get(
        "needs_review",
        False,
    )

    raw_text = dialogue.get(
        "raw_text",
        "",
    )

    clean_text = dialogue.get(
        "clean_text",
        "",
    )

    risky_change = has_risky_text_change(
        raw_text,
        clean_text,
    )

    if is_safe_tiny_ocr_typo(dialogue):
        decision = "auto_accepted"
        calibration_rule = "tiny_ocr_typo"

    elif (
        score >= 0.90
        and not model_needs_review
        and not risky_change
    ):
        decision = "auto_accepted"
        calibration_rule = None

    elif (
        score >= 0.75
        and ocr_confidence >= 0.65
        and not model_needs_review
        and not risky_change
    ):
        decision = "auto_accepted"
        calibration_rule = None

    else:
        decision = "needs_recovery"
        calibration_rule = None

    return {
        **dialogue,
        "risky_text_change": risky_change,
        "decision": decision,
        "calibration_rule": calibration_rule,
    }


def apply_dialogue_decisions(
    dialogues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        decide_dialogue_action(dialogue)
        for dialogue in dialogues
    ]


def _process_dialogue_batch(
    image_path: str,
    dialogues: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
    verified_text_by_region: dict[int, str],
) -> list[dict[str, Any]]:
    if not dialogues:
        return []
    corrected = correct_dialogues(
        image_path,
        dialogues,
        ocr_blocks,
        verified_text_by_region,
    )
    validation = validate_corrected_dialogues(dialogues, corrected)
    if not validation["is_valid"]:
        raise ValueError(f"Invalid corrected dialogue batch: {validation}")
    scored = calculate_correction_score(dialogues, corrected, ocr_blocks)
    decided = apply_dialogue_decisions(scored)
    return recover_uncertain_dialogues(
        image_path=image_path,
        dialogues=decided,
        ocr_blocks=ocr_blocks,
    )


def process_dialogue_batches(
    image_path: str,
    dialogues: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    verified_text_by_region: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """Keep uncertain OCR-empty evidence out of the trusted page batch."""
    recovered_ids = {
        region.get("id")
        for region in regions
        if region.get("region_source") in RECOVERED_REGION_SOURCES
    }
    normal = [item for item in dialogues if item.get("region_id") not in recovered_ids]
    recovered = [item for item in dialogues if item.get("region_id") in recovered_ids]
    verified = verified_text_by_region or {}
    normal_result = (
        _process_dialogue_batch(image_path, normal, ocr_blocks, verified)
        if normal
        else []
    )
    recovered_result = (
        _process_dialogue_batch(image_path, recovered, ocr_blocks, verified)
        if recovered
        else []
    )
    result_by_id = {
        item["region_id"]: item
        for item in [*normal_result, *recovered_result]
    }
    if set(result_by_id) != {item["region_id"] for item in dialogues}:
        raise ValueError("Dialogue batch merge lost or invented region IDs.")
    return [
        {**result_by_id[item["region_id"]], "order": item["order"]}
        for item in dialogues
    ]


def apply_verified_ground_truth(
    dialogues: list[dict[str, Any]],
    verified_text_by_region: dict[int, str],
) -> list[dict[str, Any]]:
    results = []

    for dialogue in dialogues:
        region_id = dialogue.get("region_id")
        verified_text = verified_text_by_region.get(region_id)

        if not isinstance(verified_text, str) or not verified_text.strip():
            results.append(dialogue)
            continue

        final_text = verified_text.strip()
        results.append(
            {
                **dialogue,
                "pre_verification_text": dialogue.get("clean_text", ""),
                "clean_text": final_text,
                "verified_text": final_text,
                "human_verified": True,
                "needs_review": False,
                "decision": "verified",
            }
        )

    return results


def recover_dialogue(
    image_path: str,
    dialogue: dict[str, Any],
    previous_dialogue: dict[str, Any] | None = None,
    next_dialogue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = {
        "current": dialogue,
        "previous": previous_dialogue,
        "next": next_dialogue,
    }

    context_json = json.dumps(
        context,
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
You are performing a second-pass OCR recovery
for a comic dialogue.

The first pass was uncertain.

CONTEXT:

{context_json}

Your task:
- Look carefully at the original comic image.
- Re-check ONLY the current dialogue.
- Use surrounding dialogue context when helpful.
- Preserve names and meaning.
- Do NOT translate.
- Do NOT summarize.
- Do NOT invent text.
- Return a better correction only if supported by the image/context.
- If still uncertain, say so.

Return ONLY valid JSON:

{{
  "region_id": {dialogue["region_id"]},
  "recovered_text": "corrected text",
  "confidence": 0.0,
  "still_uncertain": true,
  "reason": "explanation"
}}
"""

    result = call_vision_model(
        image_path=image_path,
        prompt=prompt,
    )

    return result


def recover_dialogues_batch(
    image_path: str,
    dialogues: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    uncertain = [
        {
            "region_id": dialogue.get("region_id"),
            "raw": dialogue.get("raw_text", ""),
            "candidate": dialogue.get("clean_text", ""),
        }
        for dialogue in dialogues
        if dialogue.get("decision") == "needs_recovery"
    ]
    if not uncertain:
        return []
    prompt = f"""
You are performing a second-pass OCR recovery for multiple uncertain dialogue
regions on one comic page.

Re-check only these unresolved comic OCR candidates against the image. Preserve
language, names and meaning. Never invent. Return every region_id once. Use
action "unchanged" and omit clean_text when candidate is correct; otherwise use
"changed" with clean_text. decision is "review" whenever uncertain. reason_code
must be one of {sorted(REASON_CODES)}. No prose.
INPUT:{json.dumps(uncertain, ensure_ascii=False, separators=(",", ":"))}
Return only JSON:
{{"items":[{{"region_id":1,"action":"unchanged|changed","clean_text":"only if changed","confidence":0.95,"decision":"accept|review","reason_code":"ocr_typo"}}]}}
"""
    # The V1 crop experiment was slower for dispersed regions; retain the
    # minimal unresolved-only prompt while using reliable full-page evidence.
    crop_path = None
    try:
        with generation_option_overrides({"num_predict": DIALOGUE_NUM_PREDICT}):
            result = call_vision_model(image_path=crop_path or image_path, prompt=prompt, json_mode=True)
    except Exception:
        if not crop_path:
            raise
        with generation_option_overrides({"num_predict": DIALOGUE_NUM_PREDICT}):
            result = call_vision_model(image_path=image_path, prompt=prompt, json_mode=True)
    finally:
        if crop_path:
            Path(crop_path).unlink(missing_ok=True)
    original_by_id = {
        item["region_id"]: {
            "order": index,
            "region_id": item["region_id"],
            "raw_text": item["candidate"],
        }
        for index, item in enumerate(uncertain, start=1)
    }
    try:
        compact = parse_compact_corrections(list(original_by_id.values()), result)
    except ValueError:
        return []
    return [
        {
            "region_id": item["region_id"],
            "recovered_text": item["clean_text"],
            "confidence": item["confidence"],
            "still_uncertain": item["needs_review"],
            "reason_code": item["reason_code"],
        }
        for item in compact
    ]


def _apply_recovery_item(
    dialogue: dict[str, Any],
    recovery: dict[str, Any] | None,
) -> dict[str, Any]:
    valid_item = isinstance(recovery, dict) and recovery.get("region_id") == dialogue.get("region_id")
    recovered_text = recovery.get("recovered_text") if valid_item else None
    try:
        confidence = float(recovery.get("confidence", 0.0)) if valid_item else 0.0
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    agreement = correction_recovery_agree(dialogue, recovery)
    still_uncertain = not valid_item or (recovery.get("still_uncertain") is not False and not agreement)
    effective_text = (
        recovered_text.strip()
        if isinstance(recovered_text, str) and recovered_text.strip()
        else dialogue.get("clean_text", "")
    )
    return {
        **dialogue,
        "initial_clean_text": dialogue.get("clean_text", ""),
        "clean_text": effective_text,
        "recovered_text": effective_text,
        "recovery_confidence": confidence,
        "recovery_reason": recovery.get("reason_code", "needs_review") if valid_item else "needs_review",
        "recovery_reason_code": recovery.get("reason_code", "needs_review") if valid_item else "needs_review",
        "agreement_evidence": agreement,
        "decision": "auto_recovered" if confidence >= 0.90 and not still_uncertain else "needs_review",
    }


@timed_stage("dialogue_recovery")
def recover_uncertain_dialogues(
    image_path: str,
    dialogues: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    recoveries = (
        recover_dialogues_batch(image_path, dialogues, ocr_blocks)
        if ocr_blocks is not None
        else recover_dialogues_batch(image_path, dialogues)
    )
    valid_region_ids = {
        dialogue.get("region_id")
        for dialogue in dialogues
        if dialogue.get("decision") == "needs_recovery"
    }
    recovery_map: dict[Any, dict[str, Any]] = {}
    duplicate_ids: set[Any] = set()
    for item in recoveries:
        if not isinstance(item, dict) or item.get("region_id") not in valid_region_ids:
            continue
        region_id = item["region_id"]
        if region_id in recovery_map:
            duplicate_ids.add(region_id)
            continue
        recovery_map[region_id] = item

    results = []
    for dialogue in dialogues:
        if dialogue.get("decision") != "needs_recovery":
            results.append(dialogue)
            continue
        region_id = dialogue.get("region_id")
        recovery = None if region_id in duplicate_ids else recovery_map.get(region_id)
        results.append(_apply_recovery_item(dialogue, recovery))

    return results
