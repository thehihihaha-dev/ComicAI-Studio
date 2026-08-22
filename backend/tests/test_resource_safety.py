import os
import unittest
from unittest.mock import patch

from app.services.resource_safety import (
    CRITICAL,
    GIB,
    NORMAL,
    WARNING,
    HeavyInferenceGuard,
    HeavyInferenceRejected,
    ResourceThresholds,
    classify_resource_state,
    sample_resources,
)


class ResourceStateTests(unittest.TestCase):
    def setUp(self):
        self.thresholds = ResourceThresholds(
            warning_available_bytes=3 * GIB,
            critical_available_bytes=1 * GIB,
            warning_swap_used_bytes=2 * GIB,
            critical_swap_used_bytes=4 * GIB,
        )

    def test_normal_warning_and_critical_classification(self):
        self.assertEqual(
            classify_resource_state(
                {"system_available_memory_bytes": 8 * GIB, "swap_used_bytes": 0},
                self.thresholds,
            ),
            NORMAL,
        )
        self.assertEqual(
            classify_resource_state(
                {"system_available_memory_bytes": 2 * GIB, "swap_used_bytes": 0},
                self.thresholds,
            ),
            WARNING,
        )
        self.assertEqual(
            classify_resource_state(
                {"system_available_memory_bytes": 8 * GIB, "swap_used_bytes": 4 * GIB},
                self.thresholds,
            ),
            CRITICAL,
        )

    def test_unavailable_optional_metrics_are_not_fabricated(self):
        with (
            patch("app.services.resource_safety._process_rss_bytes", return_value=None),
            patch("app.services.resource_safety._available_memory_bytes", return_value=None),
            patch("app.services.resource_safety._swap_used_bytes", return_value=None),
        ):
            sample = sample_resources(self.thresholds)
        self.assertIsNone(sample["process_rss_bytes"])
        self.assertIsNone(sample["system_available_memory_bytes"])
        self.assertIsNone(sample["swap_used_bytes"])
        self.assertIsNone(sample["temperature_celsius"])
        self.assertEqual(sample["safety_state"], NORMAL)
        self.assertIn("timestamp", sample)
        self.assertIn("process_cpu_seconds", sample)

    def test_thresholds_are_environment_configurable(self):
        environment = {
            "COMICAI_WARNING_AVAILABLE_GIB": "5",
            "COMICAI_CRITICAL_AVAILABLE_GIB": "2",
            "COMICAI_WARNING_SWAP_GIB": "1",
            "COMICAI_CRITICAL_SWAP_GIB": "3",
        }
        with patch.dict(os.environ, environment, clear=False):
            configured = ResourceThresholds.from_environment()
        self.assertEqual(configured.warning_available_bytes, 5 * GIB)
        self.assertEqual(configured.critical_available_bytes, 2 * GIB)
        self.assertEqual(configured.warning_swap_used_bytes, 1 * GIB)
        self.assertEqual(configured.critical_swap_used_bytes, 3 * GIB)


class HeavyInferenceGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = HeavyInferenceGuard()
        self.thresholds = ResourceThresholds()

    @staticmethod
    def sampler(state):
        return lambda thresholds: {
            "safety_state": state,
            "system_available_memory_bytes": 8 * GIB,
            "swap_used_bytes": 0,
        }

    def test_warning_allows_one_call_but_rejects_concurrent_call(self):
        with self.guard.acquire(
            "first", sampler=self.sampler(WARNING), thresholds=self.thresholds
        ):
            self.assertEqual(self.guard.active, 1)
            with self.assertRaises(HeavyInferenceRejected):
                with self.guard.acquire(
                    "second", sampler=self.sampler(WARNING), thresholds=self.thresholds
                ):
                    pass
        self.assertEqual(self.guard.active, 0)

    def test_critical_rejects_before_launch(self):
        with self.assertRaises(HeavyInferenceRejected):
            with self.guard.acquire(
                "critical", sampler=self.sampler(CRITICAL), thresholds=self.thresholds
            ):
                pass
        self.assertEqual(self.guard.active, 0)

    def test_exception_releases_slot_without_deadlock(self):
        with self.assertRaisesRegex(RuntimeError, "inference failed"):
            with self.guard.acquire(
                "failure", sampler=self.sampler(NORMAL), thresholds=self.thresholds
            ):
                raise RuntimeError("inference failed")
        with self.guard.acquire(
            "after-failure", sampler=self.sampler(NORMAL), thresholds=self.thresholds
        ):
            self.assertEqual(self.guard.active, 1)
        self.assertEqual(self.guard.active, 0)


if __name__ == "__main__":
    unittest.main()
