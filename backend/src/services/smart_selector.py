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
    from src.api.timeline_schema import AudioClip, BackgroundConfig, MotionConfig, VisualClip
    from src.services.chapter_service import ChapterMetadata, PanelMetadata
    from src.services.script_generator import GeneratedScriptResponse, ScriptSegment
except ModuleNotFoundError:
    from backend.src.api.timeline_schema import AudioClip, BackgroundConfig, MotionConfig, VisualClip
    from backend.src.services.chapter_service import ChapterMetadata, PanelMetadata
    from backend.src.services.script_generator import GeneratedScriptResponse, ScriptSegment

logger = logging.getLogger(__name__)

# Standard Motion Presets
MOTION_PRESETS: dict[str, MotionConfig] = {
    "punch_zoom": MotionConfig(zoom_start=1.05, zoom_end=1.25, pan_start=(0, 0), pan_end=(0, 0), easing="smoothstep"),
    "zoom_in": MotionConfig(zoom_start=1.00, zoom_end=1.20, pan_start=(0, 0), pan_end=(0, 0), easing="smoothstep"),
    "pan_down": MotionConfig(zoom_start=1.05, zoom_end=1.05, pan_start=(0, -100), pan_end=(0, 100), easing="smoothstep"),
    "zoom_out": MotionConfig(zoom_start=1.22, zoom_end=1.04, pan_start=(0, 0), pan_end=(0, 0), easing="smoothstep"),
    "static_focus": MotionConfig(zoom_start=1.05, zoom_end=1.05, pan_start=(0, 0), pan_end=(0, 0), easing="linear"),
    "blur_glow": MotionConfig(zoom_start=1.02, zoom_end=1.12, pan_start=(0, 0), pan_end=(0, 0), easing="smoothstep"),
}


