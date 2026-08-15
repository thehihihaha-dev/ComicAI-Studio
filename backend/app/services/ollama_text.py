import json
import urllib.error
import urllib.request
from typing import Any


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_TEXT_MODEL = "qwen3-vl:8b-instruct"


def call_text_model(
    prompt: str,
    model: str = DEFAULT_TEXT_MODEL,
    timeout: int = 180,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 8192},
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

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
