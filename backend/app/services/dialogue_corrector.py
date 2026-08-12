import json
from typing import Any

from app.services.ollama_vision import call_vision_model


def correct_dialogues(
    image_path: str,
    dialogues: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    dialogue_json = json.dumps(
        dialogues,
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
You are correcting OCR errors from a comic page.

You receive:
1. The original comic image.
2. Dialogue regions already detected in correct reading order.
3. Raw OCR text.

DIALOGUES:

{dialogue_json}

Your task:
- Correct OCR spelling and character recognition errors.
- Preserve the original language.
- Preserve names.
- Preserve the original meaning.
- Use the image to verify uncertain text.
- Do NOT translate.
- Do NOT summarize.
- Do NOT rewrite dialogue creatively.
- Do NOT add information that is not visible in the image.
- Keep every order and region_id unchanged.
- confidence must be between 0.0 and 1.0
- Set needs_review=true if the correction is uncertain.
- Use lower confidence when the image text is ambiguous.
- Do not hide uncertainty.

Return ONLY valid JSON:

{{
  "dialogues": [
    {{
      "order": 1,
      "region_id": 1,
      "raw_text": "original OCR",
      "clean_text": "corrected text",
      "confidence": 0.95,
      "needs_review": false,
      "reason": "Minor OCR accent correction"
    }}
  ]
}}
"""

    result = call_vision_model(
        image_path=image_path,
        prompt=prompt,
    )

    return result.get("dialogues", [])
def validate_corrected_dialogues(
    original_dialogues: list[dict[str, Any]],
    corrected_dialogues: list[dict[str, Any]],
) -> dict[str, Any]:

    original_map = {
        dialogue["region_id"]: dialogue
        for dialogue in original_dialogues
    }

    corrected_map = {
        dialogue.get("region_id"): dialogue
        for dialogue in corrected_dialogues
    }

    missing_region_ids = []
    invalid_region_ids = []
    order_mismatches = []
    empty_clean_text = []

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

        clean_text = corrected.get("clean_text", "")

        if not isinstance(clean_text, str) or not clean_text.strip():
            empty_clean_text.append(region_id)

    is_valid = (
        len(corrected_dialogues) == len(original_dialogues)
        and not missing_region_ids
        and not invalid_region_ids
        and not order_mismatches
        and not empty_clean_text
    )

    return {
        "is_valid": is_valid,
        "total_original": len(original_dialogues),
        "total_corrected": len(corrected_dialogues),
        "missing_region_ids": missing_region_ids,
        "invalid_region_ids": invalid_region_ids,
        "order_mismatches": order_mismatches,
        "empty_clean_text": empty_clean_text,
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
from difflib import SequenceMatcher


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