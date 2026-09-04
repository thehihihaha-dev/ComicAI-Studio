"use client";

import React, { useState } from "react";
import { TimelineContract, VisualClip } from "../types";

interface InspectorProps {
  timeline: TimelineContract;
  selectedClipId: string | null;
  currentTime?: number;
  onUpdateTimeline: (updatedTimeline: TimelineContract) => void;
  onSeek?: (time: number) => void;
  onSelectClip?: (clipId: string) => void;
}

interface AIScriptSection {
  id: string;
  tag: string;
  title: string;
  timeRange: string;
  text: string;
}

const DEFAULT_AI_SCRIPT_SECTIONS: AIScriptSection[] = [
  {
    id: "hook",
    tag: "🎣 HOOK",
    title: "Mở đầu cuốn hút (3s đầu)",
    timeRange: "00:00 - 00:03",
    text: "Ai mà ngờ được người vợ ảo kết hôn trong game suốt 2 năm lại chính là nữ thần Idol vạn người mê ngoài đời thực?!",
  },
  {
    id: "setup",
    tag: "🎬 SETUP",
    title: "Thiết lập bối cảnh",
    timeRange: "00:03 - 00:06",
    text: "Hôn lễ thánh đường lung linh trong game diễn ra trước sự chứng giám của linh mục. Lời thề ước thủy chung tưởng như chỉ là trò chơi ảo.",
  },
  {
    id: "dev",
    tag: "⚡ DEVELOPMENT",
    title: "Phát triển cao trào",
    timeRange: "00:06 - 00:15",
    text: "Cuộc gặp gỡ ngoài đời thực bất ngờ bùng nổ khi thân phận thực sự của cô dâu được hé lộ, đảo lộn hoàn toàn cuộc sống của chàng game thủ.",
  },
  {
    id: "payoff",
    tag: "💥 PAYOFF",
    title: "Nút thắt cảm xúc",
    timeRange: "00:15 - 00:22",
    text: 'Khoảnh khắc Rin nghẹn ngào thốt lên "Con xin thề!" đã biến lời hẹn ước ảo thành định mệnh chân thực ngoài đời.',
  },
  {
    id: "ending",
    tag: "🏁 ENDING",
    title: "Kết thúc & Kêu gọi",
    timeRange: "00:22 - 00:26",
    text: "Liệu tình yêu giữa chàng game thủ bình thường và nữ thần Idol sẽ đi về đâu? Đăng ký kênh để đón xem tập tiếp theo!",
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
  onUpdateTimeline,
  onSeek,
  onSelectClip,
}: InspectorProps) {
  const [activeTab, setActiveTab] = useState<
    "dialogue" | "ai_script" | "effects"
  >("dialogue");
  const [aiScript, setAiScript] = useState<AIScriptSection[]>(
    DEFAULT_AI_SCRIPT_SECTIONS,
  );
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

  const handleCopyScript = () => {
    const fullText = aiScript
      .map((s) => `[${s.tag} - ${s.title}]\n${s.text}`)
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
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-width:thin]">
          <div className="flex items-center justify-between pb-1 border-b border-white/[0.08]">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/40">
                Kịch bản AI Review & Tóm Tắt
              </p>
              <p className="text-[10px] text-violet-300/80 mt-0.5">
                Chuẩn cấu trúc video ngắn Short 9:16
              </p>
            </div>
            <button
              type="button"
              onClick={handleCopyScript}
              className="px-2 py-1 rounded bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-[10px] font-medium text-violet-300 transition flex items-center gap-1"
            >
              <span>{copied ? "✓ Đã sao chép" : "📋 Sao chép"}</span>
            </button>
          </div>

          <div className="space-y-3">
            {aiScript.map((sec, idx) => (
              <div
                key={sec.id}
                className="rounded-lg border border-white/[0.08] bg-white/[0.02] p-3 transition hover:border-white/20"
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-violet-300">
                      {sec.tag}
                    </span>
                    <span className="text-[11px] text-white/60 font-medium">
                      · {sec.title}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-white/40">
                    {sec.timeRange}
                  </span>
                </div>
                <textarea
                  rows={3}
                  value={sec.text}
                  onChange={(e) => {
                    const next = [...aiScript];
                    next[idx] = { ...next[idx], text: e.target.value };
                    setAiScript(next);
                  }}
                  className="w-full bg-transparent border-0 border-b border-transparent focus:border-violet-500 text-xs text-white/80 focus:text-white p-0 outline-none resize-none leading-relaxed transition"
                />
              </div>
            ))}
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
