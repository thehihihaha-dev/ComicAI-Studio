from __future__ import annotations

import contextlib
import contextvars
import functools
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, TypeVar

from app.services.resource_safety import sample_resources


_collector_var: contextvars.ContextVar[PerformanceCollector | None] = (
    contextvars.ContextVar("performance_collector", default=None)
)
_model_context_var: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "performance_model_context", default={}
)
_stage_metadata_var: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "performance_stage_metadata", default={}
)
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class PerformanceCollector:
    stages: list[dict[str, Any]] = field(default_factory=list)
    model_calls: list[dict[str, Any]] = field(default_factory=list)
    resource_samples: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.perf_counter)
    started_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: float | None = None
    ended_at_utc: str | None = None

    def finish(self) -> None:
        if self.ended_at is None:
            self.ended_at = time.perf_counter()
            self.ended_at_utc = datetime.now(timezone.utc).isoformat()
            self.observe_resources("collector_end")

    def observe_resources(self, point: str, **metadata: Any) -> dict[str, Any]:
        sample = {"point": point, **sample_resources(), **metadata}
        self.resource_samples.append(sample)
        return sample

    @property
    def wall_clock_seconds(self) -> float:
        end = self.ended_at if self.ended_at is not None else time.perf_counter()
        return max(0.0, end - self.started_at)

    def report(self) -> dict[str, Any]:
        stage_work: dict[str, float] = {}
        for item in self.stages:
            if item["stage"] in {"page_total", "reliability_total"}:
                continue
            stage_work[item["stage"]] = stage_work.get(item["stage"], 0.0) + item[
                "duration_seconds"
            ]
        pages: dict[str, dict[str, Any]] = {}
        page_total_records = [item for item in self.stages if item["stage"] == "page_total"]
        page_source = page_total_records or self.stages
        for item in page_source:
            asset_id = item.get("asset_id")
            if not asset_id:
                continue
            page = pages.setdefault(
                asset_id,
                {"asset_id": asset_id, "filename": item.get("filename"), "total_seconds": 0.0},
            )
            page["total_seconds"] += item["duration_seconds"]
            if item.get("filename"):
                page["filename"] = item["filename"]
        for item in self.stages:
            asset_id = item.get("asset_id")
            if not asset_id or item["stage"] == "page_total":
                continue
            page = pages.setdefault(
                asset_id,
                {"asset_id": asset_id, "filename": item.get("filename"), "total_seconds": 0.0},
            )
            timings = page.setdefault("stage_seconds", {})
            timings[item["stage"]] = round(
                timings.get(item["stage"], 0.0) + item["duration_seconds"], 6
            )
        page_values = list(pages.values())
        durations = [page["total_seconds"] for page in page_values]
        slowest_stage = max(stage_work, key=stage_work.get) if stage_work else None
        slowest_page = max(page_values, key=lambda page: page["total_seconds"]) if page_values else None
        completed = len({item.get("asset_id") for item in self.stages if item.get("asset_id") and item["success"]})
        failed_ids = {item.get("asset_id") for item in self.stages if item.get("asset_id") and not item["success"]}
        page_call_budget: dict[str, dict[str, int]] = {}
        page_stages = {
            "vision_layout": "layout_calls",
            "vision_recovery": "vision_recovery_calls",
            "reading_order": "reading_order_calls",
            "dialogue_correction": "dialogue_correction_calls",
            "dialogue_recovery": "dialogue_recovery_calls",
        }
        for item in self.model_calls:
            asset_id = item.get("asset_id")
            budget_key = page_stages.get(item.get("stage"))
            if asset_id and budget_key:
                budget = page_call_budget.setdefault(asset_id, {key: 0 for key in page_stages.values()})
                budget[budget_key] += 1
        project_call_budget = {
            "story_analyzer_full_calls": sum(item.get("stage") == "story_analyzer" and int(item.get("attempt", 1)) == 1 for item in self.model_calls),
            "story_analyzer_repair_calls": sum(item.get("stage") == "story_analyzer_repair" for item in self.model_calls),
            "story_analyzer_full_retry_calls": sum(item.get("stage") == "story_analyzer" and int(item.get("attempt", 1)) > 1 for item in self.model_calls),
            "coverage_recovery_calls": sum(item.get("stage") == "coverage_recovery" for item in self.model_calls),
            "coverage_recovery_repair_calls": sum(item.get("stage") == "coverage_recovery_repair" for item in self.model_calls),
            "coverage_recovery_continuation_calls": sum(item.get("stage") == "coverage_recovery_continuation" for item in self.model_calls),
        }
        project_stage_names = {
            "story_input_builder", "story_analyzer", "story_analyzer_repair",
            "story_grounding", "coverage_calculation", "coverage_recovery",
            "coverage_recovery_repair", "coverage_recovery_continuation",
            "reliability_total",
        }
        project_timings: dict[str, float] = {}
        for item in self.stages:
            if item["stage"] in project_stage_names:
                project_timings[item["stage"]] = round(
                    project_timings.get(item["stage"], 0.0) + item["duration_seconds"], 6
                )
        rss_values = [
            value
            for sample in self.resource_samples
            for value in [sample.get("process_rss_bytes")]
            if isinstance(value, int)
        ]
        peak_rss_values = [
            value
            for sample in self.resource_samples
            for value in [sample.get("process_peak_rss_bytes")]
            if isinstance(value, int)
        ]
        first_sample = self.resource_samples[0] if self.resource_samples else {}
        last_sample = self.resource_samples[-1] if self.resource_samples else {}
        swap_before = first_sample.get("swap_used_bytes")
        swap_after = last_sample.get("swap_used_bytes")
        cpu_before = first_sample.get("process_cpu_seconds")
        cpu_after = last_sample.get("process_cpu_seconds")
        cpu_percent = (
            max(0.0, cpu_after - cpu_before) / self.wall_clock_seconds * 100
            if isinstance(cpu_before, (int, float))
            and isinstance(cpu_after, (int, float))
            and self.wall_clock_seconds > 0
            else None
        )
        states = [sample.get("safety_state") for sample in self.resource_samples]
        overall_state = (
            "CRITICAL" if "CRITICAL" in states else "WARNING" if "WARNING" in states else "NORMAL"
        )
        return {
            "total_assets": len(pages),
            "completed_assets": completed - len(failed_ids),
            "failed_assets": len(failed_ids),
            "wall_clock_seconds": round(self.wall_clock_seconds, 6),
            "started_at": self.started_at_utc,
            "ended_at": self.ended_at_utc,
            "stage_work_seconds": {key: round(value, 6) for key, value in stage_work.items()},
            "average_page_seconds": round(statistics.mean(durations), 6) if durations else 0.0,
            "median_page_seconds": round(statistics.median(durations), 6) if durations else 0.0,
            "p95_page_seconds": round(_percentile(durations, 0.95), 6) if durations else 0.0,
            "slowest_stage": slowest_stage,
            "slowest_page": slowest_page,
            "page_timings": page_values,
            "project_timings": project_timings,
            "total_model_calls": len(self.model_calls),
            "total_model_inference_seconds": round(sum(item["duration_seconds"] for item in self.model_calls), 6),
            "retry_count": sum(1 for item in self.model_calls if int(item.get("attempt", 1)) > 1),
            "call_budget": {"pages": page_call_budget, "project": project_call_budget},
            "stages": self.stages,
            "model_calls": self.model_calls,
            "resources": {
                "safety_state": overall_state,
                "process_rss_start_bytes": first_sample.get("process_rss_bytes"),
                "process_rss_end_bytes": last_sample.get("process_rss_bytes"),
                "peak_observed_rss_bytes": max(rss_values + peak_rss_values) if rss_values or peak_rss_values else None,
                "system_available_memory_start_bytes": first_sample.get("system_available_memory_bytes"),
                "system_available_memory_end_bytes": last_sample.get("system_available_memory_bytes"),
                "swap_before_bytes": swap_before,
                "swap_after_bytes": swap_after,
                "swap_delta_bytes": swap_after - swap_before if isinstance(swap_before, int) and isinstance(swap_after, int) else None,
                "process_cpu_utilization_percent": round(cpu_percent, 3) if cpu_percent is not None else None,
                "samples": self.resource_samples,
            },
        }


