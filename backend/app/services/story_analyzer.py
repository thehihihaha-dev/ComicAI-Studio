from typing import Any

def get_block_geometry(
    block: dict[str, Any],
) -> dict[str, float]:
    box = block.get("box", [])

    if not box:
        return {
            "x": 0,
            "y": 0,
            "width": 0,
            "height": 0,
            "center_x": 0,
            "center_y": 0,
        }

    xs = [point[0] for point in box]
    ys = [point[1] for point in box]

    x = min(xs)
    y = min(ys)
    width = max(xs) - x
    height = max(ys) - y

    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "center_x": x + width / 2,
        "center_y": y + height / 2,
    }
def analyze_story_page(
    ocr_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Analyze OCR blocks from one comic page.

    Day 7 V1:
    - Receive structured OCR data.
    - Preserve original OCR blocks.
    - Prepare data for layout / vision analysis.

    Later:
    - Detect speech bubbles.
    - Determine reading order.
    - Correct OCR text.
    - Understand dialogue and story context.
    """

    if not ocr_blocks:
        return {
            "status": "empty",
            "blocks": [],
            "block_count": 0,
        }

    cleaned_blocks = []

    for block in ocr_blocks:
        text = block.get("text", "").strip()

        if not text:
            continue

        geometry = get_block_geometry(block)

        cleaned_blocks.append(
            {
                "text": text,
                "confidence": block.get("confidence", 0.0),
                "box": block.get("box", []),
                "geometry": geometry,
            }
        )

    return {
        "status": "ready",
        "page": {
            "blocks": cleaned_blocks,
            "regions": [],
        },
        "block_count": len(cleaned_blocks),
    }