"""Day 20 Phase 1: Full Chapter Ingestion Service.

Processes an entire manga/comic chapter (10-25 pages), extracts panel geometry,
measures visual saliency, aggregates dialogue/OCR text, and constructs
hierarchical Chapter -> Pages -> Panels metadata.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import uuid
from typing import Any, Sequence
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

import cv2
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Cache for quick retrieval by project ID
CHAPTER_METADATA_CACHE: dict[str, dict[str, Any]] = {}



class PanelMetadata(BaseModel):
    """Metadata for an individual comic panel inside a page."""
    panel_id: str = Field(..., description="Deterministic panel identifier")
    page_order: int = Field(..., description="1-indexed page sequence number")
    image_path: str = Field(..., description="Absolute or relative file path to page image")
    page_image_path: str = Field(default="", description="Alias to source page image path")
    bbox: list[int] = Field(..., description="[x1, y1, x2, y2] in original image pixel coordinates")
    bbox_normalized: list[float] = Field(..., description="[x1/w, y1/h, x2/w, y2/h] (0.0 to 1.0)")
    area: int = Field(..., description="Bounding box pixel area")
    area_fraction: float = Field(..., description="Fraction of page area covered (0.0 to 1.0)")
    state: str = Field(default="DETECTED", description="'DETECTED' or 'AMBIGUOUS'")
    dialogues: list[str] = Field(default_factory=list, description="Extracted dialogue texts in this panel")
    visual_score: float = Field(default=0.5, description="Visual prominence/saliency score (0.0 to 1.0)")
    has_speech: bool = Field(default=False, description="True if panel contains dialogue bubbles")

    def model_post_init(self, __context: Any) -> None:
        if not self.page_image_path and self.image_path:
            self.page_image_path = self.image_path
        elif not self.image_path and self.page_image_path:
            self.image_path = self.page_image_path


class PageMetadata(BaseModel):
    """Metadata for a single comic page inside a chapter."""
    page_order: int = Field(..., description="1-indexed page sequence number")
    image_path: str = Field(..., description="Path to original page image")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    panels: list[PanelMetadata] = Field(default_factory=list, description="Extracted panels on this page")
    ocr_texts: list[str] = Field(default_factory=list, description="All OCR text strings found on this page")


class ChapterMetadata(BaseModel):
    """Hierarchical contract representing an entire ingested manga chapter."""
    chapter_id: str = Field(..., description="Unique chapter identifier")
    project_id: str = Field(..., description="Associated ComicAI project ID")
    total_pages: int = Field(..., description="Total number of pages ingested")
    total_panels: int = Field(..., description="Total number of panels extracted across all pages")
    pages: list[PageMetadata] = Field(default_factory=list, description="Ordered list of page metadata")
    all_ocr_texts: list[str] = Field(default_factory=list, description="Aggregated OCR dialogues across the chapter")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")


def _natural_sort_key(s: str) -> list[int | str]:
    """Natural sort key for file names containing numbers (e.g. page_2 before page_10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def calculate_panel_visual_score(
    bbox: list[int],
    page_width: int,
    page_height: int,
    state: str = "DETECTED",
    has_speech: bool = False,
) -> float:
    """Calculates visual prominence/saliency score for smart panel selection.

    Optimal panels have:
    - Balanced area fraction (0.12 to 0.65 of page).
    - Non-degenerate aspect ratio.
    - DETECTED status.
    - Presence of speech or character action.
    """
    x1, y1, x2, y2 = bbox
    pw = max(1, page_width)
    ph = max(1, page_height)
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)
    area_fraction = (w * h) / (pw * ph)

    # 1. Area score: Gaussian-like peak around 0.35 area fraction
    ideal_area = 0.35
    area_score = max(0.1, 1.0 - abs(ideal_area - area_fraction) * 2.0)

    # 2. Aspect ratio penalty: prefer standard rectangular ratios (0.4 to 2.5)
    aspect = w / h
    if 0.4 <= aspect <= 2.5:
        aspect_score = 1.0
    else:
        aspect_score = max(0.3, 1.0 - min(abs(aspect - 1.0), 2.0) * 0.3)

    # 3. State bonus
    state_bonus = 0.2 if state == "DETECTED" else 0.0

    # 4. Speech bonus
    speech_bonus = 0.15 if has_speech else 0.0

    raw_score = (area_score * 0.45) + (aspect_score * 0.25) + state_bonus + speech_bonus
    return round(float(min(1.0, max(0.05, raw_score))), 4)


