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
  page_image_path?: string;
  page_order?: number;
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
  audio_url?: string;
  start_time: number;
  end_time: number;
  duration: number;
  source?: "ai_review_script" | "manga_dialogue" | string;
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

export interface SceneSegment {
  scene_index: number;
  stage:
    | "hook"
    | "buildup"
    | "conflict"
    | "twist"
    | "cliffhanger"
    | "cta"
    | string;
  visual_direction: string;
  voiceover: string;
  target_page_hint: number;
}

export interface ScriptSegment {
  id: string;
  section_type: "hook" | "body" | "call_to_action" | string;
  text: string;
  estimated_duration: number;
  suggested_effect: string;
  audio_url?: string;
  scene_index?: number;
  stage?: string;
  visual_direction?: string;
  voiceover?: string;
  target_page_hint?: number;
}

export interface GeneratedScriptResponse {
  project_id: string;
  story_style: "dramatic" | "humorous" | "romantic" | string;
  total_duration: number;
  preview_audio_url?: string;
  segments: ScriptSegment[];
  scenes?: SceneSegment[];
}

export interface PanelItem {
  id: string;
  page_order: number;
  image: string;
  script: ScriptSegment[];
  mangaDialogue?: string[];
  reviewScript?: ScriptSegment[];
  ttsAudio?: string;
  style: "dramatic" | "humorous" | "romantic" | string;
  duration: number;
  timelineStart: number;
  timelineEnd: number;
  status: "ready" | "processing" | "completed" | "error";
  error: string | null;
}

export interface AudioEngineConfig {
  bgmVolumeDucked: number;
  bgmVolumeNormal: number;
  masterVoiceVolume: number;
  masterBgmVolume: number;
}

export const DEFAULT_AUDIO_CONFIG: AudioEngineConfig = {
  bgmVolumeDucked: 0.2,
  bgmVolumeNormal: 0.6,
  masterVoiceVolume: 1.0,
  masterBgmVolume: 0.8,
};

export function resolveImageUrl(rawPath?: string | null): string {
  if (!rawPath) return "/page_01.jpg";
  if (rawPath.startsWith("http://") || rawPath.startsWith("https://")) {
    return rawPath;
  }
  if (rawPath === "/page_01.jpg" || rawPath === "page_01.jpg") {
    return "/page_01.jpg";
  }
  let cleanPath = rawPath.replace(/^\/+/, "");
  cleanPath = cleanPath.replace(/^backend\//, "");
  if (cleanPath.includes("uploads/")) {
    cleanPath = cleanPath.substring(cleanPath.indexOf("uploads/"));
  } else if (cleanPath.includes("artifacts/")) {
    cleanPath = cleanPath.substring(cleanPath.indexOf("artifacts/"));
  } else if (cleanPath.includes("static/")) {
    cleanPath = cleanPath.substring(cleanPath.indexOf("static/"));
  }
  return `http://127.0.0.1:8000/${cleanPath}`;
}

export function resolveAudioUrl(rawPath?: string | null): string {
  if (!rawPath) return "";
  if (rawPath.startsWith("http://") || rawPath.startsWith("https://")) {
    return rawPath;
  }
  if (
    rawPath === "/default_bgm.mp3" ||
    rawPath === "default_bgm.mp3" ||
    rawPath.endsWith("default_bgm.mp3")
  ) {
    return "/default_bgm.mp3";
  }
  if (
    rawPath === "/preview_full.mp3" ||
    rawPath === "preview_full.mp3" ||
    rawPath === "/page_01_full.mp3" ||
    rawPath === "page_01_full.mp3" ||
    (rawPath.endsWith("preview_full.mp3") && !rawPath.includes("uploads"))
  ) {
    return rawPath.startsWith("/") ? rawPath : `/${rawPath}`;
  }
  let cleanPath = rawPath.replace(/^\/+/, "");
  cleanPath = cleanPath.replace(/^backend\//, "");
  if (cleanPath.includes("uploads/")) {
    cleanPath = cleanPath.substring(cleanPath.indexOf("uploads/"));
  } else if (cleanPath.includes("artifacts/")) {
    cleanPath = cleanPath.substring(cleanPath.indexOf("artifacts/"));
  } else if (cleanPath.includes("static/")) {
    cleanPath = cleanPath.substring(cleanPath.indexOf("static/"));
  }
  return `http://127.0.0.1:8000/${cleanPath}`;
}
