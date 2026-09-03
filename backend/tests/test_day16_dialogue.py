"""Unit tests for Day 16 Phase 1: Contextual Dialogue Polishing & Speaker Diarization.

Verifies:
1. 50/50 dialogue preservation (length, IDs, and spatial keys invariant).
2. Grounded speaker assignment accuracy (Page 1 PRIEST/RIN, Page 5 NARRATOR/RIN/KAZU).
3. Exact determinism across 10 repeated polishing & diarization runs.
"""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day16_dialogue import (
    LLMDialoguePolisher,
    SpeakerDiarizer,
    SpeakerRole,
)


class Day16DialogueTests(unittest.TestCase):

    def setUp(self):
        self.polisher = LLMDialoguePolisher()
        self.diarizer = SpeakerDiarizer()

        script_path = ROOT / "benchmarks" / "day15" / "dialogue_script.json"
        self.script_doc = json.loads(script_path.read_text(encoding="utf-8"))
        self.dialogues = self.script_doc["dialogues"]

    def test_dialogue_preservation_invariant(self):
        """Must preserve all 50 dialogues with exact IDs, pages, panels, and reading order indices."""
        polished = self.polisher.polish_dialogues(self.dialogues)
        diarized = self.diarizer.assign_speakers(polished)

        self.assertEqual(len(diarized), 50)
        self.assertEqual(len(diarized), len(self.dialogues))

        for orig, res in zip(self.dialogues, diarized):
            self.assertEqual(orig["dialogue_id"], res["dialogue_id"])
            self.assertEqual(orig["page_id"], res["page_id"])
            self.assertEqual(orig["panel_id"], res["panel_id"])
            self.assertEqual(orig["reading_order_index"], res["reading_order_index"])
            self.assertEqual(orig["bbox"], res["bbox"])
            self.assertIn("tts_ready_text", res)
            self.assertGreater(len(res["tts_ready_text"]), 0)
            self.assertIn("speaker_label", res)
            self.assertNotEqual(res["speaker_label"], "")

    def test_specific_speaker_assignments_page_1_and_5(self):
        """Page 1 and Page 5 speaker roles must match character and scene context."""
        polished = self.polisher.polish_dialogues(self.dialogues)
        diarized = self.diarizer.assign_speakers(polished)
        d_map = {d["dialogue_id"]: d for d in diarized}

        # Page 1: Priest officiating vows, Rin answering
        self.assertEqual(d_map["D_P01_01"]["speaker_label"], SpeakerRole.PRIEST.value)
        self.assertEqual(d_map["D_P01_02"]["speaker_label"], SpeakerRole.PRIEST.value)
        self.assertEqual(d_map["D_P01_03"]["speaker_label"], SpeakerRole.PRIEST.value)
        self.assertEqual(d_map["D_P01_04"]["speaker_label"], SpeakerRole.RIN.value)

        # Page 5: Retrospective narration, Rin introducing, Kazu instructing
        self.assertEqual(d_map["D_P05_01"]["speaker_label"], SpeakerRole.NARRATOR.value)
        self.assertEqual(d_map["D_P05_02"]["speaker_label"], SpeakerRole.RIN.value)
        self.assertEqual(d_map["D_P05_03"]["speaker_label"], SpeakerRole.RIN.value)
        self.assertEqual(d_map["D_P05_04"]["speaker_label"], SpeakerRole.NARRATOR.value)
        self.assertEqual(d_map["D_P05_05"]["speaker_label"], SpeakerRole.NARRATOR.value)
        self.assertEqual(d_map["D_P05_06"]["speaker_label"], SpeakerRole.NARRATOR.value)
        self.assertEqual(d_map["D_P05_07"]["speaker_label"], SpeakerRole.KAZU.value)
        self.assertEqual(d_map["D_P05_08"]["speaker_label"], SpeakerRole.RIN.value)

    def test_determinism_10_runs(self):
        """Polishing and diarization across 10 runs must produce identical SHA-256 digests."""
        def run_once():
            polished = self.polisher.polish_dialogues(self.dialogues)
            diarized = self.diarizer.assign_speakers(polished)
            serialized = json.dumps(diarized, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        base_hash = run_once()
        for _ in range(9):
            self.assertEqual(run_once(), base_hash, "Nondeterministic dialogue processing detected!")


if __name__ == "__main__":
    unittest.main()

