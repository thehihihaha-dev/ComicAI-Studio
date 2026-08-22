import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from reader_benchmark import result_json  # noqa: E402
from reader_benchmark_11_4 import cache_key, evaluate, language_of, tags_for, validate_artifact, SCHEMA  # noqa: E402


class FakeResult:
    json = {"res": {"rec_text": "Hây", "rec_score": 0.8}}


class ReaderBenchmark114Tests(unittest.TestCase):
    def test_paddle_adapter_result_shape(self):
        self.assertEqual(result_json(FakeResult())["rec_text"], "Hây")

    def test_cache_key_is_stable_and_configuration_sensitive(self):
        sample = {"image_sha256": "abc", "bbox": [1, 2, 3, 4]}
        self.assertEqual(cache_key(sample, "easyocr", "1", "gray"),
                         cache_key(sample, "easyocr", "1", "gray"))
        self.assertNotEqual(cache_key(sample, "easyocr", "1", "gray"),
                            cache_key(sample, "easyocr", "1", "rgb"))

    def test_evaluation_and_metadata_are_deterministic(self):
        result = evaluate("Tôi!", "Toi", 0.91)
        self.assertEqual(result["confidence_bucket"], "0.90-0.95")
        self.assertIn("SUBSTITUTION", result["error_types"])
        self.assertEqual(language_of("Tôi"), "vi")
        self.assertIn("multiline", tags_for("Tôi!", 2))

    def test_11_4_schema(self):
        validate_artifact({"schema_version": SCHEMA, "checkpoint": "11.4",
                           "artifact_kind": "comparison", "status": "completed"})
        with self.assertRaises(ValueError):
            validate_artifact({"schema_version": SCHEMA, "checkpoint": "11.3",
                               "artifact_kind": "comparison", "status": "completed"})


if __name__ == "__main__":
    unittest.main()
