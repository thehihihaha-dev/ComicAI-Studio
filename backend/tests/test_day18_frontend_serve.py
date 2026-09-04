"""Unit tests for Day 18 Phase 2: Interactive Web Editor Frontend & Asset Serving.

Verifies:
1. Physical existence and integrity of all Next.js Web Editor components in frontend/app/editor/.
2. Integrity and schema conformance of preloaded benchmark contract in frontend/public/.
3. Static media asset streaming via FastAPI backend (/uploads/ and /artifacts/).
4. End-to-end export integration: render request returns playable MP4 accessible via static endpoint.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from main import app
import mutagen.mp3

try:
    from src.api.timeline_schema import RenderResponse, TimelineContract
except ModuleNotFoundError:
    from backend.src.api.timeline_schema import RenderResponse, TimelineContract


class Day18FrontendServeTests(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.frontend_dir = ROOT / "frontend"

    def test_frontend_editor_components_exist(self):
        """All Web Editor components must exist with non-empty TypeScript code."""
        required_files = [
            self.frontend_dir / "app" / "editor" / "page.tsx",
            self.frontend_dir / "app" / "editor" / "types.ts",
            self.frontend_dir / "app" / "editor" / "components" / "VideoPreview.tsx",
            self.frontend_dir / "app" / "editor" / "components" / "Timeline.tsx",
            self.frontend_dir / "app" / "editor" / "components" / "Inspector.tsx",
            self.frontend_dir / "app" / "editor" / "components" / "ExportModal.tsx",
        ]

        for file_path in required_files:
            self.assertTrue(file_path.is_file(), f"Missing frontend component: {file_path.relative_to(ROOT)}")
            content = file_path.read_text(encoding="utf-8")
            self.assertGreater(len(content), 100, f"Component too short: {file_path.name}")

    def test_preloaded_public_contract_integrity(self):
        """Preloaded public contract must be valid JSON strictly matching TimelineContract schema."""
        contract_path = self.frontend_dir / "public" / "timeline_contract_page_01.json"
        self.assertTrue(contract_path.is_file(), "Missing frontend/public/timeline_contract_page_01.json")

        data = json.loads(contract_path.read_text(encoding="utf-8"))
        contract = TimelineContract.model_validate(data)

        self.assertEqual(contract.project_id, "project_wedding_vows")
        self.assertEqual(contract.page_id, 1)
        self.assertEqual(contract.canvas_size, (1080, 1920))
        self.assertEqual(len(contract.visual_clips), 4)
        self.assertEqual(len(contract.audio_clips), 4)
        self.assertAlmostEqual(contract.total_duration, 10.66, delta=0.1)

    def test_preloaded_media_assets_validity(self):
        """Preloaded public image and audio assets must be valid media files."""
        img_path = self.frontend_dir / "public" / "page_01.jpg"
        audio_path = self.frontend_dir / "public" / "page_01_full.mp3"

        self.assertTrue(img_path.is_file(), "Missing page_01.jpg in public/")
        self.assertGreater(img_path.stat().st_size, 50000)

        self.assertTrue(audio_path.is_file(), "Missing page_01_full.mp3 in public/")
        audio_info = mutagen.mp3.MP3(str(audio_path)).info
        self.assertGreater(audio_info.length, 8.0)

    def test_fastapi_artifacts_static_serving(self):
        """FastAPI must serve audio and video assets under /artifacts/ static mount."""
        # 1. Test audio preview track serving
        audio_res = self.client.get("/artifacts/audio/day17/previews/page_01_full.mp3")
        self.assertEqual(audio_res.status_code, 200)
        self.assertGreater(len(audio_res.content), 10000)

        # 2. Test video preview serving
        video_res = self.client.get("/artifacts/video/day17/page_01_preview.mp4")
        self.assertEqual(video_res.status_code, 200)
        self.assertGreater(len(video_res.content), 50000)

    def test_render_and_serve_workflow(self):
        """Client TimelineContract submitted to /api/v1/editor/render must be accessible via static mount."""
        contract_path = self.frontend_dir / "public" / "timeline_contract_page_01.json"
        contract_dict = json.loads(contract_path.read_text(encoding="utf-8"))

        out_name = "test_serve_render.mp4"
        res = self.client.post(
            "/api/v1/editor/render",
            json={
                "timeline": contract_dict,
                "output_filename": out_name,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        resp = RenderResponse.model_validate(data)

        # Verify static endpoint serves the newly rendered video
        static_url = resp.video_url
        get_res = self.client.get(static_url)
        self.assertEqual(get_res.status_code, 200)
        self.assertGreater(len(get_res.content), 100000)

        # Cleanup
        rendered_f = ROOT / resp.video_path
        if rendered_f.is_file():
            rendered_f.unlink()


if __name__ == "__main__":
    unittest.main()

