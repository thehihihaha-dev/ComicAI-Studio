"""Unit test to verify project isolation, upload-pages, and persistence with SQLite in-memory."""
import io
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from main import app
from app.database import Base
from app.models.project import Project
from app.models.asset import Asset


class TestProjectUploadAndIsolation(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.patchers = [
            patch("app.routers.projects.SessionLocal", self.session_factory),
            patch("app.routers.assets.SessionLocal", self.session_factory),
        ]
        for p in self.patchers:
            p.start()

        self.client = TestClient(app)
        self.test_project_id = f"test_proj_{uuid4().hex[:12]}"

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.engine.dispose()

        # Clean up test upload files if created
        upload_dir = (
            Path(__file__).resolve().parents[1] / "uploads" / self.test_project_id
        )
        if upload_dir.exists():
            import shutil

            shutil.rmtree(upload_dir, ignore_errors=True)

    def test_new_project_isolation(self):
        """New project with unknown ID must not be contaminated by benchmark data."""
        # 1. Unknown project should return 404
        res = self.client.get(f"/projects/{self.test_project_id}")
        self.assertEqual(res.status_code, 404)

        # 2. Assets for empty project must return empty list, not benchmark 10 pages
        res = self.client.get(f"/assets/project/{self.test_project_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["items"]), 0)

    def test_create_project_and_upload_pages(self):
        """Creating a project and uploading multiple chapter pages persists them in DB."""
        # 1. Create project via POST /projects/
        res = self.client.post(
            "/projects/",
            json={
                "id": self.test_project_id,
                "name": "Manga Test Chapter",
                "content_type": "short",
                "story_style": "dramatic",
            },
        )
        self.assertEqual(res.status_code, 200)
        proj_data = res.json()
        self.assertEqual(proj_data["id"], self.test_project_id)
        self.assertEqual(proj_data["name"], "Manga Test Chapter")

        # 2. Upload 2 mock image pages
        dummy_img1 = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50)
        dummy_img2 = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50)

        files = [
            ("files", ("page_01.jpg", dummy_img1, "image/jpeg")),
            ("files", ("page_02.jpg", dummy_img2, "image/jpeg")),
        ]
        res = self.client.post(
            f"/api/projects/{self.test_project_id}/upload-pages",
            files=files,
        )
        self.assertEqual(res.status_code, 200)
        upload_data = res.json()
        self.assertEqual(upload_data["project_id"], self.test_project_id)
        self.assertEqual(upload_data["uploaded_count"], 2)
        self.assertEqual(len(upload_data["pages"]), 2)

        # Check page_order and URLs
        self.assertEqual(upload_data["pages"][0]["page_order"], 1)
        self.assertEqual(upload_data["pages"][1]["page_order"], 2)
        self.assertTrue(
            upload_data["pages"][0]["url"].startswith("http://127.0.0.1:8000/uploads/")
        )

        # 3. Verify persistence via GET /assets/project/{id} (simulates F5)
        res = self.client.get(f"/assets/project/{self.test_project_id}")
        self.assertEqual(res.status_code, 200)
        asset_data = res.json()
        self.assertEqual(asset_data["total"], 2)
        self.assertEqual(len(asset_data["items"]), 2)
        self.assertEqual(asset_data["items"][0]["page_order"], 1)
        self.assertEqual(asset_data["items"][1]["page_order"], 2)
        self.assertEqual(
            asset_data["items"][0]["file_path"],
            f"uploads/{self.test_project_id}/page_01.jpg",
        )

    def test_auto_align_rejects_empty_project(self):
        """Auto-align on an empty project must raise 400 and not secretly use benchmark pages."""
        empty_id = f"empty_proj_{uuid4().hex[:10]}"
        res = self.client.post(
            f"/api/projects/{empty_id}/auto-align-chapter",
            json={"story_style": "dramatic"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Dự án chưa có trang truyện", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