@contextlib.contextmanager
def collect_performance(collector: PerformanceCollector | None = None) -> Iterator[PerformanceCollector]:
    active = collector or PerformanceCollector()
    token = _collector_var.set(active)
    try:
        active.observe_resources("collector_start")
        yield active
    finally:
        active.finish()
        _collector_var.reset(token)


@contextlib.contextmanager
def measure_stage(stage: str, **metadata: Any) -> Iterator[None]:
    collector = _collector_var.get()
    if collector is None:
        yield
        return
    inherited_metadata = _stage_metadata_var.get()
    effective_metadata = {**inherited_metadata, **metadata}
    metadata_token = _stage_metadata_var.set(effective_metadata)
    started = time.perf_counter()
    collector.observe_resources("stage_start", **{**effective_metadata, "stage": stage})
    current_model_context = _model_context_var.get()
    model_token = _model_context_var.set({**current_model_context, "stage": stage})
    success = False
    try:
        yield
        success = True
    finally:
        _model_context_var.reset(model_token)
        _stage_metadata_var.reset(metadata_token)
        collector.stages.append(
            {"stage": stage, "duration_seconds": round(time.perf_counter() - started, 6), "success": success, **effective_metadata}
        )
        collector.observe_resources(
            "stage_end", **{**effective_metadata, "stage": stage, "success": success}
        )


def timed_stage(stage: str) -> Callable[[F], F]:
    def decorator(function: F) -> F:
        @functools.wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with measure_stage(stage):
                return function(*args, **kwargs)
        return wrapped  # type: ignore[return-value]
    return decorator


@contextlib.contextmanager
def model_call_context(stage: str, attempt: int = 1, **metadata: Any) -> Iterator[None]:
    token = _model_context_var.set({"stage": stage, "attempt": attempt, **metadata})
    try:
        yield
    finally:
        _model_context_var.reset(token)


@contextlib.contextmanager
def measure_model_call(model: str, **metadata: Any) -> Iterator[dict[str, Any]]:
    collector = _collector_var.get()
    result_metadata: dict[str, Any] = {}
    if collector is None:
        yield result_metadata
        return
    started = time.perf_counter()
    collector.observe_resources("model_call_start", model=model, **_model_context_var.get())
    success = False
    try:
        yield result_metadata
        success = True
    finally:
        collector.model_calls.append(
            {
                "stage": "unknown",
                "attempt": 1,
                **_stage_metadata_var.get(),
                **_model_context_var.get(),
                "model": model,
                **metadata,
                **result_metadata,
                "duration_seconds": round(time.perf_counter() - started, 6),
                "success": success,
            }
        )
        collector.observe_resources("model_call_end", model=model, success=success, **_model_context_var.get())


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.5)))
    return ordered[position]
