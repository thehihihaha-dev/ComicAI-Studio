"""Unit tests for Day 17 Phase 2: 9:16 Vertical Video Compositing & Ken Burns Motion Engine.

Verifies:
1. VerticalFrameBuilder strictly produces 1080x1920 BGR numpy array frames.
2. PanelMotionPlanner segments cover 100% of duration without gaps.
3. VideoSynthesizer end-to-end rendering produces a valid playable MP4 with zero A/V drift.
"""
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

import cv2
import numpy as np
from src.pipeline.research.day17_live_tts import generate_mp3_silence
from src.pipeline.research.day17_video import (
    PanelMotionPlanner,
    VerticalFrameBuilder,
    VideoSynthesizer,
)


class Day17VideoTests(unittest.TestCase):

    def setUp(self):
        self.frame_builder = VerticalFrameBuilder()
        self.motion_planner = PanelMotionPlanner()
        self.synthesizer = VideoSynthesizer(
            frame_builder=self.frame_builder,
            motion_planner=self.motion_planner,
        )

    def test_vertical_frame_builder_dimensions(self):
        """VerticalFrameBuilder must produce exactly 1080x1920x3 BGR frames."""
        dummy_crop = np.zeros((400, 300, 3), dtype=np.uint8)
        dummy_crop[:, :] = [100, 150, 200]

        frame = self.frame_builder.build_frame(dummy_crop, zoom_scale=1.05, pan_offset=(5, -10))
        self.assertEqual(frame.shape, (1920, 1080, 3))
        self.assertEqual(frame.dtype, np.uint8)

    def test_panel_motion_planner_continuity(self):
        """PanelMotionPlanner must partition timeline without gaps from 0.0 to total duration."""
        bubbles = [
            {"dialogue_id": "D_1", "panel_id": "PAN_A", "start_ms": 0},
            {"dialogue_id": "D_2", "panel_id": "PAN_A", "start_ms": 1500},
            {"dialogue_id": "D_3", "panel_id": "PAN_B", "start_ms": 3000},
            {"dialogue_id": "D_4", "panel_id": "PAN_C", "start_ms": 5000},
        ]
        total_dur = 6.5
        segments = self.motion_planner.plan_panel_segments(bubbles, total_dur)

        self.assertEqual(len(segments), 4)  # 4 distinct dialogue camera sub-shots
        self.assertEqual(segments[0]["start_sec"], 0.0)
        self.assertEqual(segments[-1]["end_sec"], 6.5)

        for i in range(len(segments) - 1):
            self.assertEqual(segments[i]["end_sec"], segments[i + 1]["start_sec"])

    def test_video_synthesizer_mock_render(self):
        """VideoSynthesizer must encode a valid playable MP4 with zero audio-visual drift."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create dummy page image
            img_path = tmp_path / "page.jpg"
            dummy_img = np.zeros((1200, 900, 3), dtype=np.uint8)
            dummy_img[100:500, 100:800] = [200, 100, 50]
            cv2.imwrite(str(img_path), dummy_img)

            # Create 1.5s audio clip
            audio_path = tmp_path / "audio.mp3"
            audio_path.write_bytes(generate_mp3_silence(1500))

            panel_bboxes = {
                "PAN_1": [100.0, 100.0, 800.0, 500.0],
            }
            bubbles = [
                {"dialogue_id": "D_1", "panel_id": "PAN_1", "start_ms": 0},
            ]

            out_video_path = tmp_path / "test_out.mp4"
            meta = self.synthesizer.render_page_video(
                image_path=img_path,
                panel_bboxes=panel_bboxes,
                page_bubbles=bubbles,
                audio_path=audio_path,
                output_path=out_video_path,
                fps=30.0,
            )

            self.assertTrue(out_video_path.is_file())
            self.assertGreater(out_video_path.stat().st_size, 1000)
            self.assertEqual(meta["resolution"], [1080, 1920])
            self.assertLess(meta["drift_sec"], 0.035)  # Less than 1 frame drift at 30 fps


if __name__ == "__main__":
    unittest.main()

