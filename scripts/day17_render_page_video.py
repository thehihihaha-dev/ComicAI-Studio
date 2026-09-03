#!/usr/bin/env python3
"""Day 17 Phase 2: 9:16 Vertical Video Compositing & Ken Burns Motion Renderer Runner.

Transforms static comic panels and synthesized live audio into an animated
9:16 vertical MP4 video (1080x1920) with smooth Ken Burns camera motion and zero A/V drift.

Target: artifacts/video/day17/page_01_preview.mp4
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day13_assignment import DeterministicRegionAssigner
from src.pipeline.research.day13_harness import NormalizedBox
from src.pipeline.research.day14_dualsolver import solve_advanced_edge_cases
from src.pipeline.research.day17_video import (
    PanelMotionPlanner,
    VerticalFrameBuilder,
    VideoSynthesizer,
)


def render_page_1_video() -> int:
    print("=" * 76)
    print("ComicAI Studio — Day 17: 9:16 Vertical Video Compositing & Motion Engine")
    print("=" * 76)

    # 1. Inputs Verification
    audio_path = ROOT / "artifacts" / "audio" / "day17" / "previews" / "page_01_full.mp3"
    audit_path = ROOT / "benchmarks" / "day12" / "panel-relation-model-input-audit-12.7.json"
    manifest_path = ROOT / "benchmarks" / "day17" / "live_audio_manifest.json"

    for p in (audio_path, audit_path, manifest_path):
        if not p.is_file():
            print(f"ERROR: Missing input: {p}", file=sys.stderr)
            return 1

    print("\n[Step 1] Loading inputs:")
    print(f"  Audio Preview:        {audio_path.relative_to(ROOT)}")
    print(f"  Live Audio Manifest:  {manifest_path.relative_to(ROOT)}")

    audit_doc = json.loads(audit_path.read_text(encoding="utf-8"))
    manifest_doc = json.loads(manifest_path.read_text(encoding="utf-8"))

    p1_audit = next(p for p in audit_doc["runtime_phase"]["pages"] if p["page_order"] == 1)
    w, h = p1_audit["image_dimensions"]
    img_path = ROOT / p1_audit["source_path"]

    # 2. Resolve Page 1 Panels and Dialogues
    print(f"\n[Step 2] Resolving Page 1 panel geometry and timeline:")
    print(f"  Source Image:         {img_path.relative_to(ROOT)} ({w}x{h})")

    existing_pans = [
        NormalizedBox(
            Decimal(str(p["bbox"][0])),
            Decimal(str(p["bbox"][1])),
            Decimal(str(p["bbox"][2])),
            Decimal(str(p["bbox"][3])),
            p["panel_id"],
        )
        for p in p1_audit["realistic_selected_panels"]
    ]
    regs = [
        NormalizedBox(
            Decimal(str(r["bbox"][0])),
            Decimal(str(r["bbox"][1])),
            Decimal(str(r["bbox"][2])),
            Decimal(str(r["bbox"][3])),
            r["id"],
        )
        for r in p1_audit["persisted_logical_regions"]
    ]

    final_pans = solve_advanced_edge_cases(1, img_path, existing_pans, regs, w, h)
    panel_bboxes = {
        p.panel_id: [float(p.x1), float(p.y1), float(p.x2), float(p.y2)]
        for p in final_pans
    }
    for pid, bbox in panel_bboxes.items():
        print(f"    Panel [{pid}]: {bbox}")

    # Gather Page 1 dialogues with live timestamps
    p1_dialogues = [d for d in manifest_doc["dialogues"] if d["page_id"] == 1]
    print(f"  Page 1 Active Dialogues: {len(p1_dialogues)} entries")

    # 3. Output Directory
    out_dir = ROOT / "artifacts" / "video" / "day17"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_video_path = out_dir / "page_01_preview.mp4"

    # 4. Synthesize Video
    print(f"\n[Step 3] Rendering 1080x1920 vertical video frames with Ken Burns camera motion...")
    start_time = time.time()

    frame_builder = VerticalFrameBuilder(
        canvas_width=1080,
        canvas_height=1920,
        max_fg_width=980,
        max_fg_height=1500,
        border_width=4,
        border_color=(255, 255, 255),
    )
    motion_planner = PanelMotionPlanner()
    synthesizer = VideoSynthesizer(
        frame_builder=frame_builder,
        motion_planner=motion_planner,
    )

    meta = synthesizer.render_page_video(
        image_path=img_path,
        panel_bboxes=panel_bboxes,
        page_bubbles=p1_dialogues,
        audio_path=audio_path,
        output_path=out_video_path,
        fps=30.0,
    )
    elapsed = time.time() - start_time

    # 5. Print Execution Report
    print("\n" + "=" * 76)
    print("9:16 VERTICAL VIDEO RENDERING REPORT")
    print("=" * 76)
    print(f"Output Video:                 {meta['output_path']}")
    print(f"Resolution:                   {meta['resolution'][0]} x {meta['resolution'][1]} (9:16 Vertical)")
    print(f"Frame Rate:                   {meta['fps']} fps")
    print(f"Total Visual Frames:          {meta['total_frames']} frames")
    print(f"Visual Video Duration:        {meta['video_duration_sec']:.3f} seconds")
    print(f"Physical Audio Duration:      {meta['audio_duration_sec']:.3f} seconds")
    print(f"Audio-Visual Drift:           {meta['drift_sec']:.4f} seconds (Zero Drift: < 1 frame)")
    print(f"Rendering Time:               {elapsed:.2f} seconds")
    print(f"File Size:                    {meta['file_size_bytes']} bytes ({meta['file_size_bytes'] / 1024 / 1024:.2f} MB)")
    print(f"SHA-256 Digest:               {meta['file_sha256']}")

    print("\nShot-by-Shot Camera Timeline Breakdown:")
    for seg in meta["segments"]:
        shot_t = seg.get("shot_type", "SHOT")
        print(f"  Shot {seg['segment_index'] + 1} [{shot_t}]:")
        print(f"      Dialogue:    {', '.join(seg['dialogue_ids'])}")
        print(f"      Panel ID:    {seg['panel_id']}")
        print(f"      Time Window: {seg['start_sec']:.3f}s -> {seg['end_sec']:.3f}s (duration: {seg['duration_sec']:.3f}s)")
        print(f"      Motion:      Zoom {seg['zoom_start']:.2f}x -> {seg['zoom_end']:.2f}x | Pan {seg['pan_start']} -> {seg['pan_end']}")
    print("=" * 76)

    return 0


if __name__ == "__main__":
    raise SystemExit(render_page_1_video())

