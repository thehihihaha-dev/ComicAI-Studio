import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


RUNNER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_pipeline.py"
SPEC = importlib.util.spec_from_file_location("benchmark_pipeline_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


class BenchmarkArtifactTests(unittest.TestCase):
    def test_output_is_valid_json_and_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            output.write_text("old")
            runner.atomic_write_json(output, {"status": "completed", "value": "✓"})
            self.assertEqual(json.loads(output.read_text()), {"status": "completed", "value": "✓"})
            self.assertEqual(list(output.parent.glob(f".{output.name}.*.tmp")), [])

    @patch.object(runner, "_asset_statuses", return_value=[])
    @patch.object(runner, "process_single_asset", side_effect=RuntimeError("pipeline failed"))
    def test_failed_benchmark_can_be_persisted_with_partial_telemetry(self, _process, _statuses):
        report = runner.run_benchmark("project", [("asset", "1.jpg")], deterministic=True)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed.json"
            runner.atomic_write_json(output, report)
            saved = json.loads(output.read_text())
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["failure_stage"], "page_total")
        self.assertIn("stages", saved)
        self.assertIn("model_calls", saved)

    def test_success_artifact_has_expected_top_level_fields(self):
        report = {
            "status": "completed",
            "wall_clock_seconds": 1.0,
            "results": {"page_count": 4, "story_result_usable": True},
            "page_timings": [],
            "project_timings": {},
            "model_calls": [],
            "call_budget": {},
            "benchmark_metadata": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "success.json"
            runner.atomic_write_json(output, report)
            saved = json.loads(output.read_text())
        for field in (
            "benchmark_metadata", "results", "page_timings", "project_timings",
            "model_calls", "call_budget", "wall_clock_seconds",
        ):
            self.assertIn(field, saved)

    def test_terminal_summary_does_not_render_raw_telemetry(self):
        report = {
            "status": "completed",
            "wall_clock_seconds": 1.25,
            "results": {"page_count": 4, "story_result_usable": True},
            "model_calls": [{"raw_response": "huge-secret-output"}],
        }
        summary = runner.format_terminal_summary(report, "/tmp/report.json")
        self.assertIn("Model calls: 1", summary)
        self.assertIn("Story usable: YES", summary)
        self.assertNotIn("huge-secret-output", summary)


if __name__ == "__main__":
    unittest.main()
