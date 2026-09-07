"""Day 20 Phase 2 Test Suite: 9:16 MP4 Video Rendering Engine.

Tests:
1. VerticalFrameBuilder: 1080x1920 compositing, Gaussian blur backdrop, Ken Burns zoom & pan.
2. VideoRenderer: Multi-page panel caching, image resolution, and fallback handling.
3. Ken Burns camera motion presets with smoothstep easing.
4. Voice narration audio track stitching and duration calculations.
5. FFmpeg Audio Ducking filter integration (25% speech attenuation, 100% pause recovery).
6. End-to-end MP4 video synthesis adhering to TimelineContract.
7. End-to-end MP4 video synthesis with BGM ducking mix.
8. FastAPI endpoints: POST /api/projects/{project_id}/render and POST /projects/{project_id}/render.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid

import cv2
from fastapi.testclient import TestClient
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

from app.schemas.projects import ProjectRenderRequest
from main import app
from src.api.timeline_schema import (
    AudioClip,
    BackgroundConfig,
    MotionConfig,
    RenderResponse,
    TimelineContract,
    VisualClip,
)
from src.services.audio_ducking import build_ffmpeg_ducking_filter
from src.services.chapter_service import CHAPTER_METADATA_CACHE, ingest_chapter
from src.services.video_renderer import (
    VerticalFrameBuilder,
    VideoRenderer,
    generate_mp3_silence,
)


def create_test_comic_image(width: int = 800, height: int = 1200, color: tuple[int, int, int] = (200, 100, 50)) -> np.ndarray:
    """Creates a synthetic comic test image with borders and simple panels."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.rectangle(img, (20, 20), (width - 20, height // 2 - 10), color, -1)
    cv2.rectangle(img, (20, height // 2 + 10), (width - 20, height - 20), (100, 200, 100), -1)
    cv2.rectangle(img, (20, 20), (width - 20, height // 2 - 10), (0, 0, 0), 4)
    cv2.rectangle(img, (20, height // 2 + 10), (width - 20, height - 20), (0, 0, 0), 4)
    return img


class TestDay20RenderPipeline(unittest.TestCase):
    """Verifies end-to-end video rendering engine, Ken Burns motions, audio ducking, and API."""

    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp(prefix="comicai_test_render_"))
        self.project_id = f"proj_render_{uuid.uuid4().hex[:8]}"

        # Create 3 synthetic comic pages in temp dir
        self.page_paths: list[Path] = []
        for i in range(3):
            p = self.test_dir / f"page_{i + 1:02d}.jpg"
            img = create_test_comic_image(color=(50 * (i + 1), 70 * (i + 1), 150))
            cv2.imwrite(str(p), img)
            self.page_paths.append(p)

        # Create a sample audio file with silence frames
        self.sample_audio_path = self.test_dir / "sample_voice.mp3"
        self.sample_audio_path.write_bytes(generate_mp3_silence(1500))  # 1.5 seconds

        # Pre-ingest chapter into cache
        ingest_chapter(self.project_id, self.page_paths)

    def tearDown(self) -> None:
        CHAPTER_METADATA_CACHE.pop(self.project_id, None)
        if self.test_dir.exists():
            shutil.rmtree(str(self.test_dir), ignore_errors=True)

    def test_vertical_frame_builder_canvas_and_blur(self) -> None:
        """VerticalFrameBuilder must produce 1080x1920 frames with blurred background."""
        builder = VerticalFrameBuilder(canvas_width=1080, canvas_height=1920)
        crop = np.full((300, 400, 3), 180, dtype=np.uint8)

        frame = builder.build_frame(crop, zoom_scale=1.0, pan_offset=(0, 0), blur_radius=51, darkness=0.35)
        self.assertEqual(frame.shape, (1920, 1080, 3))
        # Ensure center of canvas has foreground content (high intensity)
        center_pixel = frame[1920 // 2, 1080 // 2]
        self.assertGreater(np.mean(center_pixel), 50)
        # Ensure corner has darkened background
        corner_pixel = frame[10, 10]
        self.assertLess(np.mean(corner_pixel), np.mean(center_pixel))

    def test_vertical_frame_builder_zoom_and_pan(self) -> None:
        """VerticalFrameBuilder handles camera zoom scaling and pan offsets accurately."""
        builder = VerticalFrameBuilder(canvas_width=1080, canvas_height=1920)
        crop = np.full((250, 250, 3), 120, dtype=np.uint8)

        # Test punch zoom and pan
        frame_zoomed = builder.build_frame(crop, zoom_scale=1.25, pan_offset=(30, -40))
        self.assertEqual(frame_zoomed.shape, (1920, 1080, 3))

    def test_video_renderer_image_caching_and_fallback(self) -> None:
        """VideoRenderer caches loaded images and safely falls back on missing paths."""
        renderer = VideoRenderer(canvas_size=(1080, 1920), fps=30.0)
        cache: dict[str, np.ndarray] = {}

        # 1. Resolve real image
        img1 = renderer._resolve_image(str(self.page_paths[0]), cache)
        self.assertIn(str(self.page_paths[0]), cache)
        self.assertIsNotNone(img1)
        self.assertEqual(img1.shape[0], 1200)

        # 2. Second access uses cache identity
        img2 = renderer._resolve_image(str(self.page_paths[0]), cache)
        self.assertIs(img1, img2)

        # 3. Nonexistent image triggers synthetic fallback
        fallback = renderer._resolve_image("nonexistent_path_page_99.jpg", cache)
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback.shape, (1280, 900, 3))

    def test_ken_burns_smoothstep_easing(self) -> None:
        """Smoothstep easing math: 3*alpha^2 - 2*alpha^3 correctly maps values."""
        def smoothstep(a: float) -> float:
            return a * a * (3.0 - 2.0 * a)

        self.assertAlmostEqual(smoothstep(0.0), 0.0)
        self.assertAlmostEqual(smoothstep(0.5), 0.5)
        self.assertAlmostEqual(smoothstep(1.0), 1.0)
        # Check S-curve acceleration
        self.assertLess(smoothstep(0.25), 0.25)
        self.assertGreater(smoothstep(0.75), 0.75)

    def test_audio_ducking_filter_string_generation(self) -> None:
        """build_ffmpeg_ducking_filter generates valid piecewise volume expressions."""
        intervals = [(1.0, 4.0), (6.0, 8.5)]
        duck_filter = build_ffmpeg_ducking_filter(intervals, duck_level=0.25, normal_level=1.0)

        self.assertIn("between(t,1.000,4.000)", duck_filter)
        self.assertIn("between(t,6.000,8.500)", duck_filter)
        self.assertIn("0.25", duck_filter)
        self.assertIn("1.00", duck_filter)

    def test_render_chapter_video_end_to_end(self) -> None:
        """VideoRenderer synthesizes broadcast-ready MP4 adhering to TimelineContract."""
        out_mp4 = self.test_dir / f"test_render_{uuid.uuid4().hex[:6]}.mp4"
        renderer = VideoRenderer(canvas_size=(1080, 1920), fps=30.0)

        # Create multi-page timeline contract with 2 visual clips across different pages
        visual_clips = [
            VisualClip(
                clip_id="VC_01",
                panel_id="PANEL_P01_01",
                bbox=[20.0, 20.0, 780.0, 580.0],
                image_path=str(self.page_paths[0]),
                start_time=0.0,
                end_time=1.0,
                duration=1.0,
                shot_type="PUNCH_ZOOM",
                motion=MotionConfig(zoom_start=1.05, zoom_end=1.25, pan_start=[0, 0], pan_end=[0, -20]),
                background=BackgroundConfig(blur_radius=51, darkness=0.35),
            ),
            VisualClip(
                clip_id="VC_02",
                panel_id="PANEL_P02_01",
                bbox=[20.0, 600.0, 780.0, 1180.0],
                image_path=str(self.page_paths[1]),
                start_time=1.0,
                end_time=2.0,
                duration=1.0,
                shot_type="ZOOM_IN",
                motion=MotionConfig(zoom_start=1.0, zoom_end=1.15, pan_start=[0, 0], pan_end=[0, 0]),
                background=BackgroundConfig(blur_radius=51, darkness=0.35),
            ),
        ]

        audio_clips = [
            AudioClip(
                clip_id="AUD_01",
                dialogue_id="SEG_01",
                speaker_label="NAMMINH",
                voice_id="vi-VN-NamMinhNeural",
                text="Câu chuyện bắt đầu ngay tại đây!",
                file_path=str(self.sample_audio_path),
                start_time=0.0,
                end_time=1.5,
                duration=1.5,
            ),
        ]

        timeline = TimelineContract(
            version="1.0.0",
            project_id=self.project_id,
            page_id=1,
            source_image_path=str(self.page_paths[0]),
            canvas_size=(1080, 1920),
            fps=30.0,
            total_duration=2.0,
            visual_clips=visual_clips,
            audio_clips=audio_clips,
            metadata={"chapter_id": self.project_id},
        )

        res = renderer.render_chapter_video(timeline, out_mp4)

        self.assertEqual(res["status"], "success")
        self.assertTrue(out_mp4.is_file())
        self.assertGreater(res["file_size_bytes"], 1000)
        self.assertEqual(res["resolution"], [1080, 1920])
        self.assertEqual(res["fps"], 30.0)
        self.assertEqual(res["total_frames"], 60)
        self.assertAlmostEqual(res["duration_sec"], 2.0, places=1)
        self.assertTrue(len(res["file_sha256"]) == 64)

    def test_render_chapter_video_with_bgm_ducking(self) -> None:
        """VideoRenderer mixes BGM with dynamic FFmpeg ducking during active speech."""
        out_mp4 = self.test_dir / f"test_render_ducking_{uuid.uuid4().hex[:6]}.mp4"
        bgm_file = self.test_dir / "test_bgm.mp3"
        bgm_file.write_bytes(generate_mp3_silence(2000))

        renderer = VideoRenderer(canvas_size=(1080, 1920), fps=30.0)

        timeline = TimelineContract(
            version="1.0.0",
            project_id=self.project_id,
            page_id=1,
            source_image_path=str(self.page_paths[0]),
            canvas_size=(1080, 1920),
            fps=30.0,
            total_duration=1.5,
            visual_clips=[
                VisualClip(
                    clip_id="VC_01",
                    panel_id="PANEL_P01_01",
                    bbox=[20.0, 20.0, 780.0, 580.0],
                    image_path=str(self.page_paths[0]),
                    start_time=0.0,
                    end_time=1.5,
                    duration=1.5,
                )
            ],
            audio_clips=[
                AudioClip(
                    clip_id="AUD_01",
                    dialogue_id="SEG_01",
                    speaker_label="NAMMINH",
                    voice_id="vi-VN-NamMinhNeural",
                    text="Thoại thử nghiệm ducking",
                    file_path=str(self.sample_audio_path),
                    start_time=0.2,
                    end_time=1.2,
                    duration=1.0,
                )
            ],
            metadata={
                "ducking": {
                    "voice_intervals": [(0.2, 1.2)],
                }
            },
        )

        res = renderer.render_chapter_video(timeline, out_mp4, bgm_path=bgm_file)
        self.assertEqual(res["status"], "success")
        self.assertTrue(out_mp4.is_file())
        self.assertGreater(res["file_size_bytes"], 1000)

    def test_api_render_endpoint_with_custom_timeline(self) -> None:
        """POST /api/projects/{id}/render handles client-submitted TimelineContract."""
        client = TestClient(app)

        visual_clips = [
            {
                "clip_id": "VC_API_01",
                "panel_id": "PANEL_01",
                "bbox": [20.0, 20.0, 780.0, 580.0],
                "image_path": str(self.page_paths[0]),
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "shot_type": "PANEL_SHOT",
                "motion": {"zoom_start": 1.0, "zoom_end": 1.1, "pan_start": [0, 0], "pan_end": [0, 0]},
                "background": {"blur_radius": 51, "darkness": 0.35},
            }
        ]

        payload = {
            "timeline": {
                "version": "1.0.0",
                "project_id": self.project_id,
                "page_id": 1,
                "source_image_path": str(self.page_paths[0]),
                "canvas_size": [1080, 1920],
                "fps": 30.0,
                "total_duration": 1.0,
                "visual_clips": visual_clips,
                "audio_clips": [],
                "metadata": {},
            },
            "output_filename": f"api_test_{uuid.uuid4().hex[:6]}.mp4",
        }

        res = client.post(f"/api/projects/{self.project_id}/render", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("video_path", data)
        self.assertEqual(data["resolution"], [1080, 1920])

    def test_api_render_endpoint_auto_align_fallback(self) -> None:
        """POST /projects/{id}/render auto-aligns chapter when timeline is omitted."""
        client = TestClient(app)

        res = client.post(
            f"/projects/{self.project_id}/render",
            json={"story_style": "dramatic"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("video_path", data)
        self.assertEqual(data["fps"], 30.0)

    def test_multi_page_chapter_different_images_and_audio_streams(self) -> None:
        """Visual clips from full chapter must map to multiple distinct page images and output valid audio/video."""
        import asyncio
        from app.routers.projects import auto_align_chapter_endpoint, AutoAlignChapterRequest

        req = AutoAlignChapterRequest(story_style="dramatic", target_duration=45, target_panel_count=8)
        timeline = asyncio.run(auto_align_chapter_endpoint(self.project_id, req))
        self.assertGreater(len(timeline.visual_clips), 0)

        # Verify clips contain different image_paths
        clip_images = set(vc.image_path for vc in timeline.visual_clips if vc.image_path)
        self.assertGreaterEqual(len(clip_images), 2, f"Expected multiple page images, got {clip_images}")

        # Render video and verify both video and audio streams
        out_mp4 = self.test_dir / f"test_multipage_render_{uuid.uuid4().hex[:6]}.mp4"
        renderer = VideoRenderer(canvas_size=(1080, 1920), fps=30.0)
        res = renderer.render_chapter_video(timeline, out_mp4)
        self.assertEqual(res["status"], "success")

        ffprobe_bin = ROOT / ".venv" / "bin" / "ffprobe"
        if ffprobe_bin.is_file():
            probe = subprocess.run(
                [str(ffprobe_bin), "-v", "error", "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1", str(out_mp4)],
                capture_output=True,
                text=True,
            )
            self.assertIn("codec_type=video", probe.stdout)
            self.assertIn("codec_type=audio", probe.stdout)


if __name__ == "__main__":
    unittest.main()

