#!/usr/bin/env python3
"""Export VERIFIED human OCR samples; optionally rerun unchanged 11.4 metrics.

The default export performs zero OCR/model calls. `--run` executes EasyOCR then
PaddleOCR sequentially through the 11.4 adapters and writes only `*-latest.json`
artifacts; it never overwrites the frozen 11.4 checkpoint files.
"""

from __future__ import annotations

import argparse, json, os, sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path[:0] = [str(BACKEND), str(ROOT / "scripts")]
load_dotenv(BACKEND / ".env"); os.chdir(BACKEND)

from app.database import SessionLocal  # noqa: E402
from app.models.ocr_benchmark_review import OcrBenchmarkReview  # noqa: E402
from app.services.ocr_benchmark_review import verified_samples  # noqa: E402


def export_verified(output: Path, project_id: str | None = None) -> dict:
    db = SessionLocal()
    try:
        samples = verified_samples(db, project_id)
        query = db.query(OcrBenchmarkReview)
        if project_id is not None:
            query = query.filter_by(project_id=project_id)
        states = Counter(row.state for row in query.all())
    finally:
        db.close()
    artifact = {"schema_version": "reader-human-gt.v1", "artifact_kind": "verified_manifest",
                "verified_only": True, "sample_count": len(samples), "samples": samples,
                "persisted_state_counts": {state: states[state] for state in
                    ("VERIFIED", "UNREADABLE", "SKIPPED", "SOURCE_UNAVAILABLE", "PENDING")},
                "total_queue": sum(states.values()),
                "unavailable_human_ground_truth": [],
                "metric_contract": "reader-ocr-expanded.v1 (11.4 definitions; every metric must include N)"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-id")
    parser.add_argument("--output", default="benchmarks/day11/reader-human-verified-latest.json")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(); output = Path(args.output)
    if not output.is_absolute(): output = ROOT / output
    artifact = export_verified(output, args.project_id)
    if args.run:
        if not artifact["sample_count"]:
            raise SystemExit("No compatible VERIFIED samples; OCR was not started")
        import reader_benchmark_11_4 as runner
        runner.MANIFEST = output
        runner.EASY = output.parent / "reader-easyocr-verified-latest.json"
        runner.PADDLE = output.parent / "reader-paddleocr-verified-latest.json"
        runner.COMPARISON = output.parent / "reader-ocr-comparison-verified-latest.json"
        runner.ERRORS = output.parent / "reader-ocr-errors-verified-latest.json"
        runner.benchmark("easyocr")
        runner.benchmark("paddleocr")
        runner.analyze()
    print(json.dumps({"verified_samples": artifact["sample_count"], "output": str(output)}))


if __name__ == "__main__": main()
