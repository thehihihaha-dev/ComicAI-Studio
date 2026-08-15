import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.asset import Asset
from app.models.dialogue_ground_truth import DialogueGroundTruth
from app.models.project import Project
from app.routers.projects import delete_project


class ProjectDeletionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.asset_path = Path(self.temp_dir.name) / "page.jpg"
        self.asset_path.write_bytes(b"image")

        with self.session_factory() as db:
            now = datetime.now(timezone.utc)
            db.add_all(
                [
                    Project(
                        id="delete-me",
                        name="Delete me",
                        content_type="short",
                        status="created",
                        created_at=now,
                    ),
                    Project(
                        id="keep-me",
                        name="Keep me",
                        content_type="short",
                        status="created",
                        created_at=now,
                    ),
                ]
            )
            db.add(
                Asset(
                    id="asset-delete-me",
                    project_id="delete-me",
                    filename="page.jpg",
                    file_type="image",
                    file_path=str(self.asset_path),
                    page_order=1,
                    created_at=now,
                )
            )
            db.add(
                DialogueGroundTruth(
                    asset_id="asset-delete-me",
                    region_id=1,
                    raw_text="RAW",
                    ai_text="AI",
                    verified_text="VERIFIED",
                )
            )
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_delete_project_removes_only_its_records_and_file(self):
        with patch(
            "app.routers.projects.SessionLocal",
            self.session_factory,
        ):
            result = delete_project("delete-me")

        self.assertEqual(result["deleted_assets"], 1)
        self.assertFalse(self.asset_path.exists())

        with self.session_factory() as db:
            self.assertIsNone(db.get(Project, "delete-me"))
            self.assertIsNotNone(db.get(Project, "keep-me"))
            self.assertEqual(db.query(Asset).count(), 0)
            self.assertEqual(db.query(DialogueGroundTruth).count(), 0)


if __name__ == "__main__":
    unittest.main()