def ingest_chapter(
    project_id: str,
    chapter_folder_or_files: Sequence[Path | str] | Path | str,
    db: Any = None,
) -> ChapterMetadata:
    """Ingests all pages in a chapter, extracting geometry and aggregating text.

    Args:
        project_id: Project identifier.
        chapter_folder_or_files: A directory Path containing images, or a list of image paths.
        db: Optional SQLAlchemy Session to synchronize Asset records.

    Returns:
        ChapterMetadata hierarchical data structure.
    """
    # 1. Resolve file list
    file_paths: list[Path] = []

    if isinstance(chapter_folder_or_files, (str, Path)):
        p = Path(chapter_folder_or_files)
        if p.is_dir():
            supported_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
            for child in p.iterdir():
                if child.is_file() and child.suffix.lower() in supported_exts:
                    file_paths.append(child)
            file_paths.sort(key=lambda x: _natural_sort_key(x.name))
        elif p.is_file():
            file_paths.append(p)
    elif isinstance(chapter_folder_or_files, (list, tuple)):
        for item in chapter_folder_or_files:
            file_paths.append(Path(item))

    if not file_paths:
        logger.warning(f"No image files found for ingestion in project {project_id}")

    # Import panel extractor
    try:
        from app.services.deterministic_panel_extractor import extract_panels
    except ModuleNotFoundError:
        from backend.app.services.deterministic_panel_extractor import extract_panels

    pages: list[PageMetadata] = []
    all_ocr_texts: list[str] = []
    total_panels_count = 0

    for idx, fpath in enumerate(file_paths, start=1):
        # Read image to obtain dimensions and run panel extraction
        img = cv2.imread(str(fpath))
        if img is not None:
            height, width = img.shape[:2]
            try:
                extraction = extract_panels(img)
                raw_panels = extraction.get("panels", [])
            except Exception as e:
                logger.info(f"Panel extraction fallback on page {fpath.name}: {e}")
                raw_panels = []
        else:
            width, height = 900, 1280
            raw_panels = []

        page_panels: list[PanelMetadata] = []

        # If no panels detected, generate fallback full-page panel
        if not raw_panels:
            raw_panels = [{
                "panel_id": f"PN_P{idx:02d}_FULL",
                "bbox": [0, 0, width, height],
                "state": "DETECTED",
            }]

        # Format image path as web-accessible relative path (e.g. uploads/filename.jpg)
        try:
            rel_fpath = str(fpath.relative_to(ROOT / "backend"))
        except ValueError:
            try:
                rel_fpath = str(fpath.relative_to(ROOT))
            except ValueError:
                rel_fpath = fpath.name
                if "uploads" in str(fpath):
                    rel_fpath = f"uploads/{fpath.name}"

        for p_idx, p_data in enumerate(raw_panels, start=1):
            bbox = p_data.get("bbox", [0, 0, width, height])
            state = p_data.get("state", "DETECTED")
            pid = p_data.get("panel_id", f"PN_P{idx:02d}_{p_idx:02d}")

            x1, y1, x2, y2 = bbox
            pw = max(1, width)
            ph = max(1, height)
            area = max(0, (x2 - x1) * (y2 - y1))
            area_frac = round(area / (pw * ph), 4)

            score = calculate_panel_visual_score(
                bbox=bbox,
                page_width=width,
                page_height=height,
                state=state,
                has_speech=False,
            )

            norm_bbox = [
                round(x1 / pw, 4),
                round(y1 / ph, 4),
                round(x2 / pw, 4),
                round(y2 / ph, 4),
            ]

            panel_meta = PanelMetadata(
                panel_id=pid,
                page_order=idx,
                image_path=rel_fpath,
                page_image_path=rel_fpath,
                bbox=bbox,
                bbox_normalized=norm_bbox,
                area=area,
                area_fraction=area_frac,
                state=state,
                visual_score=score,
                has_speech=False,
            )
            page_panels.append(panel_meta)

        # Sort panels in vertical reading order (top to bottom)
        page_panels.sort(key=lambda p: (p.bbox[1], p.bbox[0]))
        total_panels_count += len(page_panels)

        page_meta = PageMetadata(
            page_order=idx,
            image_path=rel_fpath,
            width=width,
            height=height,
            panels=page_panels,
            ocr_texts=[],
        )
        pages.append(page_meta)

    # 3. Synchronize with Database Assets if db session is present
    if db is not None:
        try:
            from app.models.asset import Asset
            import json

            for p_meta in pages:
                rel_path = p_meta.image_path
                existing = (
                    db.query(Asset)
                    .filter(
                        Asset.project_id == project_id,
                        (Asset.page_order == p_meta.page_order) | (Asset.filename == Path(p_meta.image_path).name),
                    )
                    .first()
                )
                if existing:
                    if existing.ocr_text and existing.ocr_text not in all_ocr_texts:
                        p_meta.ocr_texts.append(existing.ocr_text)
                        all_ocr_texts.append(existing.ocr_text)
                    if existing.dialogues:
                        try:
                            d_list = json.loads(existing.dialogues)
                            if isinstance(d_list, list):
                                for d in d_list:
                                    t = d.get("clean_text") or d.get("raw_text") or d.get("text")
                                    if t and t not in all_ocr_texts:
                                        p_meta.ocr_texts.append(t)
                                        all_ocr_texts.append(t)
                        except Exception:
                            pass
                else:
                    new_asset = Asset(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        filename=Path(p_meta.image_path).name,
                        file_type="image/jpeg",
                        file_path=p_meta.image_path,
                        page_order=p_meta.page_order,
                        status="ready",
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(new_asset)
            db.commit()
        except Exception as exc:
            logger.info(f"Database asset sync skipped: {exc}")
            if db:
                db.rollback()

    chapter_id = f"CHP_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    chapter_meta = ChapterMetadata(
        chapter_id=chapter_id,
        project_id=project_id,
        total_pages=len(pages),
        total_panels=total_panels_count,
        pages=pages,
        all_ocr_texts=all_ocr_texts,
        created_at=now_iso,
    )

    # Save to in-memory cache
    CHAPTER_METADATA_CACHE[project_id] = chapter_meta.model_dump()

    return chapter_meta

