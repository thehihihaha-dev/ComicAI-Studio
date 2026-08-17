import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.model_runtime import (
    DETERMINISTIC_BENCHMARK_OPTIONS,
    PRODUCTION_OPTIONS,
    effective_generation_options,
    generation_options,
    stable_file_hash,
    stable_text_hash,
)
from app.services.ollama_vision import call_vision_model


class DeterministicOptionsTests(unittest.TestCase):
    def test_benchmark_options_are_explicit_and_scoped(self):
        self.assertEqual(effective_generation_options(), PRODUCTION_OPTIONS)
        with generation_options(DETERMINISTIC_BENCHMARK_OPTIONS):
            options = effective_generation_options()
            self.assertEqual(options["temperature"], 0)
            self.assertEqual(options["seed"], 424242)
            self.assertEqual(options["num_ctx"], 8192)
        self.assertEqual(effective_generation_options(), PRODUCTION_OPTIONS)

    @patch("app.services.ollama_vision.Image.open")
    @patch("app.services.ollama_vision.urllib.request.urlopen")
    @patch("builtins.open")
    def test_fixed_options_reach_ollama_payload(self, image_open, urlopen, pil_open):
        image_open.return_value.__enter__.return_value.read.return_value = b"image"
        pil_open.return_value.__enter__.return_value.width = 10
        pil_open.return_value.__enter__.return_value.height = 20
        response = MagicMock()
        response.read.return_value = json.dumps({"response": "{\"regions\": []}"}).encode()
        urlopen.return_value.__enter__.return_value = response
        with generation_options(DETERMINISTIC_BENCHMARK_OPTIONS):
            call_vision_model("page.jpg", "prompt")
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["options"], DETERMINISTIC_BENCHMARK_OPTIONS)

    @patch("app.services.ollama_vision.Image.open")
    @patch("app.services.ollama_vision.urllib.request.urlopen")
    @patch("builtins.open")
    def test_truncated_json_is_rejected(self, file_open, urlopen, image_open):
        file_open.return_value.__enter__.return_value.read.return_value = b"image"
        image_open.return_value.__enter__.return_value.width = 10
        image_open.return_value.__enter__.return_value.height = 20
        response = MagicMock()
        response.read.return_value = json.dumps({"response": '{"items":['}).encode()
        urlopen.return_value.__enter__.return_value = response
        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            call_vision_model("page.jpg", "prompt", json_mode=True)


class FingerprintTests(unittest.TestCase):
    def test_prompt_fingerprint_is_stable(self):
        self.assertEqual(stable_text_hash("same prompt"), stable_text_hash("same prompt"))
        self.assertNotEqual(stable_text_hash("same prompt"), stable_text_hash("other prompt"))

    def test_asset_fingerprint_is_content_based(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jpg"
            second = Path(directory) / "renamed.jpg"
            first.write_bytes(b"same image")
            second.write_bytes(b"same image")
            self.assertEqual(stable_file_hash(first), stable_file_hash(second))

    def test_production_package_does_not_import_correctness_snapshot(self):
        app_root = Path(__file__).resolve().parents[1] / "app"
        contents = "\n".join(path.read_text() for path in app_root.rglob("*.py"))
        self.assertNotIn("vision_correctness.v1.json", contents)

    def test_vision_benchmark_runner_has_no_database_mutation(self):
        runner = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_vision_stability.py"
        source = runner.read_text()
        self.assertNotIn(".commit(", source)
        self.assertNotIn(".delete(", source)
        self.assertNotIn(".add(", source)


if __name__ == "__main__":
    unittest.main()
