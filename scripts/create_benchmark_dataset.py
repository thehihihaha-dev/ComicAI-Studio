#!/usr/bin/env python3
"""Create an isolated cold benchmark project from existing source assets."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / "backend" / ".env")
os.chdir(ROOT / "backend")

from app.database import SessionLocal  # noqa: E402
from app.models.asset import Asset  # noqa: E402
from app.models.project import Project  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-project-id", required=True)
    parser.add_argument("--name", default="ComicAI Benchmark V1")
    args = parser.parse_args()

    db = SessionLocal()
    copied_paths: list[Path] = []
    try:
        if db.query(Project).filter(Project.name == args.name).first():
            raise SystemExit(f"Project named {args.name!r} already exists; nothing changed.")
        source = db.query(Project).filter(Project.id == args.source_project_id).first()
        if source is None:
            raise SystemExit("Source project does not exist.")
        source_assets = (
            db.query(Asset)
            .filter(Asset.project_id == source.id)
            .order_by(Asset.page_order, Asset.id)
            .all()
        )
        usable = [asset for asset in source_assets if Path(asset.file_path).is_file()]
        if not usable:
            raise SystemExit("Source project has no assets with available image bytes.")

        project_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        project = Project(
            id=project_id,
            name=args.name,
            content_type=source.content_type,
            status="draft",
            created_at=now,
        )
        db.add(project)
        db.flush()
        manifest = []
        for page_order, source_asset in enumerate(usable, start=1):
            asset_id = str(uuid.uuid4())
            source_path = Path(source_asset.file_path)
            destination = Path("uploads") / f"{asset_id}_{source_asset.filename}"
            shutil.copyfile(source_path, destination)
            copied_paths.append(destination)
            if sha256(source_path) != sha256(destination):
                raise RuntimeError(f"Byte hash mismatch while copying {source_asset.filename}.")
            db.add(
                Asset(
                    id=asset_id,
                    project_id=project_id,
                    filename=source_asset.filename,
                    file_type=source_asset.file_type,
                    file_path=str(destination),
                    page_order=page_order,
                    created_at=now,
                    status="ready",
                    ocr_text=None,
                    ocr_blocks=None,
                    vision_regions=None,
                    reading_order=None,
                    vision_status="pending",
                    dialogues=None,
                    dialogue_status="pending",
                )
            )
            manifest.append((asset_id, source_asset.id, source_asset.filename, sha256(destination)))
        db.commit()
    except BaseException:
        db.rollback()
        for path in copied_paths:
            path.unlink(missing_ok=True)
        raise
    finally:
        db.close()

    print(f"project_id={project_id}")
    for asset_id, source_id, filename, image_hash in manifest:
        print(f"asset_id={asset_id} source_asset_id={source_id} filename={filename} sha256={image_hash}")


if __name__ == "__main__":
    main()
