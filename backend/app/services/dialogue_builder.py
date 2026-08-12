from typing import Any


def build_dialogues(
    ocr_blocks: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    reading_order: list[int],
) -> list[dict[str, Any]]:

    region_map = {
        region["id"]: region
        for region in regions
    }

    dialogues = []

    for order_index, region_id in enumerate(
        reading_order,
        start=1,
    ):
        region = region_map.get(region_id)

        if not region:
            continue

        block_ids = region.get("block_ids", [])

        texts = []

        for block_id in block_ids:
            if 0 <= block_id < len(ocr_blocks):
                text = ocr_blocks[block_id].get(
                    "text",
                    "",
                ).strip()

                if text:
                    texts.append(text)

        raw_text = " ".join(texts)

        dialogues.append(
            {
                "order": order_index,
                "region_id": region_id,
                "type": region.get(
                    "type",
                    "speech_bubble",
                ),
                "block_ids": block_ids,
                "raw_text": raw_text,
            }
        )

    return dialogues