class SelectedPanel(BaseModel):
    """An optimal keyframe panel selected and scheduled for video composition."""
    clip_id: str = Field(..., description="Unique visual clip identifier")
    segment_id: str = Field(..., description="Mapped narration script segment ID")
    section_type: str = Field(..., description="'hook', 'body', or 'call_to_action'")
    panel_id: str = Field(..., description="Source comic panel ID")
    page_order: int = Field(..., description="Original manga page number")
    image_path: str = Field(..., description="File path to source page image")
    page_image_path: str = Field(default="", description="Alias/guaranteed path to source page image")
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
    audio_clips: Sequence[AudioClip] | None = None,
) -> list[SelectedPanel]:
    """Selects keyframe panels from chapter data aligned to script segments or audio clips.

    Args:
        chapter_data: Ingested chapter metadata containing all pages and extracted panels.
        script: Narrator script with segments (hook, body, cta).
        target_count: Desired total keyframe panel count (clamped between 6 and 10) when audio_clips is None.
        audio_clips: Optional sequence of synthesized AudioClip items for frame-accurate 1:1 timeline sync.

    Returns:
        Ordered list of SelectedPanel instances with contiguous timestamps matching script/narration duration.
    """
    # 1. Flatten all panels with their page order & image path
    all_panels: list[PanelMetadata] = []
    for page in chapter_data.pages:
        for p in page.panels:
            p_img = p.image_path or page.image_path
            p.image_path = p_img
            p.page_image_path = p_img
            p.page_order = page.page_order
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

    num_pages = len(chapter_data.pages)
    sorted_pages = sorted(chapter_data.pages, key=lambda p: p.page_order) if num_pages > 0 else []

    def _normalize_image_path(raw_path: str | None) -> str:
        if not raw_path:
            return "page_01.jpg"
        p_str = str(raw_path).replace("\\", "/")
        if "uploads/" in p_str:
            return p_str[p_str.index("uploads/"):]
        if p_str.startswith("backend/"):
            return p_str[len("backend/"):]
        return p_str

    # ---------------------------------------------------------
    # Branch A: Direct Audio-Visual Synchronization
    # ---------------------------------------------------------
    if audio_clips and len(audio_clips) > 0:
        n_clips = len(audio_clips)
        target_k = max(n_clips, min(10, target_count))
        shots_per_clip: list[int] = [1] * n_clips
        remaining_shots = target_k - n_clips

        if remaining_shots > 0:
            body_indices = []
            for i, ac in enumerate(audio_clips):
                seg = next((s for s in script.segments if s.id == ac.dialogue_id), None)
                if seg and seg.section_type == "body":
                    body_indices.append(i)
            if not body_indices:
                body_indices = list(range(n_clips))

            sorted_body = sorted(body_indices, key=lambda idx: audio_clips[idx].duration, reverse=True)
            for i in range(remaining_shots):
                target_idx = sorted_body[i % len(sorted_body)]
                shots_per_clip[target_idx] += 1

        total_shots = sum(shots_per_clip)
        selected_panels_result: list[SelectedPanel] = []
        used_panel_ids: set[str] = set()
        shot_index = 0

        for clip_idx, audio_clip in enumerate(audio_clips):
            n_sub_shots = shots_per_clip[clip_idx]
            clip_start_t = round(audio_clip.start_time, 3)
            if clip_idx < n_clips - 1:
                clip_end_t = round(audio_clips[clip_idx + 1].start_time, 3)
            else:
                clip_end_t = round(audio_clip.end_time, 3)
            clip_full_dur = max(0.5, clip_end_t - clip_start_t)

            # Match script segment
            matched_segment = next((s for s in script.segments if s.id == audio_clip.dialogue_id), None)
            if matched_segment is None and script.segments:
                matched_segment = script.segments[min(clip_idx, len(script.segments) - 1)]

            section_type = (
                matched_segment.section_type
                if matched_segment
                else ("hook" if clip_idx == 0 else ("call_to_action" if clip_idx == n_clips - 1 else "body"))
            )

            for s_sub in range(n_sub_shots):
                # Target page index driven by target_page_hint if provided, else spread evenly across chapter pages
                if matched_segment and getattr(matched_segment, "target_page_hint", None):
                    target_page_idx = max(0, min(num_pages - 1, matched_segment.target_page_hint - 1))
                elif total_shots <= 1 or num_pages <= 1:
                    target_page_idx = 0
                elif shot_index == 0:
                    target_page_idx = 0
                elif shot_index == total_shots - 1:
                    target_page_idx = num_pages - 1
                else:
                    target_page_idx = int(round((shot_index / (total_shots - 1)) * (num_pages - 1)))
                    target_page_idx = max(0, min(num_pages - 1, target_page_idx))

                # Proximity-based candidate page search: [target, target+1, target-1, ...]
                candidate_pool: list[PanelMetadata] = []
                chosen_page_idx = target_page_idx
                if sorted_pages:
                    page_offsets = sorted(
                        range(num_pages),
                        key=lambda idx: abs(idx - target_page_idx),
                    )
                    for p_idx in page_offsets:
                        pg = sorted_pages[p_idx]
                        unused_page_panels = [
                            p for p in pg.panels if p.panel_id not in used_panel_ids
                        ]
                        if unused_page_panels:
                            candidate_pool = unused_page_panels
                            chosen_page_idx = p_idx
                            break

                # Fallback if all panels on candidate pages have been used
                if not candidate_pool:
                    fresh_all = [p for p in all_panels if p.panel_id not in used_panel_ids]
                    candidate_pool = fresh_all if fresh_all else all_panels

                chosen_panel = max(candidate_pool, key=lambda p: p.visual_score)
                used_panel_ids.add(chosen_panel.panel_id)

                shot_index += 1

                # Motion assignment: Hook gets punch_zoom, CTA gets zoom_out, Body alternates pan_down / zoom_in
                if section_type == "hook":
                    preferred_motion = "punch_zoom"
                elif section_type == "call_to_action":
                    preferred_motion = "zoom_out"
                else:
                    preferred_motion = "pan_down" if (shot_index % 2 == 1) else "zoom_in"

                motion_cfg = MOTION_PRESETS.get(preferred_motion, MOTION_PRESETS["zoom_in"])

                # Exact subdivision within this audio clip's time boundary
                sub_dur = clip_full_dur / n_sub_shots
                start_t = round(clip_start_t + s_sub * sub_dur, 3)
                if s_sub == n_sub_shots - 1:
                    end_t = round(clip_end_t, 3)
                else:
                    end_t = round(clip_start_t + (s_sub + 1) * sub_dur, 3)
                dur = round(max(0.5, end_t - start_t), 3)

                raw_img = (
                    chosen_panel.image_path
                    or chosen_panel.page_image_path
                    or (sorted_pages[chosen_page_idx].image_path if sorted_pages else "page_01.jpg")
                )
                actual_img_path = _normalize_image_path(raw_img)

                selected = SelectedPanel(
                    clip_id=f"CLIP_{uuid.uuid4().hex[:6]}_{shot_index:02d}",
                    segment_id=matched_segment.id if matched_segment else f"seg_{shot_index:02d}",
                    section_type=section_type,
                    panel_id=chosen_panel.panel_id,
                    page_order=chosen_panel.page_order,
                    image_path=actual_img_path,
                    page_image_path=actual_img_path,
                    bbox=chosen_panel.bbox,
                    start_time=start_t,
                    end_time=end_t,
                    duration=dur,
                    camera_motion=preferred_motion,
                    motion_config=motion_cfg,
                    narration_text=audio_clip.text if s_sub == 0 else "",
                )
                selected_panels_result.append(selected)

        return selected_panels_result

    # ---------------------------------------------------------
    # Branch B: Duration-based estimation (when audio_clips is None)
    # ---------------------------------------------------------
    target_k = max(6, min(10, target_count))
    segments = script.segments
    if not segments:
        return []

    num_segments = len(segments)
    shots_per_segment: list[int] = [1] * num_segments
    remaining_shots = target_k - num_segments

    if remaining_shots > 0:
        body_indices = [i for i, s in enumerate(segments) if s.section_type == "body"]
        if not body_indices:
            body_indices = list(range(num_segments))

        sorted_body = sorted(body_indices, key=lambda idx: segments[idx].estimated_duration, reverse=True)
        for i in range(remaining_shots):
            target_idx = sorted_body[i % len(sorted_body)]
            shots_per_segment[target_idx] += 1

    total_shots = sum(shots_per_segment)
    selected_panels_result = []

    current_timeline_sec = 0.0
    shot_index = 0
    used_panel_ids = set()

    for seg_idx, segment in enumerate(segments):
        n_shots = shots_per_segment[seg_idx]
        shot_duration = round(segment.estimated_duration / n_shots, 3)

        for s_sub in range(n_shots):
            if getattr(segment, "target_page_hint", None):
                target_page_idx = max(0, min(num_pages - 1, segment.target_page_hint - 1))
            elif total_shots <= 1 or num_pages <= 1:
                target_page_idx = 0
            elif shot_index == 0:
                target_page_idx = 0
            elif shot_index == total_shots - 1:
                target_page_idx = num_pages - 1
            else:
                target_page_idx = int(round((shot_index / (total_shots - 1)) * (num_pages - 1)))
                target_page_idx = max(0, min(num_pages - 1, target_page_idx))

            candidate_pool = []
            chosen_page_idx = target_page_idx
            if sorted_pages:
                page_offsets = sorted(
                    range(num_pages),
                    key=lambda idx: abs(idx - target_page_idx),
                )
                for p_idx in page_offsets:
                    pg = sorted_pages[p_idx]
                    unused_page_panels = [
                        p for p in pg.panels if p.panel_id not in used_panel_ids
                    ]
                    if unused_page_panels:
                        candidate_pool = unused_page_panels
                        chosen_page_idx = p_idx
                        break

            if not candidate_pool:
                fresh_all = [p for p in all_panels if p.panel_id not in used_panel_ids]
                candidate_pool = fresh_all if fresh_all else all_panels

            chosen_panel = max(candidate_pool, key=lambda p: p.visual_score)
            used_panel_ids.add(chosen_panel.panel_id)

            shot_index += 1

            if segment.section_type == "hook":
                preferred_motion = "punch_zoom"
            elif segment.section_type == "call_to_action":
                preferred_motion = "zoom_out"
            else:
                preferred_motion = "pan_down" if (s_sub % 2 == 1) else "zoom_in"

            start_t = round(current_timeline_sec, 3)
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

            raw_img = (
                chosen_panel.image_path
                or chosen_panel.page_image_path
                or (sorted_pages[chosen_page_idx].image_path if sorted_pages else "page_01.jpg")
            )
            actual_img_path = _normalize_image_path(raw_img)

            selected = SelectedPanel(
                clip_id=f"CLIP_{uuid.uuid4().hex[:6]}_{shot_index:02d}",
                segment_id=segment.id,
                section_type=segment.section_type,
                panel_id=chosen_panel.panel_id,
                page_order=chosen_panel.page_order,
                image_path=actual_img_path,
                page_image_path=actual_img_path,
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
        actual_img_path = getattr(sp, "image_path", None) or getattr(sp, "page_image_path", None)
        if actual_img_path:
            p_str = str(actual_img_path).replace("\\", "/")
            if "uploads/" in p_str:
                actual_img_path = p_str[p_str.index("uploads/"):]
            elif p_str.startswith("backend/"):
                actual_img_path = p_str[len("backend/"):]
            else:
                actual_img_path = p_str

        clip = VisualClip(
            clip_id=sp.clip_id,
            panel_id=sp.panel_id,
            bbox=[float(x) for x in sp.bbox],
            start_time=sp.start_time,
            end_time=sp.end_time,
            duration=sp.duration,
            shot_type=f"{sp.section_type.upper()}_SHOT",
            image_path=actual_img_path,
            motion=sp.motion_config,
            background=BackgroundConfig(blur_radius=51, darkness=0.35),
        )
        visual_clips.append(clip)
    return visual_clips

