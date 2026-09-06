"""Unit tests for Day 19 Phase 1: Backend LLM Script Engine & Unified TTS Ducking.

Verifies:
1. Script generation produces valid Pydantic schema across dramatic, humorous, romantic styles.
2. TTS configuration strictly enforces vi-VN-NamMinhNeural at rate=+12% and pitch=0%.
3. Audio Ducking algorithm calculates exact 25% BGM attenuation during speech and smooth 100% recovery.
4. FastAPI endpoints POST /api/projects/{project_id}/generate-script and /projects/{project_id}/generate-script.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from main import app

try:
    from src.services.script_generator import (
        GeneratedScriptResponse,
        ScriptSegment,
        generate_script,
    )
    from src.services.unified_tts import (
        UNIFIED_PITCH,
        UNIFIED_SPEAKING_RATE,
        UNIFIED_VOICE_ID,
        UnifiedTTSManager,
    )
    from src.services.audio_ducking import (
        DEFAULT_DUCK_LEVEL,
        DEFAULT_NORMAL_LEVEL,
        build_ffmpeg_ducking_filter,
        generate_ducking_keyframes,
        generate_ducking_volume_timeline,
        get_bgm_volume_at,
    )
except ModuleNotFoundError:
    from backend.src.services.script_generator import (
        GeneratedScriptResponse,
        ScriptSegment,
        generate_script,
    )
    from backend.src.services.unified_tts import (
        UNIFIED_PITCH,
        UNIFIED_SPEAKING_RATE,
        UNIFIED_VOICE_ID,
        UnifiedTTSManager,
    )
    from backend.src.services.audio_ducking import (
        DEFAULT_DUCK_LEVEL,
        DEFAULT_NORMAL_LEVEL,
        build_ffmpeg_ducking_filter,
        generate_ducking_keyframes,
        generate_ducking_volume_timeline,
        get_bgm_volume_at,
    )


class TestDay19ScriptGenerator(unittest.TestCase):
    """Verifies AI Script Generator across all required story styles."""

    def setUp(self):
        self.sample_ocr = [
            "Con có đồng ý lấy Rin làm vợ hợp pháp không?",
            "Con đồng ý.",
            "Tại sao anh lại nhìn tôi với ánh mắt đấy chứ?",
        ]

    def test_script_generation_dramatic(self):
        resp = generate_script(
            ocr_texts=self.sample_ocr,
            story_style="dramatic",
            target_duration_sec=45,
            project_id="proj_test_dramatic",
        )
        self.assertIsInstance(resp, GeneratedScriptResponse)
        self.assertEqual(resp.project_id, "proj_test_dramatic")
        self.assertEqual(resp.story_style, "dramatic")
        self.assertGreaterEqual(len(resp.segments), 3)

        # First segment must be a hook
        self.assertEqual(resp.segments[0].section_type, "hook")
        self.assertIn(resp.segments[0].suggested_effect, ["punch_zoom", "zoom_in"])

        # Body segments
        body_segs = [s for s in resp.segments if s.section_type == "body"]
        self.assertGreaterEqual(len(body_segs), 1)

        # Final segment must be call to action
        self.assertEqual(resp.segments[-1].section_type, "call_to_action")

        # Total duration must equal sum of segment durations
        calculated_dur = round(sum(s.estimated_duration for s in resp.segments), 2)
        self.assertAlmostEqual(resp.total_duration, calculated_dur, places=2)

    def test_script_generation_humorous(self):
        resp = generate_script(
            ocr_texts=self.sample_ocr,
            story_style="humorous",
            target_duration_sec=35,
            project_id="proj_test_humorous",
        )
        self.assertIsInstance(resp, GeneratedScriptResponse)
        self.assertEqual(resp.story_style, "humorous")
        self.assertGreaterEqual(len(resp.segments), 3)
        for seg in resp.segments:
            self.assertGreater(len(seg.text.strip()), 5)
            self.assertGreater(seg.estimated_duration, 0.0)

    def test_script_generation_romantic(self):
        resp = generate_script(
            ocr_texts=self.sample_ocr,
            story_style="romantic",
            target_duration_sec=40,
            project_id="proj_test_romantic",
        )
        self.assertIsInstance(resp, GeneratedScriptResponse)
        self.assertEqual(resp.story_style, "romantic")
        self.assertGreaterEqual(len(resp.segments), 3)
        for seg in resp.segments:
            self.assertGreater(len(seg.text.strip()), 5)
            self.assertGreater(seg.estimated_duration, 0.0)

    def test_script_generation_empty_ocr(self):
        """Must gracefully fallback to valid script even with empty OCR inputs."""
        resp = generate_script(
            ocr_texts=[],
            story_style="dramatic",
            target_duration_sec=45,
            project_id="proj_empty",
        )
        self.assertIsInstance(resp, GeneratedScriptResponse)
        self.assertGreaterEqual(len(resp.segments), 3)


class TestDay19UnifiedTTS(unittest.TestCase):
    """Verifies single-voice unified TTS configuration and speech track synthesis."""

    def test_tts_configuration_invariants(self):
        """Must strictly enforce vi-VN-NamMinhNeural with +12% rate and 0% pitch."""
        self.assertEqual(UNIFIED_VOICE_ID, "vi-VN-NamMinhNeural")
        self.assertEqual(UNIFIED_SPEAKING_RATE, "+12%")
        self.assertEqual(UNIFIED_PITCH, "0%")

        manager = UnifiedTTSManager()
        self.assertEqual(manager.voice_id, "vi-VN-NamMinhNeural")
        self.assertEqual(manager.speaking_rate, "+12%")
        self.assertEqual(manager.pitch, "0%")

    def test_segment_synthesis_and_stitching(self):
        """Synthesizes script segments in offline fallback mode and stitches speech track."""
        manager = UnifiedTTSManager(offline_fallback=True)

        script = GeneratedScriptResponse(
            project_id="test_tts_proj",
            story_style="dramatic",
            total_duration=12.0,
            segments=[
                ScriptSegment(
                    id="SEG_01",
                    section_type="hook",
                    text="Cứ ngỡ là hôn lễ trong mơ, ai ngờ lại là cái bẫy!",
                    estimated_duration=2.5,
                    suggested_effect="punch_zoom",
                ),
                ScriptSegment(
                    id="SEG_02",
                    section_type="body",
                    text="Ngay tại thánh đường, sự thật kinh hoàng đã bị vạch trần.",
                    estimated_duration=3.0,
                    suggested_effect="zoom_in",
                ),
                ScriptSegment(
                    id="SEG_03",
                    section_type="call_to_action",
                    text="Bấm follow ngay để đón xem tập tiếp theo!",
                    estimated_duration=2.0,
                    suggested_effect="zoom_out",
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "audio_out"
            results = asyncio.run(manager.synthesize_script(script, out_dir))

            self.assertEqual(len(results), 3)
            for seg_res in results:
                self.assertEqual(seg_res["voice_id"], "vi-VN-NamMinhNeural")
                self.assertEqual(seg_res["speaking_rate"], "+12%")
                self.assertEqual(seg_res["pitch"], "0%")
                self.assertTrue(Path(seg_res["file_path"]).is_file())
                self.assertGreater(Path(seg_res["file_path"]).stat().st_size, 0)
                self.assertGreater(seg_res["duration"], 0.5)
                self.assertLess(seg_res["start_time"], seg_res["end_time"])

            # Stitch speech track
            stitched_file = Path(tmp_dir) / "stitched_speech.mp3"
            total_speech_dur = manager.stitch_speech_track(results, stitched_file)
            self.assertTrue(stitched_file.is_file())
            self.assertGreater(stitched_file.stat().st_size, 0)
            self.assertGreater(total_speech_dur, 5.0)


class TestDay19AudioDucking(unittest.TestCase):
    """Verifies Audio Ducking algorithm attenuates BGM to 25% during speech and fades back to 100%."""

    def setUp(self):
        # Two speech segments: 2.0s -> 5.0s, and 8.0s -> 11.0s
        self.voice_intervals = [(2.0, 5.0), (8.0, 11.0)]

    def test_bgm_volume_attenuation_during_speech(self):
        """BGM volume must strictly drop to 25% (0.25) when speech is active."""
        # Inside first segment
        vol_inside_1 = get_bgm_volume_at(3.5, self.voice_intervals)
        self.assertEqual(vol_inside_1, 0.25)

        # Boundaries of first segment
        self.assertEqual(get_bgm_volume_at(2.0, self.voice_intervals), 0.25)
        self.assertEqual(get_bgm_volume_at(5.0, self.voice_intervals), 0.25)

        # Inside second segment
        vol_inside_2 = get_bgm_volume_at(9.0, self.voice_intervals)
        self.assertEqual(vol_inside_2, 0.25)

    def test_bgm_volume_at_normal_during_pauses(self):
        """BGM volume must return to 100% (1.00) well outside of speech intervals."""
        # Before speech starts (t = 0.5s, well before 2.0s - fade_out 0.1s)
        vol_before = get_bgm_volume_at(0.5, self.voice_intervals)
        self.assertEqual(vol_before, 1.0)

        # In pause gap between segments (e.g. t = 6.5s: 1.5s after 5.0s, well after fade_in 0.3s)
        vol_gap = get_bgm_volume_at(6.5, self.voice_intervals)
        self.assertEqual(vol_gap, 1.0)

        # After all speech ends (t = 15.0s)
        vol_after = get_bgm_volume_at(15.0, self.voice_intervals)
        self.assertEqual(vol_after, 1.0)

    def test_bgm_volume_fade_in_transition(self):
        """BGM volume must smoothly interpolate between 25% and 100% during 0.3s fade-in."""
        # Speech ends at 5.0s. Fade in runs from 5.0s to 5.3s.
        # At midpoint 5.15s, volume should be between 0.25 and 1.00.
        vol_fade = get_bgm_volume_at(5.15, self.voice_intervals, fade_in_sec=0.30)
        self.assertGreater(vol_fade, 0.25)
        self.assertLess(vol_fade, 1.00)
        # Expected midpoint = 0.25 + 0.75 * 0.5 = 0.625
        self.assertAlmostEqual(vol_fade, 0.625, delta=0.01)

    def test_empty_voice_intervals(self):
        """When no voice is present, volume remains at 100%."""
        vol = get_bgm_volume_at(3.0, [])
        self.assertEqual(vol, 1.0)

    def test_ducking_timeline_and_keyframes(self):
        timeline = generate_ducking_volume_timeline(self.voice_intervals, total_duration=12.0)
        self.assertGreater(len(timeline), 50)
        for point in timeline:
            self.assertGreaterEqual(point["volume"], 0.25)
            self.assertLessEqual(point["volume"], 1.0)

        keyframes = generate_ducking_keyframes(self.voice_intervals, total_duration=12.0)
        self.assertGreaterEqual(len(keyframes), 6)

        ffmpeg_filter = build_ffmpeg_ducking_filter(self.voice_intervals)
        self.assertIn("0.25", ffmpeg_filter)
        self.assertIn("1.00", ffmpeg_filter)
        self.assertIn("volume=", ffmpeg_filter)


class TestDay19ScriptAPI(unittest.TestCase):
    """Verifies FastAPI endpoints for AI Script generation."""

    def setUp(self):
        self.client = TestClient(app)

    def test_generate_script_api_prefix(self):
        """Tests POST /api/projects/{project_id}/generate-script."""
        payload = {
            "story_style": "dramatic",
            "target_duration": 45,
        }
        res = self.client.post("/api/projects/test_proj_api/generate-script", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["project_id"], "test_proj_api")
        self.assertEqual(data["story_style"], "dramatic")
        self.assertIn("segments", data)
        self.assertGreaterEqual(len(data["segments"]), 3)

    def test_generate_script_standard_prefix(self):
        """Tests POST /projects/{project_id}/generate-script."""
        payload = {
            "story_style": "humorous",
            "target_duration": 30,
        }
        res = self.client.post("/projects/test_proj_standard/generate-script", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["project_id"], "test_proj_standard")
        self.assertEqual(data["story_style"], "humorous")
        self.assertIn("segments", data)

    def test_generate_script_romantic_style(self):
        payload = {
            "story_style": "romantic",
            "target_duration": 40,
        }
        res = self.client.post("/api/projects/test_proj_romantic/generate-script", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["story_style"], "romantic")


if __name__ == "__main__":
    unittest.main()

