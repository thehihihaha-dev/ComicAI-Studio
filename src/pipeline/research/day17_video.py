"""Day 17 Phase 2: 9:16 Vertical Video Compositing & Ken Burns Motion Engine.

Provides:
1. VerticalFrameBuilder: Generates 1080x1920 canvas with Gaussian-blurred backdrop
   and aspect-ratio-preserved foreground panel framing.
2. PanelMotionPlanner: Maps dialogue timelines and panel transitions into smooth
   Ken Burns camera zoom and pan keyframes.
3. VideoSynthesizer: High-performance OpenCV frame renderer with FFmpeg audio muxer
   producing broadcast-ready 9:16 vertical MP4 video with zero A/V drift.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

import cv2
import imageio_ffmpeg
import mutagen.mp3
import numpy as np

logger = logging.getLogger(__name__)


class VerticalFrameBuilder:
    """Composites a 1080x1920 vertical canvas with blurred backdrop and centered panel."""

    def __init__(
        self,
        canvas_width: int = 1080,
        canvas_height: int = 1920,
        max_fg_width: int = 980,
        max_fg_height: int = 1500,
        border_width: int = 4,
        border_color: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.max_fg_width = max_fg_width
        self.max_fg_height = max_fg_height
        self.border_width = border_width
        self.border_color = border_color

    def build_frame(
        self,
        panel_crop: np.ndarray,
        zoom_scale: float = 1.0,
        pan_offset: tuple[int, int] = (0, 0),
    ) -> np.ndarray:
        """Compose a single 1080x1920 vertical frame.

        Args:
            panel_crop: BGR image array of the comic panel.
            zoom_scale: Ken Burns zoom multiplier (e.g. 1.0 to 1.06).
            pan_offset: (dx, dy) camera offset in pixels.

        Returns:
            np.ndarray: 1080x1920x3 BGR frame.
        """
        h_crop, w_crop = panel_crop.shape[:2]

        # 1. Background: Cover canvas and apply heavy Gaussian blur + darkening
        bg = cv2.resize(panel_crop, (self.canvas_width, self.canvas_height), interpolation=cv2.INTER_LINEAR)
        bg = cv2.GaussianBlur(bg, (51, 51), 30)
        bg = (bg * 0.35).astype(np.uint8)

        # 2. Foreground: Scale preserving aspect ratio with Ken Burns zoom
        base_scale = min(self.max_fg_width / float(w_crop), self.max_fg_height / float(h_crop))
        final_scale = base_scale * float(zoom_scale)

        fg_w = max(10, int(round(float(w_crop) * final_scale)))
        fg_h = max(10, int(round(float(h_crop) * final_scale)))
        fg = cv2.resize(panel_crop, (fg_w, fg_h), interpolation=cv2.INTER_LANCZOS4)

        # 3. Add clean subtle border
        if self.border_width > 0:
            fg = cv2.copyMakeBorder(
                fg,
                self.border_width,
                self.border_width,
                self.border_width,
                self.border_width,
                cv2.BORDER_CONSTANT,
                value=self.border_color,
            )
            fg_h, fg_w = fg.shape[:2]

        # 4. Center foreground on canvas with pan offset
        center_x = self.canvas_width // 2 + pan_offset[0]
        center_y = self.canvas_height // 2 + pan_offset[1]

        x1 = center_x - fg_w // 2
        y1 = center_y - fg_h // 2
        x2 = x1 + fg_w
        y2 = y1 + fg_h

        # Compute overlap with canvas boundaries
        canvas_x1 = max(0, x1)
        canvas_y1 = max(0, y1)
        canvas_x2 = min(self.canvas_width, x2)
        canvas_y2 = min(self.canvas_height, y2)

        crop_x1 = canvas_x1 - x1
        crop_y1 = canvas_y1 - y1
        crop_x2 = crop_x1 + (canvas_x2 - canvas_x1)
        crop_y2 = crop_y1 + (canvas_y2 - canvas_y1)

        if canvas_x2 > canvas_x1 and canvas_y2 > canvas_y1:
            bg[canvas_y1:canvas_y2, canvas_x1:canvas_x2] = fg[crop_y1:crop_y2, crop_x1:crop_x2]

        return bg


class PanelMotionPlanner:
    """Plans camera motion keyframes across comic panels synchronized with audio timeline."""

    def plan_panel_segments(
        self,
        page_bubbles: Sequence[dict[str, Any]],
        total_audio_duration_sec: float,
        pause_between_bubbles_ms: int = 150,
        pause_between_panels_ms: int = 300,
    ) -> list[dict[str, Any]]:
        """Plan distinct camera shots and sub-panel dynamics per dialogue bubble."""
        if not page_bubbles:
            return []

        # 1. Compute timeline for each bubble
        bubble_timelines: list[dict[str, Any]] = []
        curr_t = 0.0
        prev_panel_id: str | None = None

        for i, b in enumerate(page_bubbles):
            pid = b.get("panel_id", "")
            if "start_ms" in b and "end_ms" in b:
                start_sec = float(b["start_ms"]) / 1000.0
                end_sec = float(b["end_ms"]) / 1000.0
            else:
                if i > 0:
                    pause = (
                        pause_between_bubbles_ms
                        if pid == prev_panel_id
                        else pause_between_panels_ms
                    ) / 1000.0
                    curr_t += pause
                dur = float(b.get("physical_duration_sec", b.get("physical_duration_ms", 1000) / 1000.0))
                start_sec = curr_t
                end_sec = start_sec + dur
                curr_t = end_sec
                prev_panel_id = pid

            bubble_timelines.append({
                "bubble": b,
                "start_sec": start_sec,
                "end_sec": end_sec,
            })

        # 2. Build sub-shots per dialogue bubble
        segments: list[dict[str, Any]] = []
        num_bubbles = len(bubble_timelines)

        for i, item in enumerate(bubble_timelines):
            b = item["bubble"]
            did = b.get("dialogue_id", "")
            pid = b.get("panel_id", "")
            start_sec = item["start_sec"]

            # Next shot starts when next bubble starts (including pause) or at total duration
            if i < num_bubbles - 1:
                end_sec = bubble_timelines[i + 1]["start_sec"]
            else:
                end_sec = total_audio_duration_sec

            # Cinematic camera motion profiles
            if did == "D_P01_01":
                # Shot 1: Establishing Cathedral stained glass window
                zoom_start, zoom_end = 1.00, 1.05
                pan_start, pan_end = (0, 0), (0, 0)
                shot_type = "ESTABLISHING_WINDOW"
            elif did == "D_P01_02":
                # Shot 2A: Medium shot on holding hands & ring
                zoom_start, zoom_end = 1.00, 1.04
                pan_start, pan_end = (0, 5), (0, 0)
                shot_type = "MEDIUM_HANDS"
            elif did == "D_P01_03":
                # Shot 2B: Dynamic punch cut & zoom into the wedding ring finger
                zoom_start, zoom_end = 1.05, 1.12
                pan_start, pan_end = (0, 0), (0, -15)
                shot_type = "CLOSEUP_RING"
            elif did == "D_P01_04":
                # Shot 3: Snappy cut directly to Rin's face with emotional punch zoom
                zoom_start, zoom_end = 1.00, 1.08
                pan_start, pan_end = (0, 0), (0, -10)
                shot_type = "EMOTIONAL_PUNCH_RIN"
            else:
                # Generic rules: alternate zoom directions
                if i % 2 == 0:
                    zoom_start, zoom_end = 1.00, 1.06
                    pan_start, pan_end = (0, 10), (0, -10)
                else:
                    zoom_start, zoom_end = 1.05, 1.00
                    pan_start, pan_end = (0, -10), (0, 10)
                shot_type = "GENERIC_SHOT"

            segments.append({
                "segment_index": i,
                "panel_id": pid,
                "dialogue_id": did,
                "shot_type": shot_type,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "duration_sec": max(0.1, end_sec - start_sec),
                "zoom_start": zoom_start,
                "zoom_end": zoom_end,
                "pan_start": pan_start,
                "pan_end": pan_end,
                "dialogue_ids": [did],
            })

        # Ensure boundary alignment
        if segments:
            segments[0]["start_sec"] = 0.0
            segments[-1]["end_sec"] = total_audio_duration_sec
            segments[-1]["duration_sec"] = segments[-1]["end_sec"] - segments[-1]["start_sec"]

        return segments


class VideoSynthesizer:
    """Renders visual animation frames and muxes audio into MP4."""

    def __init__(
        self,
        frame_builder: VerticalFrameBuilder | None = None,
        motion_planner: PanelMotionPlanner | None = None,
    ) -> None:
        self.frame_builder = frame_builder or VerticalFrameBuilder()
        self.motion_planner = motion_planner or PanelMotionPlanner()
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def render_page_video(
        self,
        image_path: Path,
        panel_bboxes: dict[str, list[float]],
        page_bubbles: Sequence[dict[str, Any]],
        audio_path: Path,
        output_path: Path,
        fps: float = 30.0,
    ) -> dict[str, Any]:
        """Render complete 9:16 MP4 video for a comic page.

        Returns:
            dict: Synthesis summary and integrity metrics.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Load Source Image and Audio Info
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise FileNotFoundError(f"Cannot load page image: {image_path}")

        audio_info = mutagen.mp3.MP3(str(audio_path)).info
        audio_duration_sec = float(audio_info.length)

        # 2. Plan Panel Motion Segments
        segments = self.motion_planner.plan_panel_segments(page_bubbles, audio_duration_sec)

        # 3. Pre-crop Panel Images
        panel_crops: dict[str, np.ndarray] = {}
        img_h, img_w = img_bgr.shape[:2]

        for pid, bbox in panel_bboxes.items():
            x1 = max(0, min(img_w - 1, int(round(bbox[0]))))
            y1 = max(0, min(img_h - 1, int(round(bbox[1]))))
            x2 = max(x1 + 1, min(img_w, int(round(bbox[2]))))
            y2 = max(y1 + 1, min(img_h, int(round(bbox[3]))))
            panel_crops[pid] = img_bgr[y1:y2, x1:x2]

        # 4. Generate Visual Animation via cv2.VideoWriter
        total_frames = int(round(audio_duration_sec * fps))
        temp_video_path = output_path.with_name(f"temp_{output_path.name}")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(
            str(temp_video_path),
            fourcc,
            fps,
            (self.frame_builder.canvas_width, self.frame_builder.canvas_height),
        )

        for frame_idx in range(total_frames):
            current_time = float(frame_idx) / fps

            # Find active segment
            active_seg = segments[-1]
            for seg in segments:
                if seg["start_sec"] <= current_time < seg["end_sec"]:
                    active_seg = seg
                    break

            pid = active_seg["panel_id"]
            crop = panel_crops.get(pid, img_bgr)

            # Smoothstep interpolation: 3*a^2 - 2*a^3
            seg_dur = max(0.001, active_seg["duration_sec"])
            alpha = min(1.0, max(0.0, (current_time - active_seg["start_sec"]) / seg_dur))
            eased_alpha = alpha * alpha * (3.0 - 2.0 * alpha)

            zoom = active_seg["zoom_start"] + (active_seg["zoom_end"] - active_seg["zoom_start"]) * eased_alpha
            pan_x = int(round(active_seg["pan_start"][0] + (active_seg["pan_end"][0] - active_seg["pan_start"][0]) * eased_alpha))
            pan_y = int(round(active_seg["pan_start"][1] + (active_seg["pan_end"][1] - active_seg["pan_start"][1]) * eased_alpha))

            frame = self.frame_builder.build_frame(crop, zoom_scale=zoom, pan_offset=(pan_x, pan_y))
            writer.write(frame)

        writer.release()

        # 5. Mux Video and Audio via FFmpeg (H.264 + AAC)
        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-i", str(temp_video_path),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if temp_video_path.is_file():
            temp_video_path.unlink()

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg muxing failed: {proc.stderr}")

        # 6. Calculate Metrics and Integrity Hash
        video_duration_sec = float(total_frames) / fps
        drift_sec = abs(video_duration_sec - audio_duration_sec)
        file_size_bytes = output_path.stat().st_size
        file_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
        try:
            rel_output_path = str(output_path.relative_to(ROOT))
        except ValueError:
            rel_output_path = str(output_path)

        return {
            "output_path": rel_output_path,
            "resolution": [self.frame_builder.canvas_width, self.frame_builder.canvas_height],
            "fps": fps,
            "total_frames": total_frames,
            "video_duration_sec": round(video_duration_sec, 3),
            "audio_duration_sec": round(audio_duration_sec, 3),
            "drift_sec": round(drift_sec, 4),
            "file_size_bytes": file_size_bytes,
            "file_sha256": file_sha256,
            "segments": segments,
        }
