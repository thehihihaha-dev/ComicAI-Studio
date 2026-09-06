"""Day 20 Phase 1 Test Suite: Full Chapter Ingestion & Smart Panel Selection Pipeline.

Tests:
1. Visual saliency scoring of comic panels.
2. Ingestion of multi-page chapters (10+ pages) into hierarchical ChapterMetadata.
3. Smart keyframe panel selection (6-10 panels) aligning with script segments and camera motions.
4. Auto-alignment into canonical TimelineContract with Voice NamMinh & BGM Ducking.
5. FastAPI endpoints: /api/projects/{id}/ingest-chapter & /api/projects/{id}/auto-align-chapter.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import unittest

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

from app.schemas.projects import AutoAlignChapterRequest, IngestChapterRequest
from main import app
from src.api.timeline_schema import TimelineContract, VisualClip
from src.services.audio_ducking import DEFAULT_DUCK_LEVEL, DEFAULT_NORMAL_LEVEL
from src.services.chapter_service import (
    CHAPTER_METADATA_CACHE,
    ChapterMetadata,
    PageMetadata,
    PanelMetadata,
    calculate_panel_visual_score,
    ingest_chapter,
)
from src.services.script_generator import (
    GeneratedScriptResponse,
    ScriptSegment,
    generate_fallback_script,
    generate_script,
)
from src.services.smart_selector import (
    SelectedPanel,
    convert_to_visual_clips,
    select_keyframe_panels,
)
from src.services.unified_tts import UNIFIED_VOICE_ID, UnifiedTTSManager


def create_mock_comic_page(width: int = 800, height: int = 1200, num_panels: int = 3) -> np.ndarray:
    """Generates a clean synthetic comic page image with white gutters and bordered panels."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    panel_height = (height - (num_panels + 1) * 20) // num_panels

    for i in range(num_panels):
        y1 = 20 + i * (panel_height + 20)
        y2 = y1 + panel_height
        x1 = 25
        x2 = width - 25
        # Draw dark border
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), 4)
        # Add some inner content
        cv2.putText(
            img,
            f"Panel {i+1}",
            (x1 + 30, y1 + 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (50, 50, 50),
            2,
        )
    return img


class TestDay20ChapterPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="comicai_day20_test_"))
        self.project_id = "test_d20_proj_001"

        # Generate a mock chapter of 10 pages
        self.page_paths: list[Path] = []
        for p_idx in range(1, 11):
            p_path = self.temp_dir / f"page_{p_idx:02d}.jpg"
            # Vary panel count per page (2 to 4 panels)
            panels_on_page = 2 if p_idx % 2 == 0 else 3
            mock_img = create_mock_comic_page(800, 1200, num_panels=panels_on_page)
            cv2.imwrite(str(p_path), mock_img)
            self.page_paths.append(p_path)

    def tearDown(self) -> None:
        if self.temp_dir.exists():
            shutil.rmtree(str(self.temp_dir), ignore_errors=True)
        CHAPTER_METADATA_CACHE.pop(self.project_id, None)

    def test_calculate_panel_visual_score(self) -> None:
        """Visual score should properly reward balanced panels and penalize extreme slivers."""
        # Balanced panel: 0.35 area fraction
        score_good = calculate_panel_visual_score(
            bbox=[50, 50, 750, 450],
            page_width=800,
            page_height=1200,
            state="DETECTED",
            has_speech=True,
        )
        self.assertGreaterEqual(score_good, 0.6)

        # Degenerate horizontal sliver: 800 x 10
        score_sliver = calculate_panel_visual_score(
            bbox=[0, 0, 800, 10],
            page_width=800,
            page_height=1200,
            state="AMBIGUOUS",
            has_speech=False,
        )
        self.assertLess(score_sliver, score_good)

    def test_ingest_chapter_metadata_hierarchy(self) -> None:
        """ingest_chapter should parse all 10 pages and build valid ChapterMetadata."""
        chapter_meta = ingest_chapter(
            project_id=self.project_id,
            chapter_folder_or_files=self.temp_dir,
        )

        self.assertIsInstance(chapter_meta, ChapterMetadata)
        self.assertEqual(chapter_meta.project_id, self.project_id)
        self.assertEqual(chapter_meta.total_pages, 10)
        self.assertGreaterEqual(chapter_meta.total_panels, 10)
        self.assertEqual(len(chapter_meta.pages), 10)

        # Inspect page 1
        page1 = chapter_meta.pages[0]
        self.assertEqual(page1.page_order, 1)
        self.assertEqual(page1.width, 800)
        self.assertEqual(page1.height, 1200)
        self.assertGreaterEqual(len(page1.panels), 1)

        # Inspect first panel
        p1 = page1.panels[0]
        self.assertIsInstance(p1, PanelMetadata)
        self.assertTrue(p1.panel_id.startswith("PN_"))
        self.assertEqual(p1.page_order, 1)
        self.assertEqual(len(p1.bbox), 4)
        self.assertEqual(len(p1.bbox_normalized), 4)
        self.assertGreaterEqual(p1.visual_score, 0.0)
        self.assertLessEqual(p1.visual_score, 1.0)

    def test_smart_panel_selection_count_and_camera_motions(self) -> None:
        """select_keyframe_panels should return 6-10 panels matching script segments."""
        chapter_meta = ingest_chapter(
            project_id=self.project_id,
            chapter_folder_or_files=self.temp_dir,
        )

        # Script with 5 segments: hook, 3 body, cta
        script = generate_fallback_script(
            ocr_texts=["Sample chapter story dialogue"],
            story_style="dramatic",
            target_duration_sec=45,
            project_id=self.project_id,
        )

        selected_panels = select_keyframe_panels(
            chapter_data=chapter_meta,
            script=script,
            target_count=8,
        )

        # Assert count is between 6 and 10
        self.assertGreaterEqual(len(selected_panels), 6)
        self.assertLessEqual(len(selected_panels), 10)
        self.assertEqual(len(selected_panels), 8)

        # First panel must be hook with punch_zoom
        self.assertEqual(selected_panels[0].section_type, "hook")
        self.assertEqual(selected_panels[0].camera_motion, "punch_zoom")
        self.assertGreater(selected_panels[0].motion_config.zoom_end, selected_panels[0].motion_config.zoom_start)

        # Last panel must be call_to_action with zoom_out
        self.assertEqual(selected_panels[-1].section_type, "call_to_action")
        self.assertEqual(selected_panels[-1].camera_motion, "zoom_out")
        self.assertLess(selected_panels[-1].motion_config.zoom_end, selected_panels[-1].motion_config.zoom_start)

        # Assert contiguous non-overlapping time sequence
        for i in range(len(selected_panels)):
            p = selected_panels[i]
            self.assertGreater(p.duration, 0.0)
            self.assertAlmostEqual(p.end_time - p.start_time, p.duration, places=2)
            if i > 0:
                prev_p = selected_panels[i - 1]
                self.assertAlmostEqual(p.start_time, prev_p.end_time, delta=0.05)

        # Total visual duration should cover script duration
        total_visual_dur = selected_panels[-1].end_time
        self.assertAlmostEqual(total_visual_dur, script.total_duration, delta=0.1)

    def test_convert_to_visual_clips(self) -> None:
        """SelectedPanel converts cleanly to VisualClip with background and motion configs."""
        chapter_meta = ingest_chapter(self.project_id, self.temp_dir)
        script = generate_fallback_script(["Dialogue"], "humorous", 45, self.project_id)
        selected_panels = select_keyframe_panels(chapter_meta, script, target_count=7)

        visual_clips = convert_to_visual_clips(selected_panels)
        self.assertEqual(len(visual_clips), len(selected_panels))

        for vc, sp in zip(visual_clips, selected_panels):
            self.assertIsInstance(vc, VisualClip)
            self.assertEqual(vc.clip_id, sp.clip_id)
            self.assertEqual(vc.panel_id, sp.panel_id)
            self.assertEqual(vc.start_time, sp.start_time)
            self.assertEqual(vc.end_time, sp.end_time)
            self.assertEqual(vc.duration, sp.duration)
            self.assertEqual(vc.motion.easing, "smoothstep")
            self.assertEqual(vc.background.border_width, 4)

    def test_fastapi_chapter_endpoints(self) -> None:
        """FastAPI endpoints /ingest-chapter and /auto-align-chapter should succeed."""
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # 1. Ingest chapter via JSON body
        ingest_payload = {
            "chapter_dir": str(self.temp_dir),
        }
        res_ingest = client.post(f"/api/projects/{self.project_id}/ingest-chapter", json=ingest_payload)
        self.assertEqual(res_ingest.status_code, 200)
        data_ingest = res_ingest.json()
        self.assertEqual(data_ingest["project_id"], self.project_id)
        self.assertEqual(data_ingest["total_pages"], 10)
        self.assertGreaterEqual(data_ingest["total_panels"], 10)

        # 2. Auto-align chapter
        align_payload = {
            "story_style": "romantic",
            "target_duration": 40,
            "target_panel_count": 8,
        }
        res_align = client.post(f"/api/projects/{self.project_id}/auto-align-chapter", json=align_payload)
        self.assertEqual(res_align.status_code, 200)
        timeline_data = res_align.json()

        # Validate TimelineContract
        self.assertEqual(timeline_data["project_id"], self.project_id)
        self.assertGreater(timeline_data["total_duration"], 0.0)
        self.assertGreaterEqual(len(timeline_data["visual_clips"]), 6)
        self.assertLessEqual(len(timeline_data["visual_clips"]), 10)
        self.assertGreater(len(timeline_data["audio_clips"]), 0)

        # Check audio clip speaker is NAMMINH
        for ac in timeline_data["audio_clips"]:
            self.assertEqual(ac["speaker_label"], "NAMMINH")
            self.assertEqual(ac["voice_id"], UNIFIED_VOICE_ID)

        # Check metadata contains ducking information
        meta = timeline_data["metadata"]
        self.assertIn("ducking", meta)
        ducking = meta["ducking"]
        self.assertIn("keyframes", ducking)
        self.assertIn("ffmpeg_filter", ducking)
        self.assertIn("voice_intervals", ducking)

        # Verify ducking keyframes contain 0.25 duck levels during active speech
        duck_keyframe_vols = [kf["volume"] for kf in ducking["keyframes"]]
        self.assertIn(DEFAULT_DUCK_LEVEL, duck_keyframe_vols)
        self.assertIn(DEFAULT_NORMAL_LEVEL, duck_keyframe_vols)

    def test_small_chapter_fallback(self) -> None:
        """A chapter with only 1 page and 1 panel should still produce >= 6 panels."""
        single_page_dir = Path(tempfile.mkdtemp(prefix="single_p_"))
        try:
            p_img = create_mock_comic_page(800, 1200, num_panels=1)
            cv2.imwrite(str(single_page_dir / "page_01.jpg"), p_img)
            chapter_meta = ingest_chapter("single_proj", single_page_dir)
            script = generate_fallback_script(["Only one dialogue"], "dramatic", 45, "single_proj")

            selected = select_keyframe_panels(chapter_meta, script, target_count=6)
            self.assertEqual(len(selected), 6)
            for s in selected:
                self.assertGreater(s.duration, 0.0)
        finally:
            shutil.rmtree(str(single_page_dir), ignore_errors=True)

    def test_target_panel_counts(self) -> None:
        """Target counts across the 6-10 range should be accurately respected."""
        chapter_meta = ingest_chapter(self.project_id, self.temp_dir)
        script = generate_fallback_script(["Dialogue"], "humorous", 45, self.project_id)

        for k in (6, 7, 9, 10):
            with self.subTest(target_count=k):
                panels = select_keyframe_panels(chapter_meta, script, target_count=k)
                self.assertEqual(len(panels), k)

    def test_custom_script_and_alternate_prefix(self) -> None:
        """Test passing custom_script and using /projects/ prefix without /api."""
        from fastapi.testclient import TestClient

        client = TestClient(app)

        custom_script = {
            "project_id": self.project_id,
            "story_style": "humorous",
            "total_duration": 18.0,
            "segments": [
                {"id": "SEG_01", "section_type": "hook", "text": "Mở đầu hài hước!", "estimated_duration": 3.0, "suggested_effect": "punch_zoom"},
                {"id": "SEG_02", "section_type": "body", "text": "Diễn biến khó đỡ...", "estimated_duration": 11.0, "suggested_effect": "zoom_in"},
                {"id": "SEG_03", "section_type": "call_to_action", "text": "Follow ngay!", "estimated_duration": 4.0, "suggested_effect": "zoom_out"},
            ],
        }

        align_payload = {
            "story_style": "humorous",
            "target_duration": 18,
            "target_panel_count": 6,
            "custom_script": custom_script,
        }

        # First ingest chapter via /projects/ prefix
        ingest_res = client.post(
            f"/projects/{self.project_id}/ingest-chapter",
            json={"chapter_dir": str(self.temp_dir)},
        )
        self.assertEqual(ingest_res.status_code, 200)

        # Test auto-align with /projects/ prefix
        res = client.post(f"/projects/{self.project_id}/auto-align-chapter", json=align_payload)
        self.assertEqual(res.status_code, 200)
        timeline = res.json()
        self.assertEqual(len(timeline["visual_clips"]), 6)
        self.assertGreaterEqual(len(timeline["audio_clips"]), 3)


if __name__ == "__main__":
    unittest.main()

