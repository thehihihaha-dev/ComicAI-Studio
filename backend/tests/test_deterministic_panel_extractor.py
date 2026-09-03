import inspect
import json
import unittest
from pathlib import Path

import cv2
import numpy as np

from app.services.deterministic_panel_extractor import PanelConfig, _contours, extract_panels

ROOT = Path(__file__).resolve().parents[2]


def canvas(width=400, height=500):
    return np.full((height, width, 3), 255, dtype=np.uint8)


def frame(image, box, thickness=5, missing=None):
    x1, y1, x2, y2 = box
    if missing != "top": cv2.line(image, (x1, y1), (x2, y1), (0, 0, 0), thickness)
    if missing != "bottom": cv2.line(image, (x1, y2), (x2, y2), (0, 0, 0), thickness)
    if missing != "left": cv2.line(image, (x1, y1), (x1, y2), (0, 0, 0), thickness)
    if missing != "right": cv2.line(image, (x2, y1), (x2, y2), (0, 0, 0), thickness)


class DeterministicPanelExtractorTests(unittest.TestCase):
    def assert_detects(self, image, minimum=1):
        result = extract_panels(image)
        self.assertGreaterEqual(result["detected_panel_count"], minimum)
        self.assertFalse(any(panel["bbox"] == [0, 0, image.shape[1], image.shape[0]] for panel in result["panels"]))
        return result

    def test_2x2_grid_and_repeat_are_deterministic(self):
        image = canvas()
        for box in ([10, 10, 190, 240], [210, 10, 390, 240], [10, 260, 190, 490], [210, 260, 390, 490]):
            frame(image, box)
        first, second = extract_panels(image), extract_panels(image)
        self.assertEqual(first, second)
        self.assert_detects(image, 4)

    def test_right_left_and_upper_lower(self):
        horizontal = canvas()
        frame(horizontal, [5, 5, 190, 495]); frame(horizontal, [210, 5, 395, 495])
        vertical = canvas()
        frame(vertical, [5, 5, 395, 240]); frame(vertical, [5, 260, 395, 495])
        self.assert_detects(horizontal, 2)
        self.assert_detects(vertical, 2)

    def test_tall_beside_stacked_and_adjacency(self):
        image = canvas()
        frame(image, [5, 5, 190, 495]); frame(image, [210, 5, 395, 240]); frame(image, [210, 260, 395, 495])
        result = self.assert_detects(image, 3)
        self.assertTrue(result["adjacency"])

    def test_narrow_gutter(self):
        image = canvas()
        frame(image, [3, 3, 193, 497]); frame(image, [207, 3, 397, 497])
        self.assert_detects(image, 2)

    def test_missing_page_facing_border_is_completed_on_every_edge(self):
        cases = {
            "LEFT": ([0, 20, 280, 300], "left"),
            "RIGHT": ([120, 20, 400, 300], "right"),
            "TOP": ([60, 0, 340, 300], "top"),
            "BOTTOM": ([60, 200, 340, 500], "bottom"),
        }
        for expected_edge, (box, missing) in cases.items():
            with self.subTest(edge=expected_edge):
                image = canvas()
                frame(image, box, missing=missing)
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
                self.assertFalse(any(item["bbox"] == box for item in _contours(gray, PanelConfig())))
                first, second = extract_panels(image), extract_panels(image)
                self.assertEqual(first, second)
                completed = [panel for panel in first["panels"]
                             if panel.get("page_edge_completion", {}).get("completed_edge") == expected_edge]
                self.assertTrue(completed)
                panel = completed[0]
                self.assertEqual(panel["state"], "DETECTED")
                self.assertIn("page_edge_completion", panel["provenance"])
                edge_index = {"LEFT": 0, "TOP": 1, "RIGHT": 2, "BOTTOM": 3}[expected_edge]
                self.assertEqual(panel["bbox"][edge_index], box[edge_index])
                self.assertTrue(all(abs(actual - expected) <= 6 for actual, expected in zip(panel["bbox"], box)))

    def test_weak_page_edge_content_is_not_completed(self):
        image = canvas()
        cv2.line(image, (0, 40), (180, 40), (0, 0, 0), 5)
        cv2.line(image, (0, 150), (80, 240), (0, 0, 0), 5)
        result = extract_panels(image)
        self.assertFalse(any(panel["state"] == "DETECTED" and "page_edge_completion" in panel["provenance"]
                             for panel in result["panels"]))

    def test_missing_border_remains_ambiguous_or_unresolved(self):
        image = canvas()
        frame(image, [20, 20, 380, 470], missing="right")
        result = extract_panels(image)
        self.assertTrue(result["unresolved"] or result["ambiguous_panel_count"] > 0)

    def test_overlapping_structure_is_ambiguous(self):
        image = canvas()
        frame(image, [20, 20, 270, 330]); frame(image, [130, 150, 380, 470])
        result = extract_panels(image)
        self.assertGreater(result["ambiguous_panel_count"], 0)

    def test_full_page_and_tiny_bubble_like_candidates_are_rejected(self):
        image = canvas()
        frame(image, [0, 0, 399, 499]); frame(image, [170, 220, 220, 260])
        result = extract_panels(image)
        self.assertEqual(result["detected_panel_count"], 0)

    def test_provenance_ids_and_duplicate_suppression(self):
        image = canvas()
        frame(image, [10, 10, 390, 240]); frame(image, [10, 260, 390, 490])
        result = self.assert_detects(image, 2)
        self.assertTrue(all(panel["panel_id"].startswith("PN_") and panel["provenance"] for panel in result["panels"]))
        self.assertGreaterEqual(result["duplicate_candidates_suppressed"], 1)

    def test_pixels_only_api_and_gt_isolation(self):
        signature = inspect.signature(extract_panels)
        self.assertEqual(list(signature.parameters), ["image", "config"])
        result = extract_panels(canvas(), PanelConfig())
        self.assertEqual(result["gt_runtime_features"], [])


class PanelExtractionArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        day12 = ROOT / "benchmarks/day12"
        cls.audit = json.loads((day12 / "panel-extraction-input-audit-12.2.json").read_text())
        cls.protocol = json.loads((day12 / "panel-extraction-protocol-12.2.json").read_text())
        cls.predictions = json.loads((day12 / "panel-predictions-12.2.json").read_text())
        cls.metrics = json.loads((day12 / "panel-structural-metrics-12.2.json").read_text())
        cls.diagnostics = json.loads((day12 / "panel-page-15-17-diagnostics-12.2.json").read_text())
        cls.summary = json.loads((day12 / "panel-extraction-summary-12.2.json").read_text())

    def test_ten_hash_verified_pages_and_no_gt_runtime_features(self):
        self.assertEqual(len(self.audit["inputs"]), 10)
        self.assertTrue(all(item["hash_verified"] for item in self.audit["inputs"]))
        self.assertEqual(self.audit["gt_runtime_features"], [])
        self.assertEqual(self.protocol["gt_runtime_features"], [])
        self.assertEqual(self.predictions["gt_runtime_features"], [])

    def test_prediction_and_metrics_reconcile(self):
        pages = self.predictions["pages"]
        self.assertEqual(len(pages), 10)
        self.assertEqual(sum(page["detected_panel_count"] for page in pages), self.metrics["detected_panels"])
        self.assertEqual(sum(page["ambiguous_panel_count"] for page in pages), self.metrics["ambiguous_panels"])
        self.assertEqual(sum(page["unresolved"] for page in pages), self.metrics["unresolved_pages"])
        self.assertEqual(sum(self.metrics["logical_region_counts"].values()), 63)
        self.assertEqual(self.metrics["panel_precision"], "N/A: no independent panel GT")

    def test_freeze_precedes_page_diagnostics(self):
        self.assertEqual(self.predictions["prediction_stage"], "FROZEN_BEFORE_MANUAL_DIAGNOSTICS")
        self.assertEqual(len(self.diagnostics["pages"]), 2)
        self.assertEqual({page["page_order"] for page in self.diagnostics["pages"]}, {15, 17})
        self.assertTrue(all(page["status"] in {"SEPARATED", "NOT_SEPARATED", "AMBIGUOUS", "UNRESOLVED"}
                            for page in self.diagnostics["pages"]))

    def test_outcome_and_resource_contract(self):
        self.assertIn(self.summary["outcome"], {
            "A. DETERMINISTIC PANEL EXTRACTION IS VIABLE",
            "B. PARTIAL PANEL EXTRACTION — SPECIFIC FAILURE CLASSES REMAIN",
            "C. DETERMINISTIC PANEL EXTRACTION IS INSUFFICIENT",
            "D. PANEL CORRECTNESS CANNOT BE EVALUATED YET",
        })
        self.assertEqual(self.summary["resources"]["resource_guard"], "NORMAL")
        self.assertEqual(self.summary["model_calls"], {"ocr": 0, "vlm": 0, "ollama": 0})


if __name__ == "__main__":
    unittest.main()
