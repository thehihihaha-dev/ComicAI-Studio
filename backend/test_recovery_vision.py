import base64
import json
import urllib.request


MODEL = "qwen3-vl:8b-instruct"

CROPS = [
    {
        "candidate_id": 1,
        "block_ids": [1],
        "texts": ["RIN"],
        "path": "tmp/recovery/candidate_1.jpg",
    },
    {
        "candidate_id": 2,
        "block_ids": [11, 12, 13],
        "texts": ["Con", "XIN", "THỀ!"],
        "path": "tmp/recovery/candidate_2.jpg",
    },
]


def analyze_crop(candidate):
    with open(candidate["path"], "rb") as image_file:
        image_base64 = base64.b64encode(
            image_file.read()
        ).decode("utf-8")

    prompt = f"""
You are validating a cropped region from a comic page.

OCR detected these blocks inside or near this crop:

Block IDs: {candidate["block_ids"]}
OCR texts: {candidate["texts"]}

Look at the IMAGE carefully.

Determine whether these OCR blocks belong to a distinct
speech bubble or dialogue region.

Do not perform OCR again.
Do not invent block IDs.

Return ONLY valid JSON:

{{
  "is_dialogue_region": true,
  "type": "speech_bubble",
  "block_ids": [],
  "confidence": 0.0
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
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=180,
    ) as response:
        result = json.loads(response.read())

    return json.loads(result["response"])


for candidate in CROPS:
    print(
        f"\nCandidate {candidate['candidate_id']}"
    )

    result = analyze_crop(candidate)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
