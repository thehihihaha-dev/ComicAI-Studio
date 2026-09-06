"use client";

import React, { useState } from "react";
import {
  GeneratedScriptResponse,
  ScriptSegment,
  TimelineContract,
  VisualClip,
} from "../types";

interface InspectorProps {
  timeline: TimelineContract;
  selectedClipId: string | null;
  currentTime?: number;
  projectId?: string;
  onUpdateTimeline: (updatedTimeline: TimelineContract) => void;
  onSeek?: (time: number) => void;
  onSelectClip?: (clipId: string) => void;
  onAutoGenerateShort?: (
    style: "dramatic" | "humorous" | "romantic",
  ) => Promise<void>;
  isGeneratingShort?: boolean;
}

const INITIAL_SCRIPT_SEGMENTS: ScriptSegment[] = [
  {
    id: "SEG_01",
    section_type: "hook",
    text: "Cứ ngỡ là hôn lễ trong mơ, ai ngờ lại là cái bẫy trí mạng!",
    estimated_duration: 3.0,
    suggested_effect: "punch_zoom",
  },
  {
    id: "SEG_02",
    section_type: "body",
    text: "Ngay tại thánh đường trang nghiêm, sự thật kinh hoàng đã chính thức bị vạch trần.",
    estimated_duration: 4.2,
    suggested_effect: "zoom_in",
  },
  {
    id: "SEG_03",
    section_type: "body",
    text: "Ánh mắt lạnh lùng đối diện sự tuyệt vọng cùng cực, không ai có thể quay đầu lại được nữa.",
    estimated_duration: 4.0,
    suggested_effect: "pan_down",
  },
  {
    id: "SEG_04",
    section_type: "call_to_action",
    text: "Bấm follow ngay để không bỏ lỡ diễn biến nghẹt thở ở chap tiếp theo!",
    estimated_duration: 3.5,
    suggested_effect: "zoom_out",
  },
];

interface EffectPreset {
  id: string;
  icon: string;
  title: string;
  desc: string;
  apply: (clip: VisualClip) => void;
  isActive: (clip: VisualClip) => boolean;
}

