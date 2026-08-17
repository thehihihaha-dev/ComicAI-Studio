import unittest
from unittest.mock import patch

from app.services.performance import (
    PerformanceCollector,
    collect_performance,
    measure_model_call,
    measure_stage,
    model_call_context,
)


class PerformanceInstrumentationTests(unittest.TestCase):
    def test_timer_records_elapsed_duration(self):
        collector = PerformanceCollector()
        with patch("app.services.performance.time.perf_counter", side_effect=[10.0, 10.25, 10.5]):
            with collect_performance(collector):
                with measure_stage("ocr"):
                    pass
        self.assertEqual(collector.stages[0]["duration_seconds"], 0.25)

    def test_exception_is_recorded_and_not_swallowed(self):
        with collect_performance() as collector:
            with self.assertRaisesRegex(ValueError, "broken"):
                with measure_stage("vision"):
                    raise ValueError("broken")
        self.assertFalse(collector.stages[0]["success"])

    def test_multiple_stages_aggregate(self):
        collector = PerformanceCollector(
            stages=[
                {"stage": "ocr", "duration_seconds": 1.0, "success": True},
                {"stage": "ocr", "duration_seconds": 2.0, "success": True},
                {"stage": "vision", "duration_seconds": 4.0, "success": True},
            ],
            started_at=1.0,
            ended_at=3.0,
        )
        report = collector.report()
        self.assertEqual(report["stage_work_seconds"]["ocr"], 3.0)
        self.assertEqual(report["wall_clock_seconds"], 2.0)

    def test_retry_attempts_are_preserved(self):
        with collect_performance() as collector:
            for attempt in (1, 2):
                with model_call_context("story_analyzer", attempt):
                    with measure_model_call("model"):
                        pass
        self.assertEqual([item["attempt"] for item in collector.model_calls], [1, 2])
        self.assertEqual(collector.report()["retry_count"], 1)

    def test_summary_finds_slowest_stage_and_page(self):
        collector = PerformanceCollector(
            stages=[
                {"stage": "ocr", "duration_seconds": 2.0, "success": True, "asset_id": "a", "filename": "1.jpg"},
                {"stage": "vision", "duration_seconds": 5.0, "success": True, "asset_id": "b", "filename": "2.jpg"},
            ],
            started_at=1.0,
            ended_at=2.0,
        )
        report = collector.report()
        self.assertEqual(report["slowest_stage"], "vision")
        self.assertEqual(report["slowest_page"]["asset_id"], "b")


if __name__ == "__main__":
    unittest.main()
