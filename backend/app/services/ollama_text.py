import json
import hashlib
import urllib.error
import urllib.request
from typing import Any

from app.services.performance import measure_model_call
from app.services.model_runtime import effective_generation_options


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_TEXT_MODEL = "qwen3-vl:8b-instruct"


def call_text_model(
    prompt: str,
    model: str = DEFAULT_TEXT_MODEL,
    timeout: int = 180,
    json_mode: bool = False,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": effective_generation_options(),
    }
    if json_mode:
        payload["format"] = "json"
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with measure_model_call(
        model,
        prompt_chars=len(prompt),
        prompt_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        generation_options=payload["options"],
    ) as metrics:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_data = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Ollama text request failed with HTTP {error.code}: {error_body}"
            ) from error

        result = json.loads(response_data)
        raw_response = result.get("response", "")
        metrics["output_chars"] = len(raw_response) if isinstance(raw_response, str) else 0
        if isinstance(raw_response, str):
            metrics["raw_response_hash"] = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()
        if not isinstance(raw_response, str) or not raw_response.strip():
            raise RuntimeError("Text model returned an empty response.")

        cleaned_response = _strip_markdown_fence(raw_response)
        try:
            parsed = json.loads(cleaned_response)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"Text model returned invalid JSON: {raw_response}"
            ) from error

        if not isinstance(parsed, dict):
            raise RuntimeError("Text model JSON response must be an object.")
        return parsed


def _strip_markdown_fence(value: str) -> str:
    cleaned = value.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
