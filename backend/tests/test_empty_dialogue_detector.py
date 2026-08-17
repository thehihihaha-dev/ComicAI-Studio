import inspect
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from app.services import empty_dialogue_detector
from app.services.dialogue_structure_recovery import (
    enforce_recovered_region_review,
    insert_recovered_region,
)
from app.services.empty_dialogue_detector import (
    detect_empty_dialogue_candidates,
    merge_duplicate_candidates,
    run_local_candidate_ocr,
)


class EmptyDialogueDetectorTests(unittest.TestCase):
    def make_image(self, strokes=True, bubble=False):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "page.png"
        image = Image.new("L", (300, 1280), 255)
        if strokes:
            draw = ImageDraw.Draw(image)
            if bubble:
                draw.ellipse((70, 460, 155, 550), outline=0, width=2)
            for index in range(6):
                left = 100 + index * 4
                draw.rectangle((left, 500, left, 507), fill=0)
        image.save(path)
        return directory, path

    def test_blank_white_region_rejected(self):
        directory, path = self.make_image(strokes=False)
        try:
            self.assertEqual(detect_empty_dialogue_candidates(str(path), [])["candidates"], [])
        finally:
            directory.cleanup()

    def test_text_like_candidate_accepted_and_bbox_stable(self):
        directory, path = self.make_image()
        try:
            first = detect_empty_dialogue_candidates(str(path), [])
            second = detect_empty_dialogue_candidates(str(path), [])
            self.assertEqual(first["candidates"], second["candidates"])
            self.assertEqual(len(first["candidates"]), 1)
            self.assertIn("text_like_strokes", first["candidates"][0]["evidence"])
        finally:
            directory.cleanup()

    def test_bubble_like_candidate_with_text_strokes_accepted(self):
        directory, path = self.make_image(bubble=True)
        try:
            self.assertEqual(
                len(detect_empty_dialogue_candidates(str(path), [])["candidates"]),
                1,
            )
        finally:
            directory.cleanup()

    def test_ocr_overlapping_candidate_filtered(self):
        directory, path = self.make_image()
        try:
            ocr = [{"text": "known", "box": [[90, 490], [140, 490], [140, 530], [90, 530]]}]
            self.assertEqual(detect_empty_dialogue_candidates(str(path), ocr)["candidates"], [])
        finally:
            directory.cleanup()

    def test_duplicate_candidates_rejected(self):
        candidates = [
            {"bbox": [0, 0, 20, 20], "confidence": 0.9},
            {"bbox": [1, 1, 21, 21], "confidence": 0.8},
        ]
        self.assertEqual(len(merge_duplicate_candidates(candidates)), 1)

    def test_recovered_region_provenance_and_geometric_insertion(self):
        blocks = [
            {"text": "later", "box": [[100, 100], [130, 100], [130, 120], [100, 120]]}
        ]
        result = insert_recovered_region(
            {"regions": [{"id": 1, "block_ids": [0]}], "reading_order": [1]},
            blocks,
            {
                "bbox": [20, 100, 60, 120],
                "text": "new",
                "confidence": 0.7,
                "needs_review": True,
                "region_source": "vision_ocr_recovery",
                "candidate_id": "candidate-1",
            },
        )
        self.assertEqual(result["reading_order"], [2, 1])
        self.assertEqual(result["regions"][-1]["region_source"], "vision_ocr_recovery")
        self.assertEqual(result["regions"][0], {"id": 1, "block_ids": [0]})
        self.assertEqual(blocks[-1]["source"], "vision_ocr_recovery")
        self.assertTrue(blocks[-1]["needs_review"])

    def test_production_detector_never_imports_audit_snapshot(self):
        source = inspect.getsource(empty_dialogue_detector)
        self.assertNotIn("dialogue_recall_audit", source)
        self.assertNotIn("benchmarks/", source)
        self.assertNotIn("Hãy", source)

    def test_low_confidence_recovered_region_stays_in_review(self):
        dialogues = [
            {"region_id": 1, "decision": "auto_recovered", "needs_review": False},
            {"region_id": 8, "decision": "auto_recovered", "needs_review": False},
        ]
        regions = [
            {
                "id": 8,
                "region_source": "vision_ocr_recovery",
                "needs_review": True,
            }
        ]
        result = enforce_recovered_region_review(dialogues, regions)
        self.assertEqual(result[0]["decision"], "auto_recovered")
        self.assertFalse(result[0]["needs_review"])
        self.assertEqual(result[1]["decision"], "needs_review")
        self.assertTrue(result[1]["needs_review"])

    def test_local_ocr_success_without_real_model(self):
        directory, path = self.make_image()

        class Reader:
            def readtext(self, _image, detail):
                self.detail = detail
                return [([], "TEST", 0.91)]

        try:
            result = run_local_candidate_ocr(str(path), [80, 480, 150, 530], Reader())
            self.assertEqual(result["text"], "TEST")
            self.assertTrue(result["usable"])
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()
