"""Day 20 Phase 1: Smart Panel Selection Engine.

Selects 6-10 optimal manga panels from an entire ingested chapter (50-100 panels)
to match a 45-60s Short video review script (Hook -> Body -> Call to Action).
Assigns frame-accurate timing and cinematic camera motions.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Sequence

from pydantic import BaseModel, Field

try:
    from src.api.timeline_schema import BackgroundConfig, MotionConfig, VisualClip
    from src.services.chapter_service import ChapterMetadata, PanelMetadata
    from src.services.script_generator import GeneratedScriptResponse, ScriptSegment
except ModuleNotFoundError:
    from backend.src.api.timeline_schema import BackgroundConfig, MotionConfig, VisualClip
    from backend.src.services.chapter_service import ChapterMetadata, PanelMetadata
    from backend.src.services.script_generator import GeneratedScriptResponse, ScriptSegment

logger = logging.getLogger(__name__)

# Standard Motion Presets
MOTION_PRESETS: dict[str, MotionConfig] = {
    "punch_zoom": MotionConfig(zoom_start=1.05, zoom_end=1.25, pan_start=(0, 0), pan_end=(0, 0), easing="smoothstep"),
    "zoom_in": MotionConfig(zoom_start=1.00, zoom_end=1.15, pan_start=(0, 0), pan_end=(0, 0), easing="smoothstep"),
    "pan_down": MotionConfig(zoom_start=1.05, zoom_end=1.05, pan_start=(0, -60), pan_end=(0, 60), easing="smoothstep"),
    "zoom_out": MotionConfig(zoom_start=1.20, zoom_end=1.00, pan_start=(0, 0), pan_end=(0, 0), easing="smoothstep"),
    "static_focus": MotionConfig(zoom_start=1.05, zoom_end=1.05, pan_start=(0, 0), pan_end=(0, 0), easing="linear"),
    "blur_glow": MotionConfig(zoom_start=1.02, zoom_end=1.10, pan_start=(0, 0), pan_end=(0, 0), easing="smoothstep"),
}


class SelectedPanel(BaseModel):
    """An optimal keyframe panel selected and scheduled for video composition."""
    clip_id: str = Field(..., description="Unique visual clip identifier")
    segment_id: str = Field(..., description="Mapped narration script segment ID")
    section_type: str = Field(..., description="'hook', 'body', or 'call_to_action'")
    panel_id: str = Field(..., description="Source comic panel ID")
    page_order: int = Field(..., description="Original manga page number")
    image_path: str = Field(..., description="File path to source page image")
    bbox: list[int] = Field(..., description="[x1, y1, x2, y2] bounding box in original image pixels")
    start_time: float = Field(..., ge=0.0, description="Visual shot start timestamp in seconds")
    end_time: float = Field(..., ge=0.0, description="Visual shot end timestamp in seconds")
    duration: float = Field(..., ge=0.0, description="Shot duration in seconds")
    camera_motion: str = Field(..., description="Name of camera motion effect")
    motion_config: MotionConfig = Field(..., description="Parameters for camera pan/zoom")
    narration_text: str = Field(default="", description="Accompanying narrator speech text")


def select_keyframe_panels(
    chapter_data: ChapterMetadata,
    script: GeneratedScriptResponse,
    target_count: int = 8,
) -> list[SelectedPanel]:
    """Selects 6-10 keyframe panels from chapter data aligned to script segments.

    Args:
        chapter_data: Ingested chapter metadata containing all pages and extracted panels.
        script: Narrator script with segments (hook, body, cta).
        target_count: Desired total keyframe panel count (clamped between 6 and 10).

    Returns:
        Ordered list of SelectedPanel instances with contiguous timestamps matching script duration.
    """
    # Clamp target count between 6 and 10
    target_k = max(6, min(10, target_count))

    # 1. Flatten all panels with their page order & image path
    all_panels: list[PanelMetadata] = []
    for page in chapter_data.pages:
        for p in page.panels:
            all_panels.append(p)

    if not all_panels:
        # Fallback dummy panel if none exist
        all_panels.append(
            PanelMetadata(
                panel_id="PN_FALLBACK",
                page_order=1,
                image_path="page_01.jpg",
                bbox=[0, 0, 900, 1280],
                bbox_normalized=[0.0, 0.0, 1.0, 1.0],
                area=900 * 1280,
                area_fraction=1.0,
                state="DETECTED",
                visual_score=1.0,
            )
        )

    # 2. Plan shot distribution across script segments
    segments = script.segments
    if not segments:
        return []

    # Calculate how many shots each segment receives to reach target_k
    # Standard: Hook gets 1, CTA gets 1, Body segments get remainder distributed by duration
    num_segments = len(segments)
    shots_per_segment: list[int] = [1] * num_segments
    remaining_shots = target_k - num_segments

    if remaining_shots > 0:
        # Identify body segments to receive extra shots
        body_indices = [i for i, s in enumerate(segments) if s.section_type == "body"]
        if not body_indices:
            body_indices = list(range(num_segments))

        # Sort body indices by segment duration descending
        sorted_body = sorted(body_indices, key=lambda idx: segments[idx].estimated_duration, reverse=True)
        for i in range(remaining_shots):
            target_idx = sorted_body[i % len(sorted_body)]
            shots_per_segment[target_idx] += 1

    # 3. Select panels according to story progression
    total_shots = sum(shots_per_segment)
    selected_panels_result: list[SelectedPanel] = []

    current_timeline_sec = 0.0
    shot_index = 0

    num_panels = len(all_panels)

    for seg_idx, segment in enumerate(segments):
        n_shots = shots_per_segment[seg_idx]
        shot_duration = round(segment.estimated_duration / n_shots, 3)

        for s_sub in range(n_shots):
            shot_index += 1
            # Determine target chapter progress window [prog_start, prog_end]
            global_shot_progress = (shot_index - 0.5) / total_shots

            # Segment-specific motion & panel selection preferences
            if segment.section_type == "hook":
                preferred_motion = "punch_zoom"
                # Search in first 25% of panels
                max_p_idx = max(1, int(num_panels * 0.25))
                candidate_pool = all_panels[:max_p_idx]
            elif segment.section_type == "call_to_action":
                preferred_motion = "zoom_out"
                # Search in last 25% of panels
                min_p_idx = min(num_panels - 1, int(num_panels * 0.75))
                candidate_pool = all_panels[min_p_idx:]
            else:
                # Body: alternate zoom_in and pan_down
                preferred_motion = "pan_down" if (s_sub % 2 == 1) else "zoom_in"
                # Center around global progress
                center_idx = int(global_shot_progress * (num_panels - 1))
                radius = max(2, int(num_panels * 0.20))
                start_win = max(0, center_idx - radius)
                end_win = min(num_panels, center_idx + radius + 1)
                candidate_pool = all_panels[start_win:end_win]

            if not candidate_pool:
                candidate_pool = all_panels

            # Pick candidate with highest visual score
            chosen_panel = max(candidate_pool, key=lambda p: p.visual_score)

            start_t = round(current_timeline_sec, 3)
            # Ensure last shot aligns exactly with segment end to avoid floating drift
            if s_sub == n_shots - 1:
                seg_end_t = round(
                    sum(segments[k].estimated_duration for k in range(seg_idx + 1)), 3
                )
                dur = round(max(0.5, seg_end_t - start_t), 3)
                end_t = seg_end_t
            else:
                dur = shot_duration
                end_t = round(start_t + dur, 3)

            current_timeline_sec = end_t

            motion_cfg = MOTION_PRESETS.get(preferred_motion, MOTION_PRESETS["zoom_in"])

            selected = SelectedPanel(
                clip_id=f"CLIP_{uuid.uuid4().hex[:6]}_{shot_index:02d}",
                segment_id=segment.id,
                section_type=segment.section_type,
                panel_id=chosen_panel.panel_id,
                page_order=chosen_panel.page_order,
                image_path=chosen_panel.image_path,
                bbox=chosen_panel.bbox,
                start_time=start_t,
                end_time=end_t,
                duration=dur,
                camera_motion=preferred_motion,
                motion_config=motion_cfg,
                narration_text=segment.text if s_sub == 0 else "",
            )
            selected_panels_result.append(selected)

    return selected_panels_result


def convert_to_visual_clips(selected_panels: Sequence[SelectedPanel]) -> list[VisualClip]:
    """Converts a sequence of SelectedPanel instances into canonical VisualClip models."""
    visual_clips: list[VisualClip] = []
    for sp in selected_panels:
        clip = VisualClip(
            clip_id=sp.clip_id,
            panel_id=sp.panel_id,
            bbox=[float(x) for x in sp.bbox],
            start_time=sp.start_time,
            end_time=sp.end_time,
            duration=sp.duration,
            shot_type=f"{sp.section_type.upper()}_SHOT",
            image_path=sp.image_path,
            motion=sp.motion_config,
            background=BackgroundConfig(blur_radius=51, darkness=0.35),
        )
        visual_clips.append(clip)
    return visual_clips

