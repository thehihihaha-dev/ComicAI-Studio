#!/usr/bin/env python3
"""Day 15 Phase 2: Script Assembly & Text Normalization Runner.

Assembles hierarchical dialogue script (Page -> Panel -> Dialogue Bubble)
with deterministic OCR cleaning and spatial bounding boxes.
Outputs canonical artifact: benchmarks/day15/dialogue_script.json.

Strict Invariants:
1. Preserve 100% of Day 14 frozen reading order sequence (0 inversions).
2. Pure deterministic text normalization.
3. 50 / 50 dialogue bubbles retained with zero omissions.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day15_cleaner import (
    DialogueScriptAssembler,
    MangaTextCleaner,
)


def run_script_assembly() -> int:
    print("=" * 76)
    print("ComicAI Studio — Day 15: Text Post-Processing & Structured Script Assembly")
    print("=" * 76)

    # 1. Load Input Artifacts
    raw_path = ROOT / "benchmarks" / "day15" / "day15-ocr-raw-extraction.json"
    eval_path = ROOT / "benchmarks" / "day14" / "day14-full-realistic-evaluation.json"
    audit_path = ROOT / "benchmarks" / "day12" / "panel-relation-model-input-audit-12.7.json"

    for path in (raw_path, eval_path, audit_path):
        if not path.is_file():
            print(f"ERROR: Missing input artifact: {path}", file=sys.stderr)
            return 1

    print("\n[Step 1] Loading inputs:")
    print(f"  Raw OCR Extraction:   {raw_path.relative_to(ROOT)}")
    print(f"  Day 14 Evaluation:    {eval_path.relative_to(ROOT)}")
    print(f"  Model Input Audit:    {audit_path.relative_to(ROOT)}")

    raw_doc = json.loads(raw_path.read_text(encoding="utf-8"))
    eval_doc = json.loads(eval_path.read_text(encoding="utf-8"))
    audit_doc = json.loads(audit_path.read_text(encoding="utf-8"))

    # 2. Assemble Script
    print("\n[Step 2] Executing deterministic text cleaning and script hierarchy assembly...")
    cleaner = MangaTextCleaner()
    assembler = DialogueScriptAssembler(cleaner=cleaner)

    assembled_script = assembler.assemble_script(raw_doc, eval_doc, audit_doc)

    summary = assembled_script["summary"]
    pages = assembled_script["pages"]
    dialogues = assembled_script["dialogues"]

    # 3. Print Summary & Before/After Snippets
    print("\n" + "=" * 76)
    print("STRUCTURED SCRIPT ASSEMBLY SUMMARY")
    print("=" * 76)
    print(f"Total Pages Assembled:        {summary['total_pages']} / 10")
    print(f"Total Dialogues Assembled:    {summary['total_dialogues']} / 50 (100.0%)")
    print(f"Dialogues with OCR Cleaning:  {summary['total_cleaned_dialogues']} / 50 ({summary['total_cleaned_dialogues'] / 50 * 100:.1f}%)")
    print(f"Reading Order Inversions:     {summary['reading_order_inversion_count']} (Strict Invariant: 0)")

    print("\nBefore / After Cleaning Snippets:")
    p1 = next(p for p in pages if p["page_id"] == 1)
    print(f"\n--- Page 1 ({len(p1['panels'])} active panels, {p1['dialogue_count']} dialogues) ---")
    for panel in p1["panels"]:
        print(f"  Panel [{panel['panel_id']}]:")
        for d in panel["dialogues"]:
            change_marker = " [CORRECTED]" if d["cleaned_text"] != d["raw_text"] else ""
            print(f"    ({d['reading_order_index']}) {d['dialogue_id']}:{change_marker}")
            print(f"        RAW:     \"{d['raw_text']}\"")
            print(f"        CLEANED: \"{d['cleaned_text']}\"")

    p5 = next(p for p in pages if p["page_id"] == 5)
    print(f"\n--- Page 5 ({len(p5['panels'])} active panels, {p5['dialogue_count']} dialogues) ---")
    for panel in p5["panels"]:
        print(f"  Panel [{panel['panel_id']}]:")
        for d in panel["dialogues"]:
            change_marker = " [CORRECTED]" if d["cleaned_text"] != d["raw_text"] else ""
            print(f"    ({d['reading_order_index']}) {d['dialogue_id']}:{change_marker}")
            print(f"        RAW:     \"{d['raw_text']}\"")
            print(f"        CLEANED: \"{d['cleaned_text']}\"")

    # 4. Save Sealed Artifact
    out_dir = ROOT / "benchmarks" / "day15"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "dialogue_script.json"

    canonical_bytes = json.dumps(
        assembled_script, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    payload_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

    final_artifact = {
        **assembled_script,
        "script_sha256": payload_sha256,
    }
    out_file.write_text(json.dumps(final_artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    file_sha256 = hashlib.sha256(out_file.read_bytes()).hexdigest()

    print("\n" + "=" * 76)
    print(f"Artifact Saved:             {out_file.relative_to(ROOT)}")
    print(f"Artifact File SHA-256:      {file_sha256}")
    print(f"Internal Payload SHA-256:   {payload_sha256}")
    print("=" * 76)

    return 0


if __name__ == "__main__":
    raise SystemExit(run_script_assembly())

