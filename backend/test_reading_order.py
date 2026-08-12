import base64
import json
import urllib.request

from app.database import SessionLocal
from app.models.asset import Asset
from app.services.vision_analyzer import build_region_geometry


MODEL = "qwen3-vl:8b-instruct"
ASSET_FILENAME = "2.jpg"


db = SessionLocal()

try:
    asset = (
        db.query(Asset)
        .filter(Asset.filename == ASSET_FILENAME)
        .first()
    )

    if not asset:
        raise RuntimeError("Asset not found")

    ocr_blocks = json.loads(asset.ocr_blocks)

finally:
    db.close()


# Kết quả sau full-page Vision + recovery
regions = [
    {
        "id": 1,
        "type": "speech_bubble",
        "block_ids": [0, 2, 3, 4],
    },
    {
        "id": 2,
        "type": "speech_bubble",
        "block_ids": [5, 6, 7, 8, 9, 10],
    },
    {
        "id": 3,
        "type": "speech_bubble",
        "block_ids": [11, 12, 13],
    },
    {
        "id": 4,
        "type": "speech_bubble",
        "block_ids": [1],
        "recovered": True,
    },
]


geometry = build_region_geometry(
    regions,
    ocr_blocks,
)


# Thêm text để model hiểu nội dung từng region
for region in geometry:
    region["text"] = " ".join(
        ocr_blocks[block_id]["text"]
        for block_id in region["block_ids"]
    )


with open(asset.file_path, "rb") as image_file:
    image_base64 = base64.b64encode(
        image_file.read()
    ).decode("utf-8")


region_json = json.dumps(
    geometry,
    ensure_ascii=False,
    indent=2,
)


prompt = f"""
You are analyzing the reading order of dialogue
regions on a comic page.

The dialogue regions have ALREADY been detected.
Do NOT detect new regions.
Do NOT merge regions.
Do NOT remove regions.
Do NOT perform OCR.

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

Do NOT simply sort by Y coordinate.
Do NOT assume region IDs represent reading order.

Every region ID must appear exactly once.

Return ONLY valid JSON:

{{
  "reading_order": [1, 2, 3, 4]
}}
"""


payload = {
    "model": MODEL,
    "prompt": prompt,
    "images": [image_base64],
    "stream": False,
    "format": "json",
}


request = urllib.request.Request(
    "http://127.0.0.1:11434/api/generate",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
    },
    method="POST",
)


with urllib.request.urlopen(
    request,
    timeout=180,
) as response:
    result = json.loads(response.read())


raw_response = result.get("response", "")

print("RAW RESPONSE:")
print(raw_response)

if not raw_response.strip():
    raise RuntimeError(
        "Model returned an empty response"
    )


reading_result = json.loads(raw_response)

print("\nREADING ORDER:")
print(
    json.dumps(
        reading_result,
        ensure_ascii=False,
        indent=2,
    )
)