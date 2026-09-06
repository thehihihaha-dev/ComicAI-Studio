/**
 * TypeScript definitions for ComicAI Studio Web Editor (CapCut style)
 * Matches backend TimelineContract Pydantic schemas.
 */

export interface MotionConfig {
  zoom_start: number;
  zoom_end: number;
  pan_start: [number, number];
  pan_end: [number, number];
  easing: string;
}

export interface BackgroundConfig {
  blur_radius: number;
  darkness: number;
  border_width: number;
  border_color: [number, number, number];
}

export interface VisualClip {
  clip_id: string;
  panel_id: string;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  start_time: number;
  end_time: number;
  duration: number;
  shot_type: string;
  image_path?: string;
  motion: MotionConfig;
  background: BackgroundConfig;
}

export interface AudioClip {
  clip_id: string;
  dialogue_id: string;
  speaker_label: string;
  voice_id: string;
  text: string;
  file_path: string;
  start_time: number;
  end_time: number;
  duration: number;
}

export interface TimelineContract {
  version: string;
  project_id: string;
  page_id: number;
  source_image_path: string;
  image_dimensions: [number, number];
  canvas_size: [number, number];
  fps: number;
  total_duration: number;
  visual_clips: VisualClip[];
  audio_clips: AudioClip[];
  metadata: Record<string, unknown>;
}

export interface RenderRequest {
  timeline: TimelineContract;
  output_filename?: string;
}

export interface RenderResponse {
  status: string;
  video_path: string;
  video_url: string;
  resolution: [number, number];
  fps: number;
  total_frames: number;
  duration_sec: number;
  audio_drift_sec: number;
  file_size_bytes: number;
  file_sha256: string;
}

export interface ScriptSegment {
  id: string;
  section_type: "hook" | "body" | "call_to_action" | string;
  text: string;
  estimated_duration: number;
  suggested_effect: string;
}

export interface GeneratedScriptResponse {
  project_id: string;
  story_style: "dramatic" | "humorous" | "romantic" | string;
  total_duration: number;
  segments: ScriptSegment[];
}