const EFFECT_PRESETS: EffectPreset[] = [
  {
    id: "ZOOM_IN",
    icon: "🔍",
    title: "Zoom-in Cảm xúc",
    desc: "Phóng nhẹ 1.0x → 1.15x vào tâm điểm",
    apply: (c) => {
      c.shot_type = "ZOOM_IN";
      c.motion.zoom_start = 1.0;
      c.motion.zoom_end = 1.15;
      c.motion.pan_start = [0, 0];
      c.motion.pan_end = [0, 0];
      c.background.blur_radius = 35;
      c.background.darkness = 0.35;
    },
    isActive: (c) =>
      c.shot_type === "ZOOM_IN" ||
      (c.motion.zoom_start === 1.0 &&
        c.motion.zoom_end > 1.05 &&
        c.motion.zoom_end <= 1.18 &&
        c.motion.pan_end[1] === 0 &&
        c.background.blur_radius < 65),
  },
  {
    id: "PUNCH_ZOOM",
    icon: "💥",
    title: "Giật Khung Hình",
    desc: "Cận cảnh kịch tính biểu cảm 1.05x → 1.25x",
    apply: (c) => {
      c.shot_type = "PUNCH_ZOOM";
      c.motion.zoom_start = 1.05;
      c.motion.zoom_end = 1.25;
      c.motion.pan_start = [0, 0];
      c.motion.pan_end = [0, -20];
      c.background.blur_radius = 45;
      c.background.darkness = 0.45;
    },
    isActive: (c) =>
      c.shot_type === "PUNCH_ZOOM" ||
      (c.motion.zoom_end >= 1.2 && c.motion.pan_end[1] < -10),
  },
  {
    id: "VERTICAL_TILT",
    icon: "📜",
    title: "Cuộn Trang Đọc",
    desc: "Lia mượt từ trên xuống dọc trang",
    apply: (c) => {
      c.shot_type = "PAN";
      c.motion.zoom_start = 1.03;
      c.motion.zoom_end = 1.03;
      c.motion.pan_start = [0, 25];
      c.motion.pan_end = [0, -25];
      c.background.blur_radius = 30;
      c.background.darkness = 0.3;
    },
    isActive: (c) =>
      c.shot_type === "PAN" ||
      c.motion.pan_start[1] !== 0 ||
      c.motion.pan_end[1] !== 0,
  },
  {
    id: "ZOOM_OUT",
    icon: "🌐",
    title: "Mở Rộng Toàn Cảnh",
    desc: "Thu từ chi tiết ra bao quát 1.20x → 1.0x",
    apply: (c) => {
      c.shot_type = "ZOOM_OUT";
      c.motion.zoom_start = 1.2;
      c.motion.zoom_end = 1.0;
      c.motion.pan_start = [0, -10];
      c.motion.pan_end = [0, 0];
      c.background.blur_radius = 30;
      c.background.darkness = 0.3;
    },
    isActive: (c) =>
      c.shot_type === "ZOOM_OUT" || c.motion.zoom_start > c.motion.zoom_end,
  },
  {
    id: "BLUR_GLOW",
    icon: "✨",
    title: "Mờ Ảo Tình Cảm",
    desc: "Zoom nhẹ + tăng mờ viền phông nền",
    apply: (c) => {
      c.shot_type = "BLUR_GLOW";
      c.motion.zoom_start = 1.02;
      c.motion.zoom_end = 1.08;
      c.motion.pan_start = [0, 0];
      c.motion.pan_end = [0, 0];
      c.background.blur_radius = 75;
      c.background.darkness = 0.55;
    },
    isActive: (c) =>
      c.shot_type === "BLUR_GLOW" || c.background.blur_radius >= 65,
  },
  {
    id: "STATIC",
    icon: "🛑",
    title: "Khung Hình Tĩnh",
    desc: "Cố định góc nhìn, không chuyển động",
    apply: (c) => {
      c.shot_type = "STATIC";
      c.motion.zoom_start = 1.0;
      c.motion.zoom_end = 1.0;
      c.motion.pan_start = [0, 0];
      c.motion.pan_end = [0, 0];
      c.background.blur_radius = 30;
      c.background.darkness = 0.3;
    },
    isActive: (c) =>
      c.shot_type === "STATIC" ||
      (c.motion.zoom_start === 1.0 &&
        c.motion.zoom_end === 1.0 &&
        c.motion.pan_start[1] === 0 &&
        c.motion.pan_end[1] === 0 &&
        c.background.blur_radius < 60),
  },
];

