"""Unit tests for Day 17 Phase 1: Real Voice Synthesis Generation & Audio Artifact Persistence.

Verifies:
1. LiveTTSGenerator offline fallback produces non-zero valid MP3 files with accurate length.
2. PageAudioStitcher correctly concatenates audio clips with silence frames.
3. Physical duration matching modeled duration within reasonable variance.
"""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

import mutagen.mp3
from src.pipeline.research.day17_live_tts import (
    LiveTTSGenerator,
    PageAudioStitcher,
    generate_mp3_silence,
)


class Day17LiveTTSTests(unittest.TestCase):

    def setUp(self):
        self.generator = LiveTTSGenerator(offline_fallback=True)
        self.stitcher = PageAudioStitcher(pause_between_bubbles_ms=150, pause_between_panels_ms=300)

    def test_offline_fallback_synthesis(self):
        """Offline fallback must create valid MP3 files with non-zero bytes and exact expected duration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "test_bubble.mp3"

            # In an offline environment or forced fallback
            duration_sec = asyncio.run(
                self.generator.synthesize_bubble(
                    text="Thử nghiệm âm thanh dự phòng",
                    voice_id="vi-VN-NamMinhNeural",
                    output_path=out_path,
                    fallback_duration_ms=1200,
                )
            )

            self.assertTrue(out_path.is_file())
            self.assertGreater(out_path.stat().st_size, 0)

            # Read via mutagen
            audio = mutagen.mp3.MP3(str(out_path))
            self.assertGreater(audio.info.length, 0.5)
            # Duration should be within 50ms of 1.2s
            self.assertAlmostEqual(duration_sec, 1.2, delta=0.05)

    def test_page_audio_stitching_with_pauses(self):
        """PageAudioStitcher must concatenate clips and insert silence pauses accurately."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()

            # Create 2 test clips
            c1_path = raw_dir / "D_P01_01.mp3"
            c2_path = raw_dir / "D_P01_02.mp3"
            c1_path.write_bytes(generate_mp3_silence(1000))  # ~1.0s
            c2_path.write_bytes(generate_mp3_silence(2000))  # ~2.0s

            bubbles = [
                {"dialogue_id": "D_P01_01", "panel_id": "PAN_1"},
                {"dialogue_id": "D_P01_02", "panel_id": "PAN_2"},  # different panel -> 300ms pause
            ]

            preview_path = tmp_path / "page_01_preview.mp3"
            total_sec = self.stitcher.stitch_page_audio(bubbles, raw_dir, preview_path)

            self.assertTrue(preview_path.is_file())
            self.assertGreater(preview_path.stat().st_size, 0)

            # Expected: 1.0s + 0.3s (inter-panel pause) + 2.0s = ~3.3s
            self.assertAlmostEqual(total_sec, 3.3, delta=0.1)

    def test_silence_frame_generator_precision(self):
        """generate_mp3_silence must produce multiple of 144 bytes matching requested duration."""
        silence_150ms = generate_mp3_silence(150)
        # 150 / 24 = 6.25 -> 6 frames * 144 = 864 bytes
        self.assertEqual(len(silence_150ms) % 144, 0)
        self.assertEqual(len(silence_150ms), 6 * 144)

        silence_300ms = generate_mp3_silence(300)
        # 300 / 24 = 12.5 -> 12 or 13 frames * 144
        expected_frames = int(round(300 / 24.0))
        self.assertEqual(len(silence_300ms) % 144, 0)
        self.assertEqual(len(silence_300ms), expected_frames * 144)


if __name__ == "__main__":
    unittest.main()

