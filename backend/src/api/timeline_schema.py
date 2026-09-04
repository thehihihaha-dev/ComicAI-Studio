"""Pydantic schemas for the Timeline JSON Contract (CapCut style Web Editor).

Decouples AI draft generation from final video rendering, enabling interactive
client-side preview and non-destructive visual/motion adjustments.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class MotionConfig(BaseModel):
    """Ken Burns camera motion parameters for a visual clip."""
    model_config = ConfigDict(extra="ignore")

    zoom_start: float = Field(default=1.00, description="Camera zoom multiplier at clip start")
    zoom_end: float = Field(default=1.06, description="Camera zoom multiplier at clip end")
    pan_start: tuple[int, int] = Field(default=(0, 0), description="(dx, dy) pan offset in pixels at clip start")
    pan_end: tuple[int, int] = Field(default=(0, 0), description="(dx, dy) pan offset in pixels at clip end")
    easing: str = Field(default="smoothstep", description="Motion interpolation easing function ('smoothstep', 'linear')")


class BackgroundConfig(BaseModel):
    """Canvas backdrop configuration for vertical framing."""
    model_config = ConfigDict(extra="ignore")

    blur_radius: int = Field(default=51, description="Gaussian blur kernel size (odd integer)")
    darkness: float = Field(default=0.35, description="Backdrop brightness factor (0.0 to 1.0)")
    border_width: int = Field(default=4, description="Border width around foreground panel in pixels")
    border_color: tuple[int, int, int] = Field(default=(255, 255, 255), description="BGR border color")


class VisualClip(BaseModel):
    """Individual visual shot bound to a comic panel or sub-panel."""
    model_config = ConfigDict(extra="ignore")

    clip_id: str = Field(..., description="Unique visual clip identifier")
    panel_id: str = Field(..., description="Mapped comic panel ID")
    bbox: list[float] = Field(..., description="Panel bounding box [x1, y1, x2, y2] in original image coordinates")
    start_time: float = Field(..., ge=0.0, description="Timeline start time in seconds")
    end_time: float = Field(..., ge=0.0, description="Timeline end time in seconds")
    duration: float = Field(..., ge=0.0, description="Clip duration in seconds")
    shot_type: str = Field(default="PANEL_SHOT", description="Cinematic shot category (ESTABLISHING, MEDIUM, CLOSEUP, PUNCH)")
    motion: MotionConfig = Field(default_factory=MotionConfig, description="Camera pan/zoom animation config")
    background: BackgroundConfig = Field(default_factory=BackgroundConfig, description="Backdrop styling config")


class AudioClip(BaseModel):
    """Individual dialogue audio speech segment on the audio track."""
    model_config = ConfigDict(extra="ignore")

    clip_id: str = Field(..., description="Unique audio clip identifier")
    dialogue_id: str = Field(..., description="Original dialogue bubble ID")
    speaker_label: str = Field(default="UNKNOWN", description="Diarized character speaker name")
    voice_id: str = Field(..., description="TTS voice identifier")
    text: str = Field(..., description="Synthesized spoken text")
    file_path: str = Field(..., description="Path to audio file (.mp3 / .wav)")
    start_time: float = Field(..., ge=0.0, description="Audio playback start time in seconds")
    end_time: float = Field(..., ge=0.0, description="Audio playback end time in seconds")
    duration: float = Field(..., ge=0.0, description="Speech duration in seconds")


class TimelineContract(BaseModel):
    """Canonical Timeline JSON Contract representing full draft state for the Web Editor."""
    model_config = ConfigDict(extra="ignore")

    version: str = Field(default="1.0.0", description="Contract schema version")
    project_id: str = Field(..., description="ComicAI project identifier")
    page_id: int = Field(default=1, description="Page index or number")
    source_image_path: str = Field(..., description="Path to original comic page image")
    image_dimensions: tuple[int, int] = Field(default=(900, 1280), description="(width, height) of source image")
    canvas_size: tuple[int, int] = Field(default=(1080, 1920), description="(width, height) of 9:16 vertical canvas")
    fps: float = Field(default=30.0, description="Target video frame rate")
    total_duration: float = Field(..., ge=0.0, description="Total page timeline runtime in seconds")
    visual_clips: list[VisualClip] = Field(default_factory=list, description="Ordered visual camera shots")
    audio_clips: list[AudioClip] = Field(default_factory=list, description="Ordered dialogue audio speech track")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Supplementary pipeline and audit metadata")


class DraftRequest(BaseModel):
    """Request payload to generate a timeline draft from an existing image path."""
    model_config = ConfigDict(extra="ignore")

    image_path: str | None = Field(default=None, description="Path to source comic image on server")
    project_id: str = Field(default="default_project", description="Project ID")
    page_order: int = Field(default=1, description="Page sequence number")


class RenderRequest(BaseModel):
    """Request payload to render final 9:16 MP4 video from a Timeline Contract."""
    model_config = ConfigDict(extra="ignore")

    timeline: TimelineContract = Field(..., description="Client-modified Timeline Contract")
    output_filename: str | None = Field(default=None, description="Optional custom video file name")


class RenderResponse(BaseModel):
    """Response payload returned after video synthesis completes."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(default="success", description="Render status ('success', 'error')")
    video_path: str = Field(..., description="Relative file path of rendered MP4")
    video_url: str = Field(..., description="Public or static URL to stream the video")
    resolution: list[int] = Field(default_factory=lambda: [1080, 1920], description="[width, height] in pixels")
    fps: float = Field(default=30.0, description="Encoded frames per second")
    total_frames: int = Field(..., description="Total visual frames rendered")
    duration_sec: float = Field(..., description="Total visual video duration in seconds")
    audio_drift_sec: float = Field(..., description="Audio-visual drift delta in seconds")
    file_size_bytes: int = Field(..., description="Rendered file size in bytes")
    file_sha256: str = Field(..., description="Cryptographic SHA-256 digest of rendered video")

