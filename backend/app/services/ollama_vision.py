import base64
import json
import urllib.request
import urllib.error
from typing import Any


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_VISION_MODEL = "qwen3-vl:8b-instruct"


def call_vision_model(
    image_path: str,
    prompt: str,
    model: str = DEFAULT_VISION_MODEL,
    timeout: int = 180,
) -> dict[str, Any]:

    with open(image_path, "rb") as image_file:
        image_base64 = base64.b64encode(
            image_file.read()
        ).decode("utf-8")

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "options": {
            "num_ctx": 8192,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            response_data = response.read().decode(
                "utf-8"
            )

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        print("\n=== OLLAMA HTTP ERROR ===")
        print("Status:", error.code)
        print("Reason:", error.reason)
        print("Body:", error_body)

        raise

    # Parse response của Ollama
    result = json.loads(response_data)

    raw_response = result.get(
        "response",
        "",
    )

    if not raw_response.strip():
        raise RuntimeError(
            "Vision model returned an empty response"
        )
    cleaned_response = raw_response.strip()

    if cleaned_response.startswith("```"):
        cleaned_response = cleaned_response.removeprefix("```json")
        cleaned_response = cleaned_response.removeprefix("```")
        cleaned_response = cleaned_response.removesuffix("```")
        cleaned_response = cleaned_response.strip()

    try:
        return json.loads(cleaned_response)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Vision model returned invalid JSON: "
            f"{raw_response}"
        ) from error