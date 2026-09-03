import unittest

from app.services.panel_correctness_evaluator import evaluate_page, one_to_one_matches


def panel(panel_id, bbox, state="DETECTED"):
    return {"panel_id": panel_id, "bbox": bbox, "state": state}


class PanelCorrectnessEvaluatorTests(unittest.TestCase):
    def test_one_to_one_maximizes_cardinality_then_iou_deterministically(self):
        truths = [panel("h1", [0, 0, 100, 100]), panel("h2", [100, 0, 200, 100])]
        predictions = [panel("p-wide", [0, 0, 200, 100]), panel("p-left", [0, 0, 100, 100])]
        first = one_to_one_matches(predictions, truths, 0.5)
        self.assertEqual(first, one_to_one_matches(list(reversed(predictions)), list(reversed(truths)), 0.5))
        self.assertEqual({match["human_panel_id"] for match in first}, {"h1", "h2"})

    def test_duplicate_predictions_cannot_match_one_truth_twice(self):
        truth = [panel("h", [0, 0, 100, 100])]
        predictions = [panel("p1", [0, 0, 100, 100]), panel("p2", [0, 0, 100, 100])]
        matches = one_to_one_matches(predictions, truth, 0.5)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["prediction_id"], "p1")

    def test_detected_and_ambiguous_are_not_combined(self):
        page = {"page_order": 1, "unresolved": False, "panels": [
            panel("det", [0, 0, 100, 100]), panel("amb", [100, 0, 200, 100], "AMBIGUOUS")]}
        result = evaluate_page(page, [panel("h1", [0, 0, 100, 100]), panel("h2", [100, 0, 200, 100])])
        self.assertEqual(result["matched_true_panels_detected"], 1)
        self.assertEqual(result["human_panels_recoverable_in_ambiguous"], 1)

    def test_under_and_over_split_relations(self):
        truths = [panel("h1", [0, 0, 100, 100]), panel("h2", [100, 0, 200, 100])]
        page = {"page_order": 1, "unresolved": True, "panels": [
            panel("wide", [0, 0, 200, 100], "AMBIGUOUS"),
            panel("left-a", [0, 0, 50, 100], "AMBIGUOUS"),
            panel("left-b", [50, 0, 100, 100], "AMBIGUOUS")]}
        result = evaluate_page(page, truths)
        self.assertEqual(result["under_splitting"][0]["prediction_id"], "wide")
        self.assertEqual(result["over_splitting"][0]["human_panel_id"], "h1")
        wide_match = next(match for match in result["ambiguous_matches"] if match["prediction_id"] == "wide")
        self.assertFalse(wide_match["structurally_clean"])

    def test_threshold_boundary_is_inclusive(self):
        matches = one_to_one_matches([panel("p", [0, 0, 200, 100])], [panel("h", [0, 0, 100, 100])], 0.5)
        self.assertEqual(matches[0]["iou"], 0.5)


if __name__ == "__main__":
    unittest.main()
