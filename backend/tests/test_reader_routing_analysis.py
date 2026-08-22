import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from reader_routing_analysis import (  # noqa: E402
    accept, cache_reusable, language_hint, normalized_similarity, routing_metrics, sanity_flags,
)


class ReaderRoutingAnalysisTests(unittest.TestCase):
    def sample(self, sample_id="a", easy_cer=0.0, paddle_cer=0.0):
        return {"sample_id": sample_id, "similarity": .95, "sanity_flags": [],
                "easyocr": {"confidence": .9, "normalized_cer": easy_cer},
                "paddleocr": {"confidence": .8, "normalized_cer": paddle_cer}}

    def test_normalized_similarity(self):
        self.assertEqual(normalized_similarity(" TÔI ", "tôi"), 1.0)
        self.assertAlmostEqual(normalized_similarity("abc", "axc"), 2 / 3)

    def test_false_safe_precision_and_hard_metrics(self):
        samples = [self.sample("a", easy_cer=0), self.sample("b", easy_cer=.2)]
        result = routing_metrics(samples, {"a", "b"}, "easyocr", 0.0)
        self.assertEqual(result["false_safe_count"], 1)
        self.assertEqual(result["false_safe_rate"], .5)
        self.assertEqual(result["safe_accept_rate"], .5)
        self.assertEqual(result["easy_precision"], .5)
        self.assertEqual(result["hard_rate"], 0)

    def test_threshold_router_and_sanity(self):
        sample = self.sample()
        self.assertTrue(accept({"kind": "agreement_confidence", "engine": "paddleocr", "similarity": .9, "confidence": .8}, sample))
        sample["sanity_flags"] = ["empty"]
        self.assertFalse(accept({"kind": "combined_sanity", "engine": "paddleocr", "similarity": .9, "confidence": .8}, sample))
        self.assertIn("empty", sanity_flags(""))
        self.assertIn("repeated_character_pattern", sanity_flags("aaaa"))
        self.assertEqual(language_hint("Tôi"), "vi")
        self.assertEqual(language_hint("Hello"), "unknown")

    def test_cache_reuse_requires_exact_key_and_reuse_status(self):
        self.assertTrue(cache_reusable("x", {"cache_key": "x", "cache_status": "CACHED"}))
        self.assertFalse(cache_reusable("x", {"cache_key": "x", "cache_status": "measured_this_run"}))
        self.assertFalse(cache_reusable("x", {"cache_key": "y", "cache_status": "CACHED"}))


if __name__ == "__main__": unittest.main()
