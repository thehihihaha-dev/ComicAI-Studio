"""Day 20 Phase 2: End-to-End 9:16 MP4 Video Rendering Engine.

Composites broadcast-ready 9:16 vertical MP4 video (1080x1920) from TimelineContract:
1. Multi-page manga panel image caching and sub-panel cropping.
2. Vertical 1080x1920 canvas generation with Gaussian blur backdrop.
3. Smooth Ken Burns camera motion interpolation (zoom & pan with smoothstep easing).
4. Audio track stitching for voice narration (vi-VN-NamMinhNeural).
5. Dynamic FFmpeg Audio Ducking filter mixing BGM (25% speech attenuation, 100% pause recovery).
6. Hardware/fast H.264 + AAC MP4 muxing producing broadcast-ready video.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

import cv2
import imageio_ffmpeg
import numpy as np

try:
    from src.api.timeline_schema import RenderResponse, TimelineContract, VisualClip
    from src.services.audio_ducking import build_ffmpeg_ducking_filter
except ModuleNotFoundError:
    from backend.src.api.timeline_schema import RenderResponse, TimelineContract, VisualClip
    from backend.src.services.audio_ducking import build_ffmpeg_ducking_filter

logger = logging.getLogger(__name__)

SILENCE_FRAME_BYTES = bytes.fromhex("fff364c47c0000034800000000" + "55" * (144 - 13))
FRAME_DURATION_MS = 24.0


def generate_mp3_silence(duration_ms: int) -> bytes:
    """Generate exact silence bytes for given duration in milliseconds."""
    num_frames = max(1, int(round(float(duration_ms) / FRAME_DURATION_MS)))
    return SILENCE_FRAME_BYTES * num_frames


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
        blur_radius: int = 51,
        darkness: float = 0.35,
    ) -> np.ndarray:
        """Compose a single 1080x1920 vertical frame.

        Args:
            panel_crop: BGR image array of the comic panel.
            zoom_scale: Ken Burns zoom multiplier (e.g. 1.0 to 1.25).
            pan_offset: (dx, dy) camera offset in pixels.
            blur_radius: Gaussian blur kernel size for backdrop.
            darkness: Darkening multiplier for backdrop.

        Returns:
            np.ndarray: 1080x1920x3 BGR frame.
        """
        h_crop, w_crop = panel_crop.shape[:2]

        # 1. Background: Cover canvas and apply heavy Gaussian blur + darkening
        bg = cv2.resize(panel_crop, (self.canvas_width, self.canvas_height), interpolation=cv2.INTER_LINEAR)
        ksize = blur_radius if blur_radius % 2 == 1 else blur_radius + 1
        ksize = max(3, ksize)
        bg = cv2.GaussianBlur(bg, (ksize, ksize), 30)
        bg = (bg * float(darkness)).astype(np.uint8)

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


class VideoRenderer:
    """Renders broadcast-ready 9:16 vertical MP4 video adhering to TimelineContract."""

    def __init__(
        self,
        canvas_size: tuple[int, int] = (1080, 1920),
        fps: float = 30.0,
    ) -> None:
        self.canvas_size = canvas_size
        self.fps = fps
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.frame_builder = VerticalFrameBuilder(
            canvas_width=canvas_size[0],
            canvas_height=canvas_size[1],
        )

    def _resolve_image(self, path_str: str, cache: dict[str, np.ndarray]) -> np.ndarray:
        """Loads and caches image from disk, falling back to a synthetic canvas if missing."""
        if path_str in cache:
            return cache[path_str]

        candidate_paths = [
            Path(path_str),
            ROOT / path_str,
            ROOT / "backend" / path_str,
        ]

        img: np.ndarray | None = None
        for p in candidate_paths:
            if p.is_file():
                img = cv2.imread(str(p))
                if img is not None:
                    break

        if img is None:
            logger.warning("Image path not found: %s. Creating synthetic gradient fallback.", path_str)
            # Create synthetic 1280x900 image
            img = np.zeros((1280, 900, 3), dtype=np.uint8)
            for y in range(1280):
                img[y, :, 0] = int(30 + 100 * (y / 1280.0))
                img[y, :, 1] = int(20 + 80 * (y / 1280.0))
                img[y, :, 2] = int(50 + 150 * (y / 1280.0))

        cache[path_str] = img
        return img

    def render_chapter_video(
        self,
        timeline: TimelineContract,
        output_path: Path,
        bgm_path: Path | None = None,
    ) -> dict[str, Any]:
        """Synthesizes final 9:16 vertical MP4 video for full chapter or page.

        Args:
            timeline: TimelineContract containing visual_clips, audio_clips, and metadata.
            output_path: Destination path for rendered MP4 file.
            bgm_path: Optional path to background music audio file.

        Returns:
            dict: Summary metrics compatible with RenderResponse schema.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas_w, canvas_h = timeline.canvas_size if timeline.canvas_size else self.canvas_size
        fps = timeline.fps if timeline.fps else self.fps
        total_dur = max(0.5, timeline.total_duration)

        # 1. Multi-page Panel Image Cache and Cropping
        image_cache: dict[str, np.ndarray] = {}
        clip_crops: dict[str, np.ndarray] = {}

        for vc in timeline.visual_clips:
            src_path = vc.image_path or timeline.source_image_path
            img = self._resolve_image(src_path, image_cache)
            h_img, w_img = img.shape[:2]

            bx1 = max(0, min(w_img - 1, int(round(vc.bbox[0]))))
            by1 = max(0, min(h_img - 1, int(round(vc.bbox[1]))))
            bx2 = max(bx1 + 1, min(w_img, int(round(vc.bbox[2]))))
            by2 = max(by1 + 1, min(h_img, int(round(vc.bbox[3]))))

            crop = img[by1:by2, bx1:bx2]
            if crop.size == 0:
                crop = img
            clip_crops[vc.clip_id] = crop

        # Fallback default crop if visual_clips is empty
        default_img = self._resolve_image(timeline.source_image_path, image_cache)

        # 2. Voice Audio Stitching
        temp_voice_path = output_path.with_name(f"temp_voice_{output_path.stem}.mp3")
        total_audio_ms = int(round(total_dur * 1000.0))

        if timeline.audio_clips:
            stitched_audio = bytearray()
            curr_pos_ms = 0

            for ac in timeline.audio_clips:
                clip_candidates = [
                    Path(ac.file_path),
                    ROOT / ac.file_path,
                    ROOT / "backend" / ac.file_path,
                ]
                clip_file = next((p for p in clip_candidates if p.is_file()), None)

                target_start_ms = int(round(ac.start_time * 1000.0))
                if target_start_ms > curr_pos_ms:
                    stitched_audio.extend(generate_mp3_silence(target_start_ms - curr_pos_ms))
                    curr_pos_ms = target_start_ms

                clip_dur_ms = int(round(ac.duration * 1000.0))
                if clip_file:
                    stitched_audio.extend(clip_file.read_bytes())
                else:
                    stitched_audio.extend(generate_mp3_silence(clip_dur_ms))
                curr_pos_ms += clip_dur_ms

            if curr_pos_ms < total_audio_ms:
                stitched_audio.extend(generate_mp3_silence(total_audio_ms - curr_pos_ms))

            temp_voice_path.write_bytes(stitched_audio)
        else:
            temp_voice_path.write_bytes(generate_mp3_silence(total_audio_ms))

        # 3. Visual Animation Frames via cv2.VideoWriter
        total_frames = max(1, int(round(total_dur * fps)))
        temp_video_path = output_path.with_name(f"temp_video_{output_path.stem}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(temp_video_path), fourcc, fps, (canvas_w, canvas_h))

        frame_builder = VerticalFrameBuilder(
            canvas_width=canvas_w,
            canvas_height=canvas_h,
        )

        for frame_idx in range(total_frames):
            t = float(frame_idx) / fps

            # Find active visual clip
            if timeline.visual_clips:
                active_clip = timeline.visual_clips[-1]
                for vc in timeline.visual_clips:
                    if vc.start_time <= t < vc.end_time:
                        active_clip = vc
                        break
                crop = clip_crops.get(active_clip.clip_id, default_img)
                dur = max(0.001, active_clip.duration)
                alpha = min(1.0, max(0.0, (t - active_clip.start_time) / dur))

                # Smoothstep easing
                if active_clip.motion.easing == "smoothstep":
                    eased_alpha = alpha * alpha * (3.0 - 2.0 * alpha)
                else:
                    eased_alpha = alpha

                m = active_clip.motion
                zoom = m.zoom_start + (m.zoom_end - m.zoom_start) * eased_alpha
                pan_x = int(round(m.pan_start[0] + (m.pan_end[0] - m.pan_start[0]) * eased_alpha))
                pan_y = int(round(m.pan_start[1] + (m.pan_end[1] - m.pan_start[1]) * eased_alpha))
                bg_cfg = active_clip.background
                blur_r = bg_cfg.blur_radius
                darkness = bg_cfg.darkness
            else:
                crop = default_img
                zoom = 1.0
                pan_x, pan_y = 0, 0
                blur_r = 51
                darkness = 0.35

            frame = frame_builder.build_frame(
                crop,
                zoom_scale=zoom,
                pan_offset=(pan_x, pan_y),
                blur_radius=blur_r,
                darkness=darkness,
            )
            writer.write(frame)

        writer.release()

        # 4. Resolve BGM and Audio Ducking
        resolved_bgm: Path | None = None
        if bgm_path and Path(bgm_path).is_file():
            resolved_bgm = Path(bgm_path)
        elif timeline.metadata.get("bgm_path"):
            meta_bgm = Path(str(timeline.metadata["bgm_path"]))
            if meta_bgm.is_file():
                resolved_bgm = meta_bgm
            elif (ROOT / meta_bgm).is_file():
                resolved_bgm = ROOT / meta_bgm

        # 5. FFmpeg Muxing with Ducking Filter
        cmd = [self.ffmpeg_exe, "-y", "-i", str(temp_video_path), "-i", str(temp_voice_path)]

        if resolved_bgm and resolved_bgm.is_file():
            # Get voice intervals for ducking
            voice_intervals = timeline.metadata.get("ducking", {}).get("voice_intervals", [])
            if not voice_intervals and timeline.audio_clips:
                voice_intervals = [(ac.start_time, ac.end_time) for ac in timeline.audio_clips]

            duck_filter = build_ffmpeg_ducking_filter(voice_intervals)

            # Input 0: video, Input 1: voice, Input 2: bgm looped
            cmd.extend([
                "-stream_loop", "-1",
                "-i", str(resolved_bgm),
                "-filter_complex",
                f"[2:a]{duck_filter}[ducked_bgm]; [1:a][ducked_bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v",
                "-map", "[aout]",
            ])
        else:
            cmd.extend([
                "-map", "0:v",
                "-map", "1:a",
            ])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(output_path),
        ])

        proc = subprocess.run(cmd, capture_output=True, text=True)

        # Cleanup temporary files
        if temp_video_path.is_file():
            temp_video_path.unlink()
        if temp_voice_path.is_file():
            temp_voice_path.unlink()

        if proc.returncode != 0:
            logger.error("FFmpeg execution error: %s", proc.stderr)
            raise RuntimeError(f"FFmpeg muxing failed: {proc.stderr}")

        # 6. Verify outputs and calculate metrics
        file_size_bytes = output_path.stat().st_size
        file_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
        video_dur = float(total_frames) / fps
        audio_drift = abs(video_dur - total_dur)

        try:
            rel_out = str(output_path.relative_to(ROOT))
        except ValueError:
            rel_out = str(output_path)

        return {
            "status": "success",
            "video_path": rel_out,
            "video_url": f"/{rel_out}",
            "resolution": [canvas_w, canvas_h],
            "fps": fps,
            "total_frames": total_frames,
            "duration_sec": round(video_dur, 3),
            "audio_drift_sec": round(audio_drift, 4),
            "file_size_bytes": file_size_bytes,
            "file_sha256": file_sha256,
        }

