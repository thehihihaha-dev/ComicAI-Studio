from __future__ import annotations

import hashlib, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.project import Project  # noqa: F401 - registers FK target for standalone tools
from app.models.reading_order_benchmark_review import ReadingOrderBenchmarkReview
from app.services.reader_v2_fast_pass import READER_VERSION, ReadingOrderPolicy, prepare_reading_order

ROOT = Path(__file__).resolve().parents[3]
MAX_PAGES = 10


def union_rect(boxes: list[Any]) -> list[float] | None:
    points = [point for box in boxes for point in box if isinstance(point, (list, tuple)) and len(point) == 2]
    return ([min(float(p[0]) for p in points), min(float(p[1]) for p in points),
             max(float(p[0]) for p in points), max(float(p[1]) for p in points)] if points else None)


def asset_path(asset: Asset) -> Path:
    path = Path(asset.file_path)
    return path if path.is_absolute() else ROOT / "backend" / path


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logical_regions(asset: Asset) -> list[dict[str, Any]]:
    blocks, regions = json.loads(asset.ocr_blocks or "[]"), json.loads(asset.vision_regions or "[]")
    result = []
    for region in regions:
        boxes = [blocks[i].get("box") for i in region.get("block_ids", []) if isinstance(i, int) and 0 <= i < len(blocks) and blocks[i].get("box")]
        bbox = union_rect(boxes)
        if bbox is not None:
            result.append({"id": region["id"], "bbox": [float(x) for x in bbox], "type": region.get("type", "unknown"), "group_id": "PAGE"})
    return result


def load_queue(db: Session, project_id: str) -> list[ReadingOrderBenchmarkReview]:
    assets = (db.query(Asset).filter(Asset.project_id == project_id).order_by(Asset.page_order, Asset.id).limit(MAX_PAGES).all())
    for asset in assets:
        review_id = f"reading-order:{asset.id}"; existing = db.get(ReadingOrderBenchmarkReview, review_id)
        path, regions = asset_path(asset), logical_regions(asset)
        if existing is not None:
            if not path.is_file() or source_hash(path) != existing.source_image_hash:
                existing.source_compatible = False; existing.state = "SOURCE_UNAVAILABLE"; db.add(existing)
            continue
        if not regions: continue
        compatible = path.is_file(); digest = source_hash(path) if compatible else ""
        prediction = prepare_reading_order(regions, None, ReadingOrderPolicy.MANGA_RTL)
        db.add(ReadingOrderBenchmarkReview(
            review_id=review_id, project_id=project_id, asset_id=asset.id, page_order=asset.page_order,
            source_image_hash=digest, reader_revision=READER_VERSION, reading_policy="MANGA_RTL",
            predicted_groups=[{"group_id": "PAGE", "region_ids": prediction["reading_order"]}],
            predicted_sequence=prediction["reading_order"], predicted_ambiguity=prediction["region_ambiguity"],
            state="PENDING" if compatible else "SOURCE_UNAVAILABLE", source_compatible=compatible,
        ))
    db.commit()
    return (db.query(ReadingOrderBenchmarkReview).filter_by(project_id=project_id)
            .order_by(ReadingOrderBenchmarkReview.page_order, ReadingOrderBenchmarkReview.asset_id).all())


def serialize_queue(db: Session, project_id: str) -> dict[str, Any]:
    items = []
    for row in load_queue(db, project_id):
        asset = db.get(Asset, row.asset_id); regions = logical_regions(asset) if asset else []
        compatible = bool(asset and asset.project_id == project_id and asset_path(asset).is_file() and source_hash(asset_path(asset)) == row.source_image_hash)
        dimensions = None
        if compatible:
            with Image.open(asset_path(asset)) as image:
                dimensions = {"width": image.width, "height": image.height}
        state = row.state if compatible else "SOURCE_UNAVAILABLE"
        items.append({"review_id": row.review_id, "asset_id": row.asset_id, "page_order": row.page_order,
                      "state": state, "source_compatible": compatible, "revision": row.revision,
                      "reader_revision": row.reader_revision, "reading_policy": row.reading_policy,
                      "regions": regions, "predicted_groups": row.predicted_groups,
                      "image_dimensions": dimensions,
                      "predicted_sequence": row.predicted_sequence, "predicted_ambiguity": row.predicted_ambiguity,
                      "human_groups": row.human_groups, "human_sequence": row.human_sequence,
                      "human_dispositions": row.human_dispositions,
                      "image_url": f"http://127.0.0.1:8000/projects/{project_id}/reading-order-benchmark-review/{row.review_id}/image" if compatible else None})
    counts = Counter(x["state"] for x in items)
    return {"project_id": project_id, "total": len(items), "verified": counts["VERIFIED"],
            "pending": counts["PENDING"], "source_unavailable": counts["SOURCE_UNAVAILABLE"], "items": items,
            "model_calls": {"vlm": 0, "ollama": 0}}


def image_bytes(db: Session, project_id: str, review_id: str) -> bytes:
    row = db.get(ReadingOrderBenchmarkReview, review_id)
    if row is None or row.project_id != project_id: raise HTTPException(404, "Review page not found")
    asset = db.get(Asset, row.asset_id); path = asset_path(asset) if asset else None
    if asset is None or asset.project_id != project_id or not path.is_file() or source_hash(path) != row.source_image_hash:
        raise HTTPException(409, "SOURCE_UNAVAILABLE")
    return path.read_bytes()


def save_review(db: Session, project_id: str, review_id: str, sequence: list[int], groups: list[dict[str, Any]], dispositions: dict[str, str]) -> dict[str, Any]:
    row = db.get(ReadingOrderBenchmarkReview, review_id)
    if row is None or row.project_id != project_id: raise HTTPException(404, "Review page not found")
    asset = db.get(Asset, row.asset_id); path = asset_path(asset) if asset else None
    if asset is None or not path.is_file() or source_hash(path) != row.source_image_hash: raise HTTPException(409, "SOURCE_UNAVAILABLE")
    expected = set(row.predicted_sequence)
    if len(sequence) != len(set(sequence)) or set(sequence) != expected: raise HTTPException(422, "Human sequence must contain every region exactly once")
    grouped = [region for group in groups for region in group.get("region_ids", [])]
    if len(grouped) != len(set(grouped)) or set(grouped) != expected: raise HTTPException(422, "Human groups must contain every region exactly once")
    changed = row.state != "VERIFIED" or row.human_sequence != sequence or row.human_groups != groups or row.human_dispositions != dispositions
    row.human_sequence, row.human_groups, row.human_dispositions = sequence, groups, dispositions
    row.state = "VERIFIED"; row.source_compatible = True
    if changed:
        row.revision += 1; row.updated_at = datetime.now(timezone.utc); row.verified_at = datetime.now(timezone.utc)
    db.add(row); db.commit()
    return {"review_id": review_id, "state": row.state, "revision": row.revision}


def ordering_metrics(predicted: list[int], human: list[int]) -> dict[str, Any]:
    position = {value: index for index, value in enumerate(human)}; total = inversions = 0
    for i, left in enumerate(predicted):
        for right in predicted[i + 1:]:
            total += 1; inversions += position[left] > position[right]
    return {"exact": predicted == human, "pairwise_total": total, "inversions": inversions,
            "pairwise_accuracy": (total - inversions) / total if total else 1.0,
            "corrections": sum(a != b for a, b in zip(predicted, human))}
