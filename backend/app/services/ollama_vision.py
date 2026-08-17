import base64
import hashlib
import json
import urllib.request
import urllib.error
from typing import Any

from PIL import Image

from app.services.performance import measure_model_call, measure_stage
from app.services.model_runtime import effective_generation_options


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_VISION_MODEL = "qwen3-vl:8b-instruct"


def call_vision_model(
    image_path: str,
    prompt: str,
    model: str = DEFAULT_VISION_MODEL,
    timeout: int = 180,
    json_mode: bool = False,
) -> dict[str, Any]:

    with measure_stage("image_preparation"):
        with Image.open(image_path) as image:
            image_dimensions = [image.width, image.height]
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "options": effective_generation_options(),
    }
    if json_mode:
        payload["format"] = "json"

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with measure_model_call(
        model,
        prompt_chars=len(prompt),
        prompt_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        image_hash=hashlib.sha256(image_bytes).hexdigest(),
        image_dimensions=image_dimensions,
        generation_options=payload["options"],
    ) as metrics:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_data = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            print("\n=== OLLAMA HTTP ERROR ===")
            print("Status:", error.code)
            print("Reason:", error.reason)
            print("Body:", error_body)
            raise

        result = json.loads(response_data)

        raw_response = result.get("response", "")
        metrics["output_chars"] = len(raw_response) if isinstance(raw_response, str) else 0
        if isinstance(raw_response, str):
            metrics["raw_response_hash"] = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()

        if not raw_response.strip():
            raise RuntimeError("Vision model returned an empty response")
        cleaned_response = raw_response.strip()

        if cleaned_response.startswith("```"):
            response_lines = cleaned_response.splitlines()[1:]

            if response_lines and response_lines[-1].strip() == "```":
                response_lines = response_lines[:-1]

            cleaned_response = "\n".join(response_lines).strip()

        try:
            return json.loads(cleaned_response)

        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"Vision model returned invalid JSON: {raw_response}"
            ) from error
