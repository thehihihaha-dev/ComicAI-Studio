from typing import Any
from pathlib import Path
from PIL import Image
import json
import tempfile

from app.services.ollama_vision import call_vision_model

def build_vision_context(
    ocr_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    context = []

    for index, block in enumerate(ocr_blocks):
        context.append(
            {
                "id": index,
                "text": block.get("text", ""),
                "confidence": block.get("confidence", 0.0),
                "box": block.get("box", []),
            }
        )

    return context
def validate_vision_result(
    vision_result: dict[str, Any],
    ocr_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    all_block_ids = set(range(len(ocr_blocks)))

    assigned_ids = []
    duplicate_ids = []
    invalid_ids = []

    seen_ids = set()

    for region in vision_result.get("regions", []):
        for block_id in region.get("block_ids", []):
            if block_id not in all_block_ids:
                invalid_ids.append(block_id)
                continue

            if block_id in seen_ids:
                duplicate_ids.append(block_id)
            else:
                seen_ids.add(block_id)
                assigned_ids.append(block_id)

    missing_ids = sorted(
        all_block_ids - seen_ids
    )

    ignored_missing_ids = []
    important_missing_ids = []

    for block_id in missing_ids:
        if not (
            0 <= block_id < len(ocr_blocks)
        ):
            important_missing_ids.append(
                block_id
            )
            continue

        confidence = float(
            ocr_blocks[block_id].get(
                "confidence",
                0.0,
            )
        )

        # OCR confidence quá thấp:
        # nhiều khả năng chỉ là text rác
        if confidence < 0.20:
            ignored_missing_ids.append(
                block_id
            )
        else:
            important_missing_ids.append(
                block_id
            )

    is_valid = (
        len(important_missing_ids) == 0
        and len(duplicate_ids) == 0
        and len(invalid_ids) == 0
    )

    return {
        "is_valid": is_valid,
        "total_blocks": len(all_block_ids),
        "assigned_blocks": len(seen_ids),
        "missing_block_ids": missing_ids,
        "ignored_missing_block_ids": (
            ignored_missing_ids
        ),
        "important_missing_block_ids": (
            important_missing_ids
        ),
        "duplicate_block_ids": sorted(
            set(duplicate_ids)
        ),
        "invalid_block_ids": sorted(
            set(invalid_ids)
        ),
    }
def get_unassigned_blocks(
    validation: dict[str, Any],
    ocr_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    missing_ids = validation.get(
        "missing_block_ids",
        [],
    )

    unassigned_blocks = []

    for block_id in missing_ids:
        if block_id < 0 or block_id >= len(ocr_blocks):
            continue

        block = ocr_blocks[block_id]

        unassigned_blocks.append(
            {
                "id": block_id,
                "text": block.get("text", ""),
                "confidence": block.get(
                    "confidence",
                    0.0,
                ),
                "box": block.get("box", []),
            }
        )

    return unassigned_blocks
def recover_missing_blocks(
    image_path: str,
    vision_result: dict[str, Any],
    validation: dict[str, Any],
    ocr_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    important_missing_ids = validation.get(
        "important_missing_block_ids",
        [],
    )

    if not important_missing_ids:
        return vision_result

    missing_blocks = []

    for block_id in important_missing_ids:
        if 0 <= block_id < len(ocr_blocks):
            block = ocr_blocks[block_id]

            missing_blocks.append(
                {
                    "id": block_id,
                    "text": block.get("text", ""),
                    "confidence": block.get(
                        "confidence",
                        0.0,
                    ),
                    "box": block.get("box", []),
                }
            )

    prompt = f"""
You are recovering OCR blocks that were not assigned
to any text region on a comic page.

CURRENT VISION RESULT:

{json.dumps(
    vision_result,
    ensure_ascii=False,
    indent=2,
)}

IMPORTANT UNASSIGNED OCR BLOCKS:

{json.dumps(
    missing_blocks,
    ensure_ascii=False,
    indent=2,
)}

Look at the original image carefully.

For each unassigned block:
- Determine whether it belongs to an existing region.
- If yes, add its block id to that region.
- If it belongs to a separate visible text region, create a new region.
- Preserve all existing region ids when possible.
- Do NOT invent OCR block ids.
- Do NOT remove valid existing blocks.

Allowed region types include:
- speech_bubble
- narration
- thought
- title
- game_ui
- note
- translator_note
- other

Return ONLY valid JSON:

{{
  "regions": [
    {{
      "id": 1,
      "type": "narration",
      "block_ids": [0, 1]
    }}
  ],
  "reading_order": [1]
}}
"""

    recovered = call_vision_model(
        image_path=image_path,
        prompt=prompt,
    )

    return recovered
def create_recovery_crop(
    image_path: str,
    blocks: list[dict[str, Any]],
    output_path: str,
    padding: int = 80,
) -> str:
    if not blocks:
        raise ValueError("No blocks provided for recovery crop")

    xs = []
    ys = []

    for block in blocks:
        box = block.get("box", [])

        for point in box:
            xs.append(point[0])
            ys.append(point[1])

    if not xs or not ys:
        raise ValueError("Blocks have no valid coordinates")

    with Image.open(image_path) as image:
        image_width, image_height = image.size

        left = max(0, min(xs) - padding)
        top = max(0, min(ys) - padding)
        right = min(image_width, max(xs) + padding)
        bottom = min(image_height, max(ys) + padding)

        crop = image.crop(
            (left, top, right, bottom)
        )

        output = Path(output_path)
        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        crop.save(output)

    return str(output)
def group_recovery_candidates(
    blocks: list[dict[str, Any]],
    distance_threshold: float = 120.0,
) -> list[list[dict[str, Any]]]:
    if not blocks:
        return []

    def get_center(block):
        box = block.get("box", [])

        xs = [point[0] for point in box]
        ys = [point[1] for point in box]

        return (
            sum(xs) / len(xs),
            sum(ys) / len(ys),
        )

    remaining = blocks.copy()
    groups = []

    while remaining:
        current = remaining.pop(0)
        group = [current]

        changed = True

        while changed:
            changed = False

            for candidate in remaining[:]:
                candidate_x, candidate_y = get_center(candidate)

                for member in group:
                    member_x, member_y = get_center(member)

                    distance = (
                        (candidate_x - member_x) ** 2
                        + (candidate_y - member_y) ** 2
                    ) ** 0.5

                    if distance <= distance_threshold:
                        group.append(candidate)
                        remaining.remove(candidate)
                        changed = True
                        break

        groups.append(group)

    return groups
def create_recovery_crops(
    image_path: str,
    groups: list[list[dict[str, Any]]],
    output_dir: str = "tmp/recovery",
    padding: int = 80,
) -> list[dict[str, Any]]:
    results = []

    for index, group in enumerate(groups, start=1):
        output_path = (
            f"{output_dir}/candidate_{index}.jpg"
        )

        crop_path = create_recovery_crop(
            image_path=image_path,
            blocks=group,
            output_path=output_path,
            padding=padding,
        )

        results.append(
            {
                "candidate_id": index,
                "block_ids": [
                    block["id"]
                    for block in group
                ],
                "crop_path": crop_path,
            }
        )

    return results
def recover_dialogue_regions(
    image_path: str,
    ocr_blocks: list[dict[str, Any]],
    validation: dict[str, Any],
) -> list[dict[str, Any]]:
    missing_blocks = get_unassigned_blocks(
        validation,
        ocr_blocks,
    )

    if not missing_blocks:
        return []

    groups = group_recovery_candidates(
        missing_blocks,
    )

    recovery_results = []

    Path("tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="vision-recovery-",
        dir="tmp",
    ) as recovery_dir:
        crops = create_recovery_crops(
            image_path,
            groups,
            output_dir=recovery_dir,
        )

        for crop, group in zip(crops, groups):
            block_ids = [
                block["id"]
                for block in group
            ]

            texts = [
                block.get("text", "")
                for block in group
            ]

            prompt = f"""
You are validating a cropped region from a comic page.

OCR detected these blocks inside or near this crop:

Block IDs: {block_ids}
OCR texts: {texts}

Look carefully at the IMAGE.

Determine whether these OCR blocks belong to a distinct
speech bubble or dialogue region.

Do not perform OCR again.
Do not invent block IDs.

Return ONLY valid JSON:

{{
  "is_dialogue_region": true,
  "type": "speech_bubble",
  "block_ids": {block_ids},
  "confidence": 0.0
}}
"""

            result = call_vision_model(
                image_path=crop["crop_path"],
                prompt=prompt,
            )

            recovery_results.append(result)

    return recovery_results
def merge_recovered_regions(
    vision_result: dict[str, Any],
    recovery_results: list[dict[str, Any]],
) -> dict[str, Any]:
    regions = list(
        vision_result.get("regions", [])
    )

    existing_ids = {
        region.get("id")
        for region in regions
    }

    next_region_id = (
        max(existing_ids) + 1
        if existing_ids
        else 1
    )

    for recovery in recovery_results:
        if not recovery.get("is_dialogue_region"):
            continue

        block_ids = recovery.get(
            "block_ids",
            [],
        )

        if not block_ids:
            continue

        regions.append(
            {
                "id": next_region_id,
                "type": recovery.get(
                    "type",
                    "speech_bubble",
                ),
                "block_ids": block_ids,
                "recovered": True,
                "confidence": recovery.get(
                    "confidence",
                    0.0,
                ),
            }
        )

        next_region_id += 1

    return {
        **vision_result,
        "regions": regions,
    }
def build_region_geometry(
    regions: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []

    for region in regions:
        block_ids = region.get("block_ids", [])

        xs = []
        ys = []

        for block_id in block_ids:
            if block_id < 0 or block_id >= len(ocr_blocks):
                continue

            box = ocr_blocks[block_id].get("box", [])

            for point in box:
                xs.append(point[0])
                ys.append(point[1])

        if not xs or not ys:
            continue

        left = min(xs)
        top = min(ys)
        right = max(xs)
        bottom = max(ys)

        result.append(
            {
                "id": region.get("id"),
                "type": region.get("type", "unknown"),
                "block_ids": block_ids,
                "bbox": [
                    left,
                    top,
                    right,
                    bottom,
                ],
                "center": [
                    (left + right) / 2,
                    (top + bottom) / 2,
                ],
                "recovered": region.get(
                    "recovered",
                    False,
                ),
            }
        )

    return result
def analyze_reading_order(
    image_path: str,
    regions: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
) -> list[int]:
    region_geometry = build_region_geometry(
        regions,
        ocr_blocks,
    )

    for region in region_geometry:
        region["text"] = " ".join(
            ocr_blocks[block_id].get("text", "")
            for block_id in region["block_ids"]
            if 0 <= block_id < len(ocr_blocks)
        )

    region_json = json.dumps(
        region_geometry,
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
You are analyzing the reading order of dialogue
regions on a comic page.

The dialogue regions have ALREADY been detected.

Do NOT:
- detect new regions
- remove regions
- merge regions
- perform OCR
- assume region IDs represent reading order

REGIONS:

{region_json}

Look at the original comic image and determine
the natural dialogue reading order.

Use:
- speech bubble placement
- panel composition
- dialogue flow
- spatial relationships
- comic reading conventions
- semantic continuity when useful

Every region ID must appear exactly once.

Return ONLY valid JSON:

{{
  "reading_order": [1, 2, 3]
}}
"""

    result = call_vision_model(
        image_path=image_path,
        prompt=prompt,
    )

    reading_order = result.get(
        "reading_order",
        [],
    )

    region_ids = {
        region.get("id")
        for region in regions
    }

    if (
        len(reading_order) != len(region_ids)
        or set(reading_order) != region_ids
    ):
        raise RuntimeError(
            f"Invalid reading order: {reading_order}"
        )

    return reading_order
def analyze_page_layout(
    image_path: str,
    ocr_blocks: list[dict[str, Any]],
) -> dict[str, Any]:

    vision_context = build_vision_context(ocr_blocks)

    return {
        "status": "ready",
        "image_path": image_path,
        "ocr_blocks": vision_context,
        "regions": [],
        "reading_order": [],
        "ocr_block_count": len(vision_context),
    }
def analyze_comic_page(
    image_path: str,
    ocr_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    vision_context = build_vision_context(ocr_blocks)

    ocr_json = json.dumps(
        vision_context,
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
You are a comic page layout analyzer.

You receive:
1. The original comic image.
2. OCR blocks extracted from that exact image.

Each OCR block has:
- id
- text
- confidence
- box coordinates

OCR BLOCKS:

{ocr_json}

Your task is NOT to perform OCR again.

Use the IMAGE to understand:
- speech bubble boundaries
- separate dialogue regions
- visual reading order

Use OCR block IDs to represent text.

Important:
- Blocks that are visually inside the same speech bubble belong to one region.
- A small isolated bubble must remain a separate region.
- Do NOT determine reading order by simply sorting Y coordinates.
- Use the visual composition of the comic.
- Do not invent OCR block IDs.

Return ONLY valid JSON.

Schema:

{{
  "regions": [
    {{
      "id": 1,
      "type": "speech_bubble",
      "block_ids": [0, 1]
    }}
  ],
  "reading_order": [1]
}}
"""

    vision_result = call_vision_model(
        image_path=image_path,
        prompt=prompt,
    )

    validation = validate_vision_result(
        vision_result,
        ocr_blocks,
    )
    if (
        len(vision_result.get("regions", [])) == 0
        and len(vision_result.get("reading_order", [])) == 0
    ):
        low_confidence_count = sum(
            1
            for block in ocr_blocks
            if float(block.get("confidence", 0.0)) < 0.40
        )

        low_confidence_ratio = (
            low_confidence_count / len(ocr_blocks)
            if ocr_blocks
            else 1.0
        )

        if low_confidence_ratio >= 0.60:
            return {
                "vision_result": {
                    "regions": [],
                    "reading_order": [],
                },
                "validation": {
                    **validation,
                    "is_valid": True,
                    "page_type": "no_dialogue",
                    "reason": (
                        "No dialogue regions detected and "
                        "most OCR blocks have low confidence."
                    ),
                },
                "recovery_results": [],
            }
    if not validation["is_valid"]:
        important_missing_ids = validation.get(
            "important_missing_block_ids",
            [],
        )

        if important_missing_ids:
            vision_result = recover_missing_blocks(
                image_path=image_path,
                vision_result=vision_result,
                validation=validation,
                ocr_blocks=ocr_blocks,
            )

            validation = validate_vision_result(
                vision_result,
                ocr_blocks,
            )

    recovery_results = []

    if not validation["is_valid"]:
        recovery_results = recover_dialogue_regions(
            image_path=image_path,
            ocr_blocks=ocr_blocks,
            validation=validation,
        )

        vision_result = merge_recovered_regions(
            vision_result,
            recovery_results,
        )

        validation = validate_vision_result(
            vision_result,
            ocr_blocks,
        )
    reading_order = []

    if validation["is_valid"]:
        reading_order = analyze_reading_order(
            image_path=image_path,
            regions=vision_result["regions"],
            ocr_blocks=ocr_blocks,
        )

        vision_result["reading_order"] = reading_order
    return {
        "vision_result": vision_result,
        "validation": validation,
        "recovery_results": recovery_results,
    }
