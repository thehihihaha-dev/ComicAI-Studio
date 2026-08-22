from __future__ import annotations

import contextlib
import os
import platform
import re
import resource
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterator


GIB = 1024**3
NORMAL = "NORMAL"
WARNING = "WARNING"
CRITICAL = "CRITICAL"


class HeavyInferenceRejected(RuntimeError):
    """Raised before launch when resource policy cannot safely admit work."""


@dataclass(frozen=True)
class ResourceThresholds:
    """Conservative defaults for the 16 GiB Day 11 development machine."""

    warning_available_bytes: int = 3 * GIB
    critical_available_bytes: int = int(1.5 * GIB)
    warning_swap_used_bytes: int = 2 * GIB
    critical_swap_used_bytes: int = 4 * GIB

    def __post_init__(self) -> None:
        if not 0 <= self.critical_available_bytes <= self.warning_available_bytes:
            raise ValueError("available-memory thresholds must satisfy 0 <= critical <= warning")
        if not 0 <= self.warning_swap_used_bytes <= self.critical_swap_used_bytes:
            raise ValueError("swap thresholds must satisfy 0 <= warning <= critical")

    @classmethod
    def from_environment(cls) -> ResourceThresholds:
        def bytes_from_gib(name: str, default: float) -> int:
            raw = os.getenv(name)
            if raw is None:
                return int(default * GIB)
            try:
                value = float(raw)
            except ValueError as error:
                raise ValueError(f"{name} must be a number of GiB") from error
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
            return int(value * GIB)

        return cls(
            warning_available_bytes=bytes_from_gib("COMICAI_WARNING_AVAILABLE_GIB", 3),
            critical_available_bytes=bytes_from_gib("COMICAI_CRITICAL_AVAILABLE_GIB", 1.5),
            warning_swap_used_bytes=bytes_from_gib("COMICAI_WARNING_SWAP_GIB", 2),
            critical_swap_used_bytes=bytes_from_gib("COMICAI_CRITICAL_SWAP_GIB", 4),
        )


def classify_resource_state(
    sample: dict[str, Any], thresholds: ResourceThresholds
) -> str:
    available = sample.get("system_available_memory_bytes")
    swap = sample.get("swap_used_bytes")
    if (
        isinstance(available, int)
        and available <= thresholds.critical_available_bytes
    ) or (isinstance(swap, int) and swap >= thresholds.critical_swap_used_bytes):
        return CRITICAL
    if (
        isinstance(available, int)
        and available <= thresholds.warning_available_bytes
    ) or (isinstance(swap, int) and swap >= thresholds.warning_swap_used_bytes):
        return WARNING
    return NORMAL


def _run(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _process_rss_bytes() -> int | None:
    output = _run(["ps", "-o", "rss=", "-p", str(os.getpid())])
    try:
        return int(output) * 1024 if output else None
    except ValueError:
        return None


def _available_memory_bytes() -> int | None:
    output = _run(["vm_stat"])
    if not output:
        return None
    page_match = re.search(r"page size of (\d+) bytes", output)
    if not page_match:
        return None
    values: dict[str, int] = {}
    for key in ("Pages free", "Pages inactive", "Pages speculative"):
        match = re.search(rf"^{re.escape(key)}:\s+(\d+)\.", output, re.MULTILINE)
        if match:
            values[key] = int(match.group(1))
    if "Pages free" not in values:
        return None
    # macOS can reclaim inactive/speculative pages. This is an approximation,
    # not a claim about physically unused RAM.
    return sum(values.values()) * int(page_match.group(1))


def _swap_used_bytes() -> int | None:
    output = _run(["sysctl", "vm.swapusage"])
    if not output:
        return None
    match = re.search(r"used\s*=\s*([0-9.]+)([KMGTP])", output)
    if not match:
        return None
    units = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5}
    return int(float(match.group(1)) * units[match.group(2)])


def sample_resources(
    thresholds: ResourceThresholds | None = None,
) -> dict[str, Any]:
    configured = thresholds or ResourceThresholds.from_environment()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    sample: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "process_rss_bytes": _process_rss_bytes(),
        "process_peak_rss_bytes": int(usage.ru_maxrss)
        * (1 if platform.system() == "Darwin" else 1024),
        "system_available_memory_bytes": _available_memory_bytes(),
        "system_available_memory_note": "free + inactive + speculative vm_stat pages; reclaimable approximation",
        "swap_used_bytes": _swap_used_bytes(),
        "process_cpu_seconds": round(usage.ru_utime + usage.ru_stime, 6),
        "temperature_celsius": None,
        "temperature_note": "not measured: no reliable supported macOS standard-library API",
    }
    sample["safety_state"] = classify_resource_state(sample, configured)
    return sample


class HeavyInferenceGuard:
    """Non-blocking, process-local admission guard for one heavy model call."""

    def __init__(self, concurrency: int = 1) -> None:
        if concurrency != 1:
            raise ValueError("Checkpoint 11.1 requires heavy_model_concurrency=1")
        self._slot = threading.BoundedSemaphore(concurrency)
        self._active = 0
        self._state_lock = threading.Lock()

    @property
    def active(self) -> int:
        with self._state_lock:
            return self._active

    @contextlib.contextmanager
    def acquire(
        self,
        stage: str,
        *,
        sampler: Callable[[ResourceThresholds], dict[str, Any]] = sample_resources,
        thresholds: ResourceThresholds | None = None,
    ) -> Iterator[dict[str, Any]]:
        configured = thresholds or ResourceThresholds.from_environment()
        prelaunch = sampler(configured)
        if prelaunch["safety_state"] == CRITICAL:
            raise HeavyInferenceRejected(
                f"CRITICAL resources: heavy stage {stage!r} rejected before launch"
            )
        if not self._slot.acquire(blocking=False):
            raise HeavyInferenceRejected(
                f"heavy_model_concurrency=1: stage {stage!r} rejected while another heavy call is active"
            )
        with self._state_lock:
            self._active += 1
        try:
            yield prelaunch
        finally:
            with self._state_lock:
                self._active -= 1
            self._slot.release()


heavy_inference_guard = HeavyInferenceGuard()


@contextlib.contextmanager
def heavy_inference_slot(stage: str) -> Iterator[dict[str, Any]]:
    with heavy_inference_guard.acquire(stage) as sample:
        yield sample
