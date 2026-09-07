"use client";

import React, { useRef } from "react";
import { TimelineContract, VisualClip, resolveImageUrl } from "../types";

interface TimelineProps {
  timeline: TimelineContract;
  currentTime: number;
  onSeek: (time: number) => void;
  selectedClipId: string | null;
  onSelectClip: (clipId: string) => void;
}

export default function Timeline({
  timeline,
  currentTime,
  onSeek,
  selectedClipId,
  onSelectClip,
}: TimelineProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const totalDur = Math.max(0.1, timeline.total_duration);

  // Helper for Ken Burns motion badge
  const getMotionLabel = (clip: VisualClip) => {
    const m = clip.motion;
    if (clip.shot_type?.includes("HOOK") || (m && m.zoom_end >= 1.18)) {
      return "💥 PUNCH ZOOM";
    }
    if (m && m.pan_end && (m.pan_end[1] < -5 || m.pan_end[1] > 5)) {
      return "📜 PAN DOWN";
    }
    if (m && m.zoom_end && m.zoom_end < 1.0) {
      return "🌐 ZOOM OUT";
    }
    return "🔍 ZOOM IN";
  };

  // Handle timeline scrub click/drag
  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const clickX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const targetTime = (clickX / rect.width) * totalDur;
    const clampedTime = Math.min(totalDur, Math.max(0, targetTime));
    onSeek(clampedTime);

    // Sync selected visual clip with Inspector Tab "Hiệu ứng"
    const matchingVisual =
      timeline.visual_clips.find(
        (v) => clampedTime >= v.start_time && clampedTime < v.end_time,
      ) ||
      (clampedTime >= totalDur
        ? timeline.visual_clips[timeline.visual_clips.length - 1]
        : timeline.visual_clips[0]);
    if (matchingVisual && onSelectClip) {
      onSelectClip(matchingVisual.clip_id);
    }
  };

  const playheadPercent = Math.min(
    100,
    Math.max(0, (currentTime / totalDur) * 100),
  );

  const selectedVisual = timeline.visual_clips.find(
    (v) => v.clip_id === selectedClipId,
  );

  // Speaker Color Scheme (Matte Finish)
  const getSpeakerTheme = (speaker: string) => {
    const s = speaker.toUpperCase();
    if (s.includes("HOOK")) {
      return {
        bg: "bg-[#21162b] border-purple-500/35 hover:border-purple-500/55 text-zinc-100",
        accent: "text-purple-300",
        badge: "🎣 HOOK",
      };
    }
    if (
      s.includes("CTA") ||
      s.includes("CALL_TO_ACTION") ||
      s.includes("ENDING")
    ) {
      return {
        bg: "bg-[#221b12] border-amber-500/35 hover:border-amber-500/55 text-zinc-100",
        accent: "text-amber-300",
        badge: "⚡ CTA",
      };
    }
    if (s.includes("BODY")) {
      return {
        bg: "bg-[#121c2a] border-sky-500/35 hover:border-sky-500/55 text-zinc-100",
        accent: "text-sky-300",
        badge: "🎬 BODY",
      };
    }
    if (s.includes("NAMMINH") || s.includes("AI")) {
      return {
        bg: "bg-[#181628] border-violet-500/35 hover:border-violet-500/55 text-zinc-100",
        accent: "text-violet-300",
        badge: "🎙️ AI REVIEW",
      };
    }
    if (s.includes("RIN")) {
      return {
        bg: "bg-[#1c1620] border-pink-500/25 hover:border-pink-500/45 text-zinc-100",
        accent: "text-pink-300",
        badge: "RIN",
      };
    }
    if (s.includes("KAZU")) {
      return {
        bg: "bg-[#141a22] border-sky-500/25 hover:border-sky-500/45 text-zinc-100",
        accent: "text-sky-300",
        badge: "KAZU",
      };
    }
    if (s.includes("PRIEST") || s.includes("LINH MỤC")) {
      return {
        bg: "bg-[#1b1915] border-amber-500/25 hover:border-amber-500/45 text-zinc-100",
        accent: "text-amber-300",
        badge: "PRIEST",
      };
    }
    return {
      bg: "bg-[#181622] border-violet-500/25 hover:border-violet-500/45 text-zinc-100",
      accent: "text-violet-300",
      badge: speaker,
    };
  };

  // Generate ruler tick marks
  const ticks = [];
  const numSeconds = Math.ceil(totalDur);
  for (let s = 0; s <= numSeconds; s++) {
    const leftPct = (s / totalDur) * 100;
    if (leftPct <= 100) {
      ticks.push({ second: s, leftPct });
    }
  }

  return (
    <div className="w-full h-full flex flex-col bg-[#0b0b0e] select-none text-xs border-t border-white/[0.08]">
      {/* Main Multi-Track Container */}
      <div className="flex-1 min-h-0 flex flex-row overflow-hidden">
        {/* Left Headers Column: Track Labels */}
        <div className="w-24 shrink-0 border-r border-white/[0.08] bg-[#0d0d11] flex flex-col z-10">
          {/* Ruler spacer */}
          <div className="h-6 shrink-0 border-b border-white/[0.06] px-2 flex items-center text-[10px] font-mono text-zinc-500">
            TRACK
          </div>

          {/* Track 0 Label: Visual Panels */}
          <div className="flex-1 min-h-0 border-b border-white/[0.06] px-2.5 flex flex-col justify-center gap-0.5 text-white/80">
            <div className="flex items-center gap-1.5 text-xs font-semibold">
              <span>🎬</span>
              <span className="truncate">Visual</span>
            </div>
            <span className="text-[9px] text-white/40 font-mono uppercase tracking-wider">
              {timeline.visual_clips.length} Panels
            </span>
          </div>

          {/* Track 1 Label: Thoại */}
          <div className="flex-1 min-h-0 px-2.5 flex flex-col justify-center gap-0.5 text-white/80">
            <div className="flex items-center gap-1.5 text-xs font-semibold">
              <span>🎙️</span>
              <span className="truncate">Thoại</span>
            </div>
            <span className="text-[9px] text-white/40 font-mono uppercase tracking-wider">
              Voice
            </span>
          </div>
        </div>

        {/* Right Interactive Tracks Area */}
        <div
          ref={containerRef}
          onClick={handleTimelineClick}
          className="flex-1 min-w-0 relative flex flex-col overflow-x-hidden cursor-pointer bg-[#08080b]"
        >
          {/* 1. Time Ruler */}
          <div className="relative h-6 shrink-0 border-b border-white/[0.06] bg-white/[0.02]">
            {ticks.map((t) => (
              <div
                key={t.second}
                className="absolute top-0 bottom-0 flex flex-col items-center pointer-events-none"
                style={{ left: `${t.leftPct}%` }}
              >
                <div className="w-[1px] h-1.5 bg-white/20" />
                <span className="text-[10px] font-mono text-zinc-500 mt-0.5 -translate-x-1/2 select-none">
                  {t.second}s
                </span>
              </div>
            ))}
          </div>

          {/* 2. Track 0: Visual Panels (Khung tranh & Hiệu ứng Ken Burns) */}
          <div className="flex-1 min-h-0 relative border-b border-white/[0.06] px-1 py-1.5">
            {timeline.visual_clips.map((clip) => {
              const leftPct = (clip.start_time / totalDur) * 100;
              const widthPct = Math.max(3, (clip.duration / totalDur) * 100);
              const isCurrent =
                currentTime >= clip.start_time && currentTime < clip.end_time;
              const isSelected = clip.clip_id === selectedClipId;
              const thumbUrl = resolveImageUrl(
                clip.image_path || timeline.source_image_path,
              );
              const motionLabel = getMotionLabel(clip);

              return (
                <div
                  key={clip.clip_id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSeek(clip.start_time);
                    if (onSelectClip) {
                      onSelectClip(clip.clip_id);
                    }
                  }}
                  className={`absolute top-1.5 bottom-1.5 rounded-lg border px-2 py-1 transition flex items-center gap-2 overflow-hidden cursor-pointer ${
                    isSelected
                      ? "bg-[#1f1a30] border-violet-400 ring-1 ring-violet-400/70 shadow-md shadow-black/50 z-20"
                      : isCurrent
                        ? "bg-[#191924] border-white/60 ring-1 ring-white/50 shadow-sm shadow-black/40 z-15"
                        : "bg-[#12121a] border-white/10 hover:border-white/25 text-zinc-300 z-10"
                  }`}
                  style={{
                    left: `${leftPct}%`,
                    width: `calc(${widthPct}% - 3px)`,
                  }}
                  title={`${clip.panel_id || clip.clip_id} (${clip.duration.toFixed(1)}s) - ${motionLabel}`}
                >
                  {/* Thumbnail */}
                  <div className="w-8 h-8 rounded shrink-0 overflow-hidden bg-zinc-900 border border-white/10 relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={thumbUrl}
                      alt={clip.panel_id}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = "/page_01.jpg";
                      }}
                    />
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0 flex flex-col justify-center">
                    <div className="flex items-center justify-between w-full">
                      <span className="text-[10px] font-mono font-bold text-violet-300 truncate">
                        {motionLabel}
                      </span>
                      <span className="text-[9px] font-mono text-zinc-400 shrink-0 ml-1">
                        {clip.duration.toFixed(1)}s
                      </span>
                    </div>
                    <span className="text-[9px] font-mono text-zinc-500 truncate">
                      {clip.panel_id || clip.clip_id}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* 3. Track 1: Thoại (Voice Clips) */}
          <div className="flex-1 min-h-0 relative px-1 py-1.5">
            {timeline.audio_clips.map((clip) => {
              const leftPct = (clip.start_time / totalDur) * 100;
              const widthPct = Math.max(3, (clip.duration / totalDur) * 100);
              const theme = getSpeakerTheme(clip.speaker_label);
              const isCurrent =
                currentTime >= clip.start_time && currentTime < clip.end_time;
              const isVisualSelected =
                selectedVisual &&
                clip.start_time >= selectedVisual.start_time &&
                clip.start_time < selectedVisual.end_time;

              return (
                <div
                  key={clip.clip_id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSeek(clip.start_time);
                    const matchingVisual =
                      timeline.visual_clips.find(
                        (v) =>
                          clip.start_time >= v.start_time &&
                          clip.start_time < v.end_time,
                      ) || timeline.visual_clips[0];
                    if (matchingVisual && onSelectClip) {
                      onSelectClip(matchingVisual.clip_id);
                    }
                  }}
                  className={`absolute top-1.5 bottom-1.5 rounded-lg border px-2.5 py-1.5 transition flex flex-col justify-between overflow-hidden cursor-pointer ${theme.bg} ${
                    isCurrent
                      ? "ring-1 ring-white/70 shadow-md shadow-black/50 z-20"
                      : isVisualSelected
                        ? "ring-1 ring-violet-400/50 shadow-sm shadow-black/40 z-15"
                        : "z-10"
                  }`}
                  style={{
                    left: `${leftPct}%`,
                    width: `calc(${widthPct}% - 3px)`,
                  }}
                  title={`${clip.speaker_label}: "${clip.text}"`}
                >
                  <div className="flex items-center justify-between w-full">
                    <span
                      className={`truncate font-mono uppercase tracking-wide text-xs font-bold ${theme.accent}`}
                    >
                      {theme.badge || clip.speaker_label}
                    </span>
                    <span className="text-[10px] font-mono opacity-60 shrink-0 ml-1.5">
                      {clip.duration.toFixed(1)}s
                    </span>
                  </div>
                  <div className="text-[11px] text-zinc-400 line-clamp-2 leading-snug break-words">
                    &ldquo;{clip.text}&rdquo;
                  </div>
                </div>
              );
            })}
          </div>

          {/* Vertical Playhead Line across all tracks */}
          <div
            className="absolute top-0 bottom-0 w-[1.5px] bg-rose-500/90 pointer-events-none z-30 shadow-[0_0_4px_rgba(244,63,94,0.4)]"
            style={{ left: `${playheadPercent}%` }}
          >
            {/* Top pointer head */}
            <div className="absolute -top-1 -translate-x-1/2 w-2.5 h-2.5 bg-rose-500 rotate-45 rounded-xs shadow-sm" />
          </div>
        </div>
      </div>
    </div>
  );
}
