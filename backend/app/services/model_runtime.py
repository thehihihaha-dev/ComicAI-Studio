from __future__ import annotations

import contextlib
import contextvars
import hashlib
from pathlib import Path
from typing import Any, Iterator


PRODUCTION_OPTIONS = {"num_ctx": 8192}
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


def effective_generation_options() -> dict[str, Any]:
    configured = _options_var.get()
    return dict(configured if configured is not None else PRODUCTION_OPTIONS)


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
