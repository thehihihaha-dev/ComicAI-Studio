"""Unit tests for Day 16 Phase 2: Pluggable TTS Synthesis & Timeline Alignment Engine.

Verifies:
1. Monotonic timeline integrity: end_ms > start_ms and zero speech overlap within every page.
2. Voice profile assignment parity per SpeakerRole.
3. 100% Determinism across 10 repeated timeline alignment runs.
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

from src.pipeline.research.day16_dialogue import SpeakerRole
from src.pipeline.research.day16_tts import (
    TimelineAligner,
    VoiceSynthesisEngine,
)


class Day16TTSTests(unittest.TestCase):

    def setUp(self):
        self.engine = VoiceSynthesisEngine()
        self.aligner = TimelineAligner(pause_between_bubbles_ms=350, pause_between_panels_ms=700)

        polished_path = ROOT / "benchmarks" / "day16" / "day16-polished-dialogues.json"
        self.polished_doc = json.loads(polished_path.read_text(encoding="utf-8"))
        self.dialogues = self.polished_doc["dialogues"]

    def test_monotonic_timeline_and_zero_speech_overlap(self):
        """Within each page, end_ms > start_ms and start_ms[i+1] >= end_ms[i] + pause."""
        pages_map: dict[int, list[dict]] = {}
        for d in self.dialogues:
            pages_map.setdefault(d["page_id"], []).append(d)

        total_aligned_bubbles = 0

        for p_num, page_bubbles in pages_map.items():
            aligned = self.aligner.align_page_dialogues(page_bubbles, self.engine)
            self.assertEqual(len(aligned), len(page_bubbles))
            total_aligned_bubbles += len(aligned)

            for i, d in enumerate(aligned):
                self.assertGreater(d["duration_ms"], 0)
                self.assertGreater(d["end_ms"], d["start_ms"])
                self.assertEqual(d["end_ms"], d["start_ms"] + d["duration_ms"])

                if i > 0:
                    prev = aligned[i - 1]
                    expected_min_gap = (
                        self.aligner.pause_between_bubbles_ms
                        if d["panel_id"] == prev["panel_id"]
                        else self.aligner.pause_between_panels_ms
                    )
                    actual_gap = d["start_ms"] - prev["end_ms"]
                    self.assertGreaterEqual(
                        actual_gap,
                        expected_min_gap,
                        f"Speech overlap on page {p_num} between dialogue {prev['dialogue_id']} and {d['dialogue_id']}",
                    )

        self.assertEqual(total_aligned_bubbles, 50)

    def test_voice_assignment_parity(self):
        """Each speaker role must map to its designated voice profile."""
        kazu_prof = self.engine.get_profile(SpeakerRole.KAZU)
        rin_prof = self.engine.get_profile(SpeakerRole.RIN)
        priest_prof = self.engine.get_profile(SpeakerRole.PRIEST)
        narrator_prof = self.engine.get_profile(SpeakerRole.NARRATOR)

        self.assertEqual(kazu_prof.voice_id, "vi-VN-NamMinhNeural")
        self.assertEqual(kazu_prof.gender, "male")

        self.assertEqual(rin_prof.voice_id, "vi-VN-HoaiMyNeural")
        self.assertEqual(rin_prof.gender, "female")

        self.assertEqual(priest_prof.voice_id, "vi-VN-NamMinhNeural")
        self.assertEqual(priest_prof.rate, "-10%")

        self.assertEqual(narrator_prof.voice_id, "vi-VN-NamMinhNeural")

    def test_determinism_10_runs(self):
        """Repeated alignment across 10 runs must produce identical SHA-256 digests."""
        def run_once():
            pages_map: dict[int, list[dict]] = {}
            for d in self.dialogues:
                pages_map.setdefault(d["page_id"], []).append(d)

            all_aligned = []
            for p_num in sorted(pages_map.keys()):
                aligned = self.aligner.align_page_dialogues(pages_map[p_num], self.engine)
                all_aligned.extend(aligned)

            serialized = json.dumps(all_aligned, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        base_hash = run_once()
        for _ in range(9):
            self.assertEqual(run_once(), base_hash, "Nondeterministic audio alignment detected!")


if __name__ == "__main__":
    unittest.main()

