from __future__ import annotations

import contextlib
import contextvars
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Iterator


PRODUCTION_OPTIONS = {"num_ctx": 8192}
PRODUCTION_STORY_MODEL = "qwen3-vl:8b-instruct"
DETERMINISTIC_BENCHMARK_OPTIONS = {
    "num_ctx": 8192,
    "temperature": 0,
    "seed": 424242,
    "top_k": 1,
    "top_p": 1.0,
    "repeat_penalty": 1.0,
}

_options_var: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "ollama_generation_options", default=None
)
_story_model_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "story_model_override", default=None
)
_MODEL_REFERENCE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$"
)


def effective_generation_options() -> dict[str, Any]:
    configured = _options_var.get()
    return dict(configured if configured is not None else PRODUCTION_OPTIONS)


def validate_model_reference(value: str) -> str:
    normalized = value.strip()
    if not normalized or not _MODEL_REFERENCE.fullmatch(normalized):
        raise ValueError("Story model must be a local Ollama model reference")
    return normalized


def resolve_story_model(environment: dict[str, str] | None = None) -> str:
    override = _story_model_var.get()
    if override is not None:
        return validate_model_reference(override)
    source = os.environ if environment is None else environment
    configured = source.get("STORY_MODEL")
    return (
        validate_model_reference(configured)
        if configured is not None
        else PRODUCTION_STORY_MODEL
    )


@contextlib.contextmanager
def story_model_override(model: str) -> Iterator[None]:
    validated = validate_model_reference(model)
    token = _story_model_var.set(validated)
    try:
        yield
    finally:
        _story_model_var.reset(token)


def stable_text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_file_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextlib.contextmanager
def generation_options(options: dict[str, Any]) -> Iterator[None]:
    token = _options_var.set(dict(options))
    try:
        yield
    finally:
        _options_var.reset(token)


@contextlib.contextmanager
def generation_option_overrides(overrides: dict[str, Any]) -> Iterator[None]:
    """Temporarily merge call-family options into the active runtime options."""
    with generation_options({**effective_generation_options(), **overrides}):
        yield
