"""Unit tests for Day 18 Phase 1: Backend Pipeline Orchestrator & Timeline JSON Contract API.

Verifies:
1. Serialization/deserialization fidelity of Timeline JSON Contract schema.
2. Endpoint POST /api/v1/editor/draft (both JSON and multipart form-data).
3. Endpoint POST /api/v1/editor/render with client-modified timeline.
4. Error handling and validation resilience.
"""
from __future__ import annotations

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
from fastapi.testclient import TestClient
from main import app
import numpy as np

try:
    from src.api.timeline_schema import (
        AudioClip,
        BackgroundConfig,
        MotionConfig,
        RenderRequest,
        RenderResponse,
        TimelineContract,
        VisualClip,
    )
    from src.services.pipeline_orchestrator import ComicPipelineOrchestrator
except ModuleNotFoundError:
    from backend.src.api.timeline_schema import (
        AudioClip,
        BackgroundConfig,
        MotionConfig,
        RenderRequest,
        RenderResponse,
        TimelineContract,
        VisualClip,
    )
    from backend.src.services.pipeline_orchestrator import ComicPipelineOrchestrator


class Day18EditorAPITests(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.sample_img_path = ROOT / "backend" / "uploads" / "92961605-5553-4df1-b74e-9a3bed5e14f5_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-2.jpg"

    def test_schema_serialization_roundtrip(self):
        """TimelineContract must serialize to JSON and deserialize back losslessly."""
        timeline = TimelineContract(
            version="1.0.0",
            project_id="test_proj_01",
            page_id=1,
            source_image_path="backend/uploads/sample.jpg",
            image_dimensions=(900, 1280),
            canvas_size=(1080, 1920),
            fps=30.0,
            total_duration=5.5,
            visual_clips=[
                VisualClip(
                    clip_id="VIS_01",
                    panel_id="PAN_1",
                    bbox=[100.0, 100.0, 500.0, 600.0],
                    start_time=0.0,
                    end_time=3.0,
                    duration=3.0,
                    shot_type="ESTABLISHING",
                    motion=MotionConfig(zoom_start=1.0, zoom_end=1.05, pan_start=(0, 0), pan_end=(0, 10)),
                    background=BackgroundConfig(blur_radius=51, darkness=0.35, border_width=4),
                ),
                VisualClip(
                    clip_id="VIS_02",
                    panel_id="PAN_2",
                    bbox=[100.0, 600.0, 800.0, 1100.0],
                    start_time=3.0,
                    end_time=5.5,
                    duration=2.5,
                    shot_type="CLOSEUP",
                    motion=MotionConfig(zoom_start=1.05, zoom_end=1.10, pan_start=(0, 0), pan_end=(0, -10)),
                ),
            ],
            audio_clips=[
                AudioClip(
                    clip_id="AUD_01",
                    dialogue_id="D_01",
                    speaker_label="RIN",
                    voice_id="vi-VN-HoaiMyNeural",
                    text="Chào cậu!",
                    file_path="artifacts/audio/test.mp3",
                    start_time=0.0,
                    end_time=2.8,
                    duration=2.8,
                )
            ],
            metadata={"source": "test_suite"},
        )

        # 1. Serialize to dict / json
        json_data = timeline.model_dump_json()
        self.assertIsInstance(json_data, str)

        # 2. Deserialize
        restored = TimelineContract.model_validate_json(json_data)
        self.assertEqual(restored.project_id, "test_proj_01")
        self.assertEqual(len(restored.visual_clips), 2)
        self.assertEqual(restored.visual_clips[0].motion.zoom_end, 1.05)
        self.assertEqual(len(restored.audio_clips), 1)
        self.assertEqual(restored.audio_clips[0].text, "Chào cậu!")

    def test_post_draft_generation_json(self):
        """POST /api/v1/editor/draft must generate valid TimelineContract from JSON request."""
        response = self.client.post(
            "/api/v1/editor/draft",
            json={
                "image_path": str(self.sample_img_path.relative_to(ROOT)),
                "project_id": "proj_draft_test",
                "page_order": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Validate with Pydantic
        contract = TimelineContract.model_validate(data)
        self.assertEqual(contract.project_id, "proj_draft_test")
        self.assertEqual(contract.page_id, 1)
        self.assertEqual(contract.canvas_size, (1080, 1920))
        self.assertGreater(len(contract.visual_clips), 0)
        self.assertGreater(len(contract.audio_clips), 0)
        self.assertGreater(contract.total_duration, 0.0)

    def test_post_draft_generation_multipart_upload(self):
        """POST /api/v1/editor/draft must support multipart file uploads."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_img_path = Path(tmp_dir) / "temp_comic.jpg"
            dummy_img = np.zeros((1000, 800, 3), dtype=np.uint8)
            dummy_img[100:400, 100:700] = [180, 120, 80]
            cv2.imwrite(str(dummy_img_path), dummy_img)

            with open(dummy_img_path, "rb") as f:
                response = self.client.post(
                    "/api/v1/editor/draft",
                    files={"file": ("temp_comic.jpg", f, "image/jpeg")},
                    data={"project_id": "proj_multipart_test", "page_order": "1"},
                )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            contract = TimelineContract.model_validate(data)
            self.assertEqual(contract.project_id, "proj_multipart_test")
            self.assertGreaterEqual(len(contract.visual_clips), 1)

    def test_post_render_from_edited_contract(self):
        """POST /api/v1/editor/render must synthesize valid MP4 from a modified contract."""
        # 1. Generate baseline draft
        draft_res = self.client.post(
            "/api/v1/editor/draft",
            json={
                "image_path": str(self.sample_img_path.relative_to(ROOT)),
                "project_id": "proj_render_test",
                "page_order": 1,
            },
        )
        self.assertEqual(draft_res.status_code, 200)
        timeline_dict = draft_res.json()

        # 2. Simulate client web editor modification: change zoom and pan on Shot 1
        timeline_dict["visual_clips"][0]["motion"]["zoom_start"] = 1.02
        timeline_dict["visual_clips"][0]["motion"]["zoom_end"] = 1.15
        timeline_dict["visual_clips"][0]["background"]["border_width"] = 6

        # 3. Call render endpoint
        render_res = self.client.post(
            "/api/v1/editor/render",
            json={
                "timeline": timeline_dict,
                "output_filename": "test_edited_render.mp4",
            },
        )
        self.assertEqual(render_res.status_code, 200)
        render_data = render_res.json()

        # Validate response schema
        resp = RenderResponse.model_validate(render_data)
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.resolution, [1080, 1920])
        self.assertEqual(resp.fps, 30.0)
        self.assertGreater(resp.total_frames, 300)
        self.assertGreater(resp.file_size_bytes, 100000)
        self.assertLess(resp.audio_drift_sec, 0.05)

        # Cleanup test artifact
        rendered_f = ROOT / resp.video_path
        if rendered_f.is_file():
            rendered_f.unlink()

    def test_error_resilience_missing_image(self):
        """POST /api/v1/editor/draft must return 404 for non-existent image paths."""
        response = self.client.post(
            "/api/v1/editor/draft",
            json={"image_path": "non_existent_image_12345.jpg"},
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

