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
        max_fg_width: int = 1040,
        max_fg_height: int = 1680,
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

        # 2. Foreground: Scale preserving aspect ratio with Ken Burns zoom and 1.18x prominence
        base_scale = min(self.max_fg_width / float(w_crop), self.max_fg_height / float(h_crop)) * 1.18
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

    def _resolve_image(self, path_str: str | None, cache: dict[str, np.ndarray]) -> np.ndarray:
        """Loads and caches image from disk, falling back to a synthetic canvas if missing."""
        if not path_str:
            path_str = "default_page.jpg"
        if path_str in cache:
            return cache[path_str]

        clean_str = path_str
        if "://" in clean_str:
            clean_str = clean_str.split("://", 1)[1]
            if "/" in clean_str:
                clean_str = clean_str.split("/", 1)[1]
        clean_str = clean_str.lstrip("/")

        candidate_paths = [
            Path(path_str),
            Path(clean_str),
            ROOT / clean_str,
            ROOT / "backend" / clean_str,
            Path(__file__).resolve().parents[2] / clean_str,
            Path(__file__).resolve().parents[2] / "uploads" / Path(clean_str).name,
            ROOT / "backend" / "uploads" / Path(clean_str).name,
        ]

        img: np.ndarray | None = None
        for p in candidate_paths:
            if p.is_file():
                img = cv2.imread(str(p))
                if img is not None and img.size > 0:
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

    def _resolve_audio_file(self, raw_path: str | Path | None) -> Path | None:
        """Resolves audio file path across relative, absolute, and upload locations."""
        if not raw_path:
            return None
        p_str = str(raw_path).strip()
        if "://" in p_str:
            p_str = p_str.split("://", 1)[1]
            if "/" in p_str:
                p_str = p_str.split("/", 1)[1]
        clean_str = p_str.lstrip("/")

        candidates = [
            Path(str(raw_path)),
            Path(clean_str),
            ROOT / clean_str,
            ROOT / "backend" / clean_str,
            Path.cwd() / clean_str,
            Path(__file__).resolve().parents[2] / clean_str,
            Path(__file__).resolve().parents[2] / "uploads" / "audio" / Path(clean_str).name,
            ROOT / "backend" / "uploads" / "audio" / Path(clean_str).name,
            ROOT / "backend" / "uploads" / "audio" / "default_bgm.mp3",
        ]
        for c in candidates:
            if c.is_file() and c.stat().st_size > 0:
                return c
        return None

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

            x1_r, y1_r, x2_r, y2_r = vc.bbox
            if x2_r <= 1.05 and y2_r <= 1.05:
                x1_r *= w_img
                y1_r *= h_img
                x2_r *= w_img
                y2_r *= h_img

            bx1 = max(0, min(w_img - 1, int(round(x1_r))))
            by1 = max(0, min(h_img - 1, int(round(y1_r))))
            bx2 = max(bx1 + 1, min(w_img, int(round(x2_r))))
            by2 = max(by1 + 1, min(h_img, int(round(y2_r))))

            crop = img[by1:by2, bx1:bx2]
            if crop.size == 0:
                crop = img
            clip_crops[vc.clip_id] = crop

        # Fallback default crop if visual_clips is empty
        default_img = self._resolve_image(timeline.source_image_path, image_cache)

        # 2. Stage A: Voice Narration Assembly
        temp_voice_path = output_path.with_name(f"temp_voice_{output_path.stem}.wav")
        total_audio_ms = int(round(total_dur * 1000.0))

        preview_audio_meta = timeline.metadata.get("preview_audio_url") or timeline.metadata.get("preview_audio_path")
        preview_full_file = self._resolve_audio_file(preview_audio_meta)

        if preview_full_file and preview_full_file.is_file() and preview_full_file.stat().st_size > 1000:
            cmd_conv = [
                self.ffmpeg_exe, "-y", "-i", str(preview_full_file),
                "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
                "-t", str(total_dur), str(temp_voice_path)
            ]
            subprocess.run(cmd_conv, capture_output=True, check=True)
        else:
            stitched_audio = bytearray()
            curr_pos_ms = 0

            if timeline.audio_clips:
                for ac in timeline.audio_clips:
                    clip_file = self._resolve_audio_file(ac.file_path)
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
            else:
                stitched_audio.extend(generate_mp3_silence(total_audio_ms))

            temp_mp3 = output_path.with_name(f"temp_voice_raw_{output_path.stem}.mp3")
            temp_mp3.write_bytes(stitched_audio)
            cmd_conv = [
                self.ffmpeg_exe, "-y", "-i", str(temp_mp3),
                "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
                "-t", str(total_dur), str(temp_voice_path)
            ]
            subprocess.run(cmd_conv, capture_output=True, check=True)
            if temp_mp3.is_file():
                temp_mp3.unlink()

        if not temp_voice_path.is_file() or temp_voice_path.stat().st_size == 0:
            raise RuntimeError(f"Voice narration track generation failed: {temp_voice_path} is empty or missing")

        # 3. Stage B: Resolve BGM and Audio Ducking Mixing into final_audio.wav
        final_audio_path = output_path.with_name(f"final_audio_{output_path.stem}.wav")
        resolved_bgm: Path | None = None
        if bgm_path:
            resolved_bgm = self._resolve_audio_file(bgm_path)
        if not resolved_bgm and timeline.metadata.get("bgm_path"):
            bgm_meta = str(timeline.metadata["bgm_path"])
            if "default_bgm.mp3" not in bgm_meta:
                resolved_bgm = self._resolve_audio_file(bgm_meta)

        voice_intervals = timeline.metadata.get("ducking", {}).get("voice_intervals", [])
        if not voice_intervals and timeline.audio_clips:
            voice_intervals = [(ac.start_time, ac.end_time) for ac in timeline.audio_clips]

        if resolved_bgm and resolved_bgm.is_file() and resolved_bgm.stat().st_size > 1000:
            duck_filter = build_ffmpeg_ducking_filter(voice_intervals)
            cmd_mix = [
                self.ffmpeg_exe, "-y",
                "-i", str(temp_voice_path),
                "-stream_loop", "-1", "-i", str(resolved_bgm),
                "-filter_complex",
                f"[1:a]{duck_filter}[ducked_bgm]; [0:a][ducked_bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "[aout]",
                "-c:a", "pcm_s16le",
                "-t", str(total_dur),
                str(final_audio_path),
            ]
        else:
            cmd_mix = [
                self.ffmpeg_exe, "-y",
                "-i", str(temp_voice_path),
                "-c:a", "pcm_s16le",
                "-t", str(total_dur),
                str(final_audio_path),
            ]

        proc_mix = subprocess.run(cmd_mix, capture_output=True, text=True)
        if proc_mix.returncode != 0:
            logger.error("Audio mixing error: %s", proc_mix.stderr)
            raise RuntimeError(f"Audio mixing failed: {proc_mix.stderr}")

        if not final_audio_path.is_file() or final_audio_path.stat().st_size == 0:
            raise RuntimeError(f"Generated final audio track is invalid or empty: {final_audio_path} (size: 0 bytes)")

        # 4. Stage C: Visual Animation Frames via cv2.VideoWriter
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

                m = active_clip.motion
                is_punch = (
                    active_clip.shot_type.lower().startswith("punch")
                    or "punch" in active_clip.clip_id.lower()
                    or (m.zoom_end > 1.2 and m.pan_end[1] == 0)
                )

                if is_punch:
                    t_punch = min(1.0, max(0.0, (t - active_clip.start_time) / 0.4))
                    eased_punch = t_punch * t_punch * (3.0 - 2.0 * t_punch)
                    zoom = m.zoom_start + (m.zoom_end - m.zoom_start) * eased_punch + 0.01 * alpha
                    pan_x = int(round(m.pan_start[0] + (m.pan_end[0] - m.pan_start[0]) * eased_punch))
                    pan_y = int(round(m.pan_start[1] + (m.pan_end[1] - m.pan_start[1]) * eased_punch))
                else:
                    if m.easing == "smoothstep":
                        eased_alpha = alpha * alpha * (3.0 - 2.0 * alpha)
                    else:
                        eased_alpha = alpha
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

        # 5. Stage D: Final FFmpeg Muxing of Video + Final Audio
        cmd_mux = [
            self.ffmpeg_exe, "-y",
            "-i", str(temp_video_path),
            "-i", str(final_audio_path),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]

        proc = subprocess.run(cmd_mux, capture_output=True, text=True)

        # Cleanup temporary files
        if temp_video_path.is_file():
            temp_video_path.unlink()
        if temp_voice_path.is_file():
            temp_voice_path.unlink()
        if final_audio_path.is_file():
            final_audio_path.unlink()

        if proc.returncode != 0:
            logger.error("FFmpeg execution error: %s", proc.stderr)
            raise RuntimeError(f"FFmpeg muxing failed: {proc.stderr}")

        # 6. Stream & Output Verification
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Render failed: output file {output_path} does not exist or is empty")

        probe_proc = subprocess.run([self.ffmpeg_exe, "-i", str(output_path)], capture_output=True, text=True)
        probe_err = probe_proc.stderr
        has_video_stream = "Video:" in probe_err
        has_audio_stream = "Audio:" in probe_err

        if not has_video_stream:
            raise RuntimeError("Render validation failed: Output MP4 has no video stream!")
        if not has_audio_stream:
            raise RuntimeError("Render validation failed: Output MP4 has no audio stream!")

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

