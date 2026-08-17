import unittest
from unittest.mock import patch

from app.services.vision_analyzer import analyze_comic_page, recover_dialogue_regions


OCR_BLOCKS = [{"text": "HELLO", "confidence": 0.99, "box": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
VALID_LAYOUT = {"regions": [{"id": 1, "type": "speech_bubble", "block_ids": [0]}], "reading_order": [1]}


class ReadingOrderReuseTests(unittest.TestCase):
    @patch("app.services.vision_analyzer.analyze_reading_order")
    @patch("app.services.vision_analyzer.call_vision_model")
    def test_layout_reading_order_avoids_fallback(self, call_model, analyze_order):
        call_model.return_value = VALID_LAYOUT
        result = analyze_comic_page("page.jpg", OCR_BLOCKS)
        analyze_order.assert_not_called()
        self.assertEqual(result["vision_result"]["reading_order"], [1])

    @patch("app.services.vision_analyzer.analyze_reading_order", return_value=[1])
    @patch("app.services.vision_analyzer.call_vision_model")
    def test_invalid_layout_reading_order_uses_fallback(self, call_model, analyze_order):
        call_model.return_value = {**VALID_LAYOUT, "reading_order": [999]}
        result = analyze_comic_page("page.jpg", OCR_BLOCKS)
        analyze_order.assert_called_once()
        self.assertEqual(result["vision_result"]["reading_order"], [1])


class VisionRecoverySafetyTests(unittest.TestCase):
    @patch("app.services.vision_analyzer.create_recovery_crops", return_value=[
        {"candidate_id": 1, "block_ids": [0], "crop_path": "one.jpg"},
        {"candidate_id": 2, "block_ids": [1], "crop_path": "two.jpg"},
    ])
    @patch("app.services.vision_analyzer.call_vision_model")
    def test_multiple_candidates_keep_independent_crop_validation(self, call_model, _create_crops):
        call_model.side_effect = [
            {"is_dialogue_region": True, "type": "speech_bubble", "block_ids": [0], "confidence": 0.9},
            {"is_dialogue_region": True, "type": "speech_bubble", "block_ids": [1], "confidence": 0.9},
        ]
        blocks = [
            {"text": "A", "confidence": 0.9, "box": [[0, 0], [1, 0], [1, 1], [0, 1]]},
            {"text": "B", "confidence": 0.9, "box": [[500, 500], [501, 500], [501, 501], [500, 501]]},
        ]
        result = recover_dialogue_regions("page.jpg", blocks, {"missing_block_ids": [0, 1]})
        self.assertEqual(call_model.call_count, 2)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
