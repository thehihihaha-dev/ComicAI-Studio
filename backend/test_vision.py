import base64
import json
import urllib.request

from app.database import SessionLocal
from app.models.asset import Asset
from app.services.vision_analyzer import build_vision_context


ASSET_FILENAME = "2.jpg"


# 1. Lấy ảnh + OCR blocks từ database
db = SessionLocal()

try:
    asset = (
        db.query(Asset)
        .filter(Asset.filename == ASSET_FILENAME)
        .first()
    )

    if not asset:
        raise RuntimeError("Asset not found")

    if not asset.ocr_blocks:
        raise RuntimeError("Asset has no OCR blocks")

    image_path = asset.file_path
    raw_blocks = json.loads(asset.ocr_blocks)

finally:
    db.close()


# 2. Chuẩn hóa OCR blocks
ocr_context = build_vision_context(raw_blocks)


# 3. Encode ảnh
with open(image_path, "rb") as image_file:
    image_base64 = base64.b64encode(
        image_file.read()
    ).decode("utf-8")


# 4. Đưa OCR context vào prompt
ocr_json = json.dumps(
    ocr_context,
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


# 5. Gọi Ollama
payload = {
    "model": "qwen3-vl:8b-instruct",
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


# 6. Parse JSON model trả về
raw_response = result.get("response", "")

print("RAW RESPONSE:")
print(raw_response)

if not raw_response.strip():
    raise RuntimeError("Model returned an empty response")

vision_result = json.loads(raw_response)

print(
    json.dumps(
        vision_result,
        ensure_ascii=False,
        indent=2,
    )
)