export default function Inspector({
  timeline,
  selectedClipId,
  currentTime = 0,
  projectId,
  onUpdateTimeline,
  onSeek,
  onSelectClip,
  onAutoGenerateShort,
  isGeneratingShort = false,
}: InspectorProps) {
  const [activeTab, setActiveTab] = useState<
    "dialogue" | "ai_script" | "effects"
  >("dialogue");
  const [storyStyle, setStoryStyle] = useState<
    "dramatic" | "humorous" | "romantic"
  >("dramatic");
  const [segments, setSegments] = useState<ScriptSegment[]>(
    INITIAL_SCRIPT_SEGMENTS,
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");
  const [appliedNotice, setAppliedNotice] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Find selected visual clip or fallback to first clip
  const clipIndex = timeline.visual_clips.findIndex(
    (c) => c.clip_id === selectedClipId,
  );
  const activeClip: VisualClip | undefined =
    clipIndex >= 0
      ? timeline.visual_clips[clipIndex]
      : timeline.visual_clips[0];

  // Helper to update visual clip attributes with zero-lag shallow clone
  const updateActiveClip = (updater: (draft: VisualClip) => void) => {
    if (!activeClip) return;
    const targetIdx = clipIndex >= 0 ? clipIndex : 0;
    const target = timeline.visual_clips[targetIdx];
    const clipCopy: VisualClip = {
      ...target,
      bbox: [...target.bbox],
      motion: {
        ...target.motion,
        pan_start: [...target.motion.pan_start],
        pan_end: [...target.motion.pan_end],
      },
      background: {
        ...target.background,
        border_color: [...target.background.border_color],
      },
    };
    updater(clipCopy);
    const updatedClips = [...timeline.visual_clips];
    updatedClips[targetIdx] = clipCopy;

    onUpdateTimeline({
      ...timeline,
      visual_clips: updatedClips,
    });
  };

  // Helper to update specific audio clip subtitle
  const updateAudioText = (clipId: string, newText: string) => {
    const updatedAudios = timeline.audio_clips.map((a) =>
      a.clip_id === clipId ? { ...a, text: newText } : a,
    );
    onUpdateTimeline({
      ...timeline,
      audio_clips: updatedAudios,
    });
  };

  const handleGenerateScript = async () => {
    setIsGenerating(true);
    setGenerateError("");
    const targetPid = projectId || timeline.project_id || "default_project";

    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/projects/${targetPid}/generate-script`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            story_style: storyStyle,
            target_duration: 45,
          }),
        },
      );

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      const data: GeneratedScriptResponse = await res.json();
      if (data && Array.isArray(data.segments) && data.segments.length > 0) {
        setSegments(data.segments);
      }
    } catch (err) {
      console.warn(
        "API call failed, generating localized fallback script:",
        err,
      );
      // Fallback generator based on selected style
      const fallbackTexts: Record<string, ScriptSegment[]> = {
        dramatic: [
          {
            id: "SEG_D_01",
            section_type: "hook",
            text: "Cứ ngỡ là hôn lễ trong mơ, ai ngờ lại là cái bẫy trí mạng!",
            estimated_duration: 3.0,
            suggested_effect: "punch_zoom",
          },
          {
            id: "SEG_D_02",
            section_type: "body",
            text: "Ngay tại thánh đường trang nghiêm, sự thật kinh hoàng đã chính thức bị vạch trần.",
            estimated_duration: 4.2,
            suggested_effect: "zoom_in",
          },
          {
            id: "SEG_D_03",
            section_type: "body",
            text: "Ánh mắt lạnh lùng đối diện sự tuyệt vọng cùng cực, không ai có thể quay đầu lại được nữa.",
            estimated_duration: 4.0,
            suggested_effect: "pan_down",
          },
          {
            id: "SEG_D_04",
            section_type: "call_to_action",
            text: "Bấm follow ngay để không bỏ lỡ diễn biến nghẹt thở ở chap tiếp theo!",
            estimated_duration: 3.5,
            suggested_effect: "zoom_out",
          },
        ],
        humorous: [
          {
            id: "SEG_H_01",
            section_type: "hook",
            text: "Tưởng được lấy vợ hiền thục, ai dè rước ngay 'nóc nhà' chiến thần!",
            estimated_duration: 3.0,
            suggested_effect: "punch_zoom",
          },
          {
            id: "SEG_H_02",
            section_type: "body",
            text: "Thầy tu vừa đọc kinh xong thì cô dâu đã kịp lườm chú rể cháy cả mắt rồi.",
            estimated_duration: 3.8,
            suggested_effect: "zoom_in",
          },
          {
            id: "SEG_H_03",
            section_type: "body",
            text: "Đúng là hảo bằng hữu trong game nhưng ngoài đời thì ai là gà ai là thóc còn chưa biết đâu nhé.",
            estimated_duration: 4.5,
            suggested_effect: "pan_down",
          },
          {
            id: "SEG_H_04",
            section_type: "call_to_action",
            text: "Thả ngay một tim và follow kênh để hóng tiếp màn combat nảy lửa này nào!",
            estimated_duration: 3.5,
            suggested_effect: "zoom_out",
          },
        ],
        romantic: [
          {
            id: "SEG_R_01",
            section_type: "hook",
            text: "Khoảnh khắc hai ánh mắt chạm nhau, mọi định kiến dường như tan biến.",
            estimated_duration: 3.0,
            suggested_effect: "punch_zoom",
          },
          {
            id: "SEG_R_02",
            section_type: "body",
            text: "Trước thánh đường thiêng liêng, lời thề nguyện như khắc sâu vào từng nhịp đập con tim.",
            estimated_duration: 4.0,
            suggested_effect: "zoom_in",
          },
          {
            id: "SEG_R_03",
            section_type: "body",
            text: "Dù phía trước là giông bão, chỉ cần một cái nắm tay ấm áp cũng đủ để vượt qua tất cả.",
            estimated_duration: 4.2,
            suggested_effect: "zoom_in",
          },
          {
            id: "SEG_R_04",
            section_type: "call_to_action",
            text: "Đăng ký kênh để cùng theo dõi câu chuyện tình ngọt ngào này nhé!",
            estimated_duration: 3.2,
            suggested_effect: "zoom_out",
          },
        ],
      };
      setSegments(fallbackTexts[storyStyle] || fallbackTexts.dramatic);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApplyToTimeline = () => {
    let currStart = 0.0;
    const pauseSec = 0.3; // Natural pause between segments

    const newAudioClips = segments.map((seg, idx) => {
      const dur = Math.max(1.0, seg.estimated_duration);
      const startT = Number(currStart.toFixed(3));
      const endT = Number((currStart + dur).toFixed(3));
      currStart = endT + pauseSec;

      const typeUpper = seg.section_type.toUpperCase();
      const speakerTag = `NAMMINH [${typeUpper}]`;

      return {
        clip_id: `AUD_AI_${seg.id}_${idx + 1}`,
        dialogue_id: seg.id,
        speaker_label: speakerTag,
        voice_id: "vi-VN-NamMinhNeural",
        text: seg.text,
        file_path: `artifacts/audio/day19/${seg.id}.mp3`,
        start_time: startT,
        end_time: endT,
        duration: dur,
      };
    });

    const newTotalDuration = Math.max(
      Number(currStart.toFixed(2)),
      timeline.total_duration,
    );

    // Proportionally adjust visual clips if new audio duration extends beyond old duration
    let updatedVisuals = [...timeline.visual_clips];
    if (
      newTotalDuration > timeline.total_duration &&
      updatedVisuals.length > 0
    ) {
      const scale = newTotalDuration / timeline.total_duration;
      updatedVisuals = updatedVisuals.map((v) => ({
        ...v,
        start_time: Number((v.start_time * scale).toFixed(3)),
        end_time: Number((v.end_time * scale).toFixed(3)),
        duration: Number((v.duration * scale).toFixed(3)),
      }));
    }

    onUpdateTimeline({
      ...timeline,
      total_duration: newTotalDuration,
      audio_clips: newAudioClips,
      visual_clips: updatedVisuals,
    });

    setAppliedNotice(true);
    setTimeout(() => setAppliedNotice(false), 3000);
  };

  const handleCopyScript = () => {
    const fullText = segments
      .map(
        (s) =>
          `[${s.section_type.toUpperCase()} - ${s.suggested_effect}]\n${s.text}`,
      )
      .join("\n\n");
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(fullText).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }
  };

  return (
    <div className="w-full bg-[#101013] flex flex-col h-full overflow-hidden text-xs select-none">
      {/* 3 Flat Tab Navigation Header */}
      <nav
        className="flex h-12 items-center border-b border-white/[0.08] px-4 shrink-0 gap-1"
        aria-label="Bảng điều khiển Inspector"
      >
        <button
          type="button"
          onClick={() => setActiveTab("dialogue")}
          className={`relative text-xs transition px-2.5 pb-3.5 pt-3.5 ${
            activeTab === "dialogue"
              ? "text-white font-semibold after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-violet-500"
              : "text-white/40 hover:text-white/70"
          }`}
        >
          Thoại Manga
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("ai_script")}
          className={`relative text-xs transition px-2.5 pb-3.5 pt-3.5 ${
            activeTab === "ai_script"
              ? "text-white font-semibold after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-violet-500"
              : "text-white/40 hover:text-white/70"
          }`}
        >
          Kịch bản AI
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("effects")}
          className={`relative text-xs transition px-2.5 pb-3.5 pt-3.5 ${
            activeTab === "effects"
              ? "text-white font-semibold after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-violet-500"
              : "text-white/40 hover:text-white/70"
          }`}
        >
          Hiệu ứng
        </button>
      </nav>

      {/* Tab 1: Thoại Manga (Lời thoại bóc từ manga gốc & phân cảnh tương ứng) */}
      {activeTab === "dialogue" && (
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-width:thin]">
          <div className="flex items-center justify-between pb-1 border-b border-white/[0.08]">
            <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/40">
              Thoại bóc từ Manga gốc
            </p>
            <span className="text-[11px] text-white/40 font-mono">
              {timeline.audio_clips.length} câu
            </span>
          </div>

          {timeline.audio_clips.length === 0 ? (
            <div className="py-12 text-center text-sm text-white/30">
              Trang này chưa có lời thoại nào.
            </div>
          ) : (
            timeline.audio_clips.map((audio, idx) => {
              const speakerUpper = (audio.speaker_label || "").toUpperCase();
              const speakerColor = speakerUpper.includes("RIN")
                ? "text-pink-400 bg-pink-500/10 border-pink-500/30"
                : speakerUpper.includes("PRIEST") ||
                    speakerUpper.includes("LINH MỤC")
                  ? "text-amber-400 bg-amber-500/10 border-amber-500/30"
                  : speakerUpper.includes("KAZU")
                    ? "text-sky-400 bg-sky-500/10 border-sky-500/30"
                    : "text-violet-400 bg-violet-500/10 border-violet-500/30";

              const isCurrent =
                currentTime !== undefined &&
                currentTime >= audio.start_time &&
                currentTime < audio.end_time;

              // Find corresponding visual shot
              const matchingVisual = timeline.visual_clips.find(
                (v) =>
                  audio.start_time >= v.start_time &&
                  audio.start_time < v.end_time,
              );

              return (
                <article
                  key={audio.clip_id}
                  onClick={() => onSeek && onSeek(audio.start_time)}
                  className={`border-b pb-3.5 cursor-pointer group transition rounded-lg p-2.5 ${
                    isCurrent
                      ? "border-violet-500/50 bg-violet-500/[0.08] shadow-sm ring-1 ring-violet-500/30"
                      : "border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/15"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-mono font-semibold transition ${
                          isCurrent
                            ? "text-violet-400"
                            : "text-white/40 group-hover:text-violet-300"
                        }`}
                      >
                        #{String(idx + 1).padStart(2, "0")}
                      </span>
                      <span
                        className={`text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded border ${speakerColor}`}
                      >
                        {audio.speaker_label}
                      </span>
                      {matchingVisual && (
                        <span className="text-[9px] font-mono text-white/40 bg-white/5 px-1.5 py-0.5 rounded">
                          {matchingVisual.shot_type}
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] font-mono text-white/40">
                      {audio.start_time.toFixed(1)}s -{" "}
                      {audio.end_time.toFixed(1)}s
                    </span>
                  </div>

                  <textarea
                    rows={2}
                    value={audio.text}
                    onFocus={() => onSeek && onSeek(audio.start_time)}
                    onChange={(e) =>
                      updateAudioText(audio.clip_id, e.target.value)
                    }
                    placeholder="Nhập lời thoại..."
                    className="w-full bg-transparent border-0 border-b border-transparent focus:border-violet-500 text-xs text-white/90 focus:text-white p-0 outline-none resize-none leading-relaxed transition"
                  />
                </article>
              );
            })
          )}
        </div>
      )}

      {/* Tab 2: Kịch bản AI (Review & Tóm tắt cốt truyện kèm Hook) */}
      {activeTab === "ai_script" && (
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3.5 [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-width:thin]">
          {/* Header & Copy */}
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.08]">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/40">
                Kịch bản AI Review & Tóm Tắt
              </p>
              <p className="text-[10px] text-violet-300/80 mt-0.5 flex items-center gap-1.5">
                <span>🎙️</span>
                <span>Giọng đọc: vi-VN-NamMinhNeural (+12% rate)</span>
              </p>
            </div>
            <button
              type="button"
              onClick={handleCopyScript}
              className="px-2 py-1 rounded bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-[10px] font-medium text-violet-300 transition flex items-center gap-1 cursor-pointer"
            >
              <span>{copied ? "✓ Đã sao chép" : "📋 Sao chép"}</span>
            </button>
          </div>

          {/* Thanh điều khiển: Bộ chọn Phong cách & Nút Tạo Kịch Bản */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 flex flex-col gap-2.5">
            {/* One-Click Auto-Generate Short (Full Chapter) */}
            {onAutoGenerateShort && (
              <button
                type="button"
                onClick={() => onAutoGenerateShort(storyStyle)}
                disabled={isGeneratingShort}
                className="w-full py-2.5 px-3 rounded-lg bg-gradient-to-r from-amber-500 via-violet-600 to-fuchsia-600 hover:from-amber-400 hover:via-violet-500 hover:to-fuchsia-500 text-white font-bold text-xs transition shadow-md shadow-purple-950/40 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                title="Tự động bóc tách panel cả chapter, chọn 6-10 panel đắt giá và khớp kịch bản AI giọng NamMinh"
              >
                {isGeneratingShort ? (
                  <>
                    <div className="h-3.5 w-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                    <span>Đang xử lý Chapter...</span>
                  </>
                ) : (
                  <>
                    <span>⚡</span>
                    <span>Tạo Video Ngắn Tự Động (Full Chapter)</span>
                  </>
                )}
              </button>
            )}

            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-white/70 uppercase tracking-wider">
                Phong cách kể chuyện
              </span>
              <span className="text-[10px] text-white/40 font-mono">
                {segments.length} phân đoạn
              </span>
            </div>

            {/* Pill Selector for 3 Styles */}
            <div className="grid grid-cols-3 gap-1.5">
              <button
                type="button"
                onClick={() => setStoryStyle("dramatic")}
                className={`py-1.5 px-2 rounded-lg border text-center transition cursor-pointer text-[11px] font-medium ${
                  storyStyle === "dramatic"
                    ? "border-purple-500 bg-purple-500/20 text-white font-semibold ring-1 ring-purple-500/40"
                    : "border-white/[0.08] bg-white/[0.02] text-white/60 hover:text-white hover:border-white/20"
                }`}
              >
                ⚡ Kịch tính
              </button>
              <button
                type="button"
                onClick={() => setStoryStyle("humorous")}
                className={`py-1.5 px-2 rounded-lg border text-center transition cursor-pointer text-[11px] font-medium ${
                  storyStyle === "humorous"
                    ? "border-amber-500 bg-amber-500/20 text-white font-semibold ring-1 ring-amber-500/40"
                    : "border-white/[0.08] bg-white/[0.02] text-white/60 hover:text-white hover:border-white/20"
                }`}
              >
                🎭 Cà khịa
              </button>
              <button
                type="button"
                onClick={() => setStoryStyle("romantic")}
                className={`py-1.5 px-2 rounded-lg border text-center transition cursor-pointer text-[11px] font-medium ${
                  storyStyle === "romantic"
                    ? "border-pink-500 bg-pink-500/20 text-white font-semibold ring-1 ring-pink-500/40"
                    : "border-white/[0.08] bg-white/[0.02] text-white/60 hover:text-white hover:border-white/20"
                }`}
              >
                💖 Lãng mạn
              </button>
            </div>

            {/* Actions: Generate & Apply */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                type="button"
                onClick={handleGenerateScript}
                disabled={isGenerating}
                className="py-2 px-3 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-[11px] transition shadow-md shadow-purple-950/40 flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {isGenerating ? (
                  <>
                    <div className="h-3 w-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                    <span>Đang viết...</span>
                  </>
                ) : (
                  <>
                    <span>✨</span>
                    <span>AI Viết Kịch Bản</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleApplyToTimeline}
                className="py-2 px-3 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/40 border border-emerald-500/40 text-emerald-200 font-semibold text-[11px] transition flex items-center justify-center gap-1.5 cursor-pointer shadow-sm"
              >
                <span>🪄</span>
                <span>Áp Dụng Timeline</span>
              </button>
            </div>

            {appliedNotice && (
              <div className="text-[11px] text-emerald-300 bg-emerald-950/60 border border-emerald-500/30 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 animate-fadeIn">
                <span>✓</span>
                <span>
                  Đã cập nhật rãnh Thoại & Audio Ducking trên Timeline!
                </span>
              </div>
            )}
            {generateError && (
              <p className="text-[10px] text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2.5 py-1 rounded">
                {generateError}
              </p>
            )}
          </div>

          {/* Danh sách các phân đoạn ScriptSegment */}
          <div className="space-y-3">
            {segments.map((seg, idx) => {
              const isHook = seg.section_type === "hook";
              const isCTA =
                seg.section_type === "call_to_action" ||
                seg.section_type === "ending";
              const badgeStyle = isHook
                ? "text-purple-300 bg-purple-500/15 border-purple-500/30"
                : isCTA
                  ? "text-amber-300 bg-amber-500/15 border-amber-500/30"
                  : "text-sky-300 bg-sky-500/15 border-sky-500/30";

              const badgeLabel = isHook
                ? "🎣 HOOK (0-3s)"
                : isCTA
                  ? "⚡ CALL TO ACTION"
                  : `🎬 BODY 0${idx}`;

              return (
                <div
                  key={seg.id || idx}
                  className="rounded-lg border border-white/[0.08] bg-white/[0.02] p-3 transition hover:border-white/20 flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between gap-1.5 flex-wrap">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${badgeStyle}`}
                      >
                        {badgeLabel}
                      </span>
                      <span className="text-[10px] font-mono text-zinc-400 bg-zinc-800/60 border border-zinc-700/40 px-1.5 py-0.5 rounded">
                        {seg.suggested_effect}
                      </span>
                    </div>

                    <span className="text-[10px] font-mono text-white/50">
                      ⏱️ {seg.estimated_duration.toFixed(1)}s
                    </span>
                  </div>

                  <textarea
                    rows={3}
                    value={seg.text}
                    onChange={(e) => {
                      const next = [...segments];
                      next[idx] = { ...next[idx], text: e.target.value };
                      setSegments(next);
                    }}
                    placeholder="Lời bình của người dẫn chuyện..."
                    className="w-full bg-black/20 rounded-md p-2 border border-white/5 focus:border-violet-500 text-xs text-white/90 focus:text-white outline-none resize-none leading-relaxed transition"
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 3: Hiệu ứng (Gói Preset 1 chạm kiểu CapCut & Tùy chỉnh chi tiết) */}
      {activeTab === "effects" && (
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-width:thin]">
          <div className="flex items-center justify-between pb-1 border-b border-white/[0.08]">
            <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/40">
              Gói Hiệu Ứng Chuyển Động
            </p>
            {activeClip && (
              <span className="text-[10px] font-mono text-violet-300 bg-violet-500/10 border border-violet-500/30 px-2 py-0.5 rounded">
                {activeClip.shot_type}
              </span>
            )}
          </div>

          {/* Shot Selection Buttons */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-[11px] text-white/50">
              <span>Đang chọn phân cảnh:</span>
              <span className="font-mono text-white/80">
                Phân cảnh {clipIndex >= 0 ? clipIndex + 1 : 1} /{" "}
                {timeline.visual_clips.length}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-1.5">
              {timeline.visual_clips.map((clip, idx) => {
                const isSelected = activeClip?.clip_id === clip.clip_id;
                return (
                  <button
                    key={clip.clip_id}
                    type="button"
                    onClick={() => {
                      if (onSelectClip) onSelectClip(clip.clip_id);
                      if (onSeek) onSeek(clip.start_time);
                    }}
                    className={`py-1.5 px-2 rounded-lg border text-center transition cursor-pointer ${
                      isSelected
                        ? "border-violet-500 bg-violet-500/20 text-white font-semibold ring-1 ring-violet-500/40 shadow-sm"
                        : "border-white/[0.08] bg-white/[0.02] text-white/60 hover:text-white hover:border-white/20"
                    }`}
                  >
                    <div className="text-xs font-medium">Cảnh {idx + 1}</div>
                    <div className="text-[9px] font-mono opacity-60">
                      {clip.duration.toFixed(1)}s
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {activeClip && (
            <div className="flex flex-col gap-3 pt-2">
              <span className="text-xs font-medium text-white/80">
                Chọn gói hiệu ứng (1 chạm áp dụng ngay):
              </span>

              {/* 6 Presets Grid */}
              <div className="grid grid-cols-2 gap-2.5">
                {EFFECT_PRESETS.map((preset) => {
                  const active = preset.isActive(activeClip);
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => {
                        updateActiveClip((c) => {
                          preset.apply(c);
                        });
                      }}
                      className={`group p-3 rounded-xl border text-left transition flex flex-col justify-between cursor-pointer ${
                        active
                          ? "border-violet-500 bg-violet-500/15 text-white ring-2 ring-violet-500/40 shadow-md shadow-violet-950/40"
                          : "border-white/[0.08] bg-white/[0.02] text-white/70 hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className="text-lg">{preset.icon}</span>
                          {active && (
                            <span className="text-[9px] font-mono text-violet-300 bg-violet-500/30 px-1.5 py-0.5 rounded border border-violet-400/30">
                              Đang dùng
                            </span>
                          )}
                        </div>
                        <p className="text-xs font-semibold leading-snug">
                          {preset.title}
                        </p>
                      </div>
                      <p className="text-[10px] text-white/40 group-hover:text-white/60 leading-normal mt-1.5">
                        {preset.desc}
                      </p>
                    </button>
                  );
                })}
              </div>

              {/* Accordion: Tùy chỉnh chi tiết (Mặc định ẩn) */}
              <div className="pt-3 border-t border-white/[0.08] mt-1">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="w-full flex items-center justify-between py-2 px-1 text-xs font-medium text-white/50 hover:text-white/80 transition cursor-pointer"
                >
                  <span className="flex items-center gap-1.5">
                    <span>⚙️</span>
                    <span>Tùy chỉnh chi tiết</span>
                  </span>
                  <span className="text-[10px] font-mono">
                    {showAdvanced ? "▲ Thu gọn" : "▼ Mở rộng"}
                  </span>
                </button>

                {showAdvanced && (
                  <div className="space-y-3 pt-3 pb-2 px-1 border-t border-white/[0.04]">
                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Phóng to bắt đầu (Zoom Start)</span>
                        <span className="font-mono text-white/80">
                          {activeClip.motion.zoom_start.toFixed(2)}x
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0.9"
                        max="1.4"
                        step="0.01"
                        value={activeClip.motion.zoom_start}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          updateActiveClip((c) => {
                            c.motion.zoom_start = val;
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Phóng to kết thúc (Zoom End)</span>
                        <span className="font-mono text-white/80">
                          {activeClip.motion.zoom_end.toFixed(2)}x
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0.9"
                        max="1.4"
                        step="0.01"
                        value={activeClip.motion.zoom_end}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          updateActiveClip((c) => {
                            c.motion.zoom_end = val;
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Lia dọc (Pan Y)</span>
                        <span className="font-mono text-white/80">
                          {activeClip.motion.pan_end[1]}px
                        </span>
                      </div>
                      <input
                        type="range"
                        min="-40"
                        max="40"
                        step="1"
                        value={activeClip.motion.pan_end[1]}
                        onChange={(e) => {
                          const val = parseInt(e.target.value, 10);
                          updateActiveClip((c) => {
                            c.motion.pan_end = [c.motion.pan_end[0], val];
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Làm mờ phông nền (Blur)</span>
                        <span className="font-mono text-white/80">
                          {activeClip.background.blur_radius}px
                        </span>
                      </div>
                      <input
                        type="range"
                        min="15"
                        max="95"
                        step="2"
                        value={activeClip.background.blur_radius}
                        onChange={(e) => {
                          const val = parseInt(e.target.value, 10);
                          updateActiveClip((c) => {
                            c.background.blur_radius = val;
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Độ tối phông nền (Darkness)</span>
                        <span className="font-mono text-white/80">
                          {Math.round(activeClip.background.darkness * 100)}%
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="0.9"
                        step="0.05"
                        value={activeClip.background.darkness}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          updateActiveClip((c) => {
                            c.background.darkness = val;
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
