"use client";

import React, { useRef } from "react";
import { TimelineContract } from "../types";

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
    if (s.includes("RIN")) {
      return {
        bg: "bg-[#1c1620] border-pink-500/25 hover:border-pink-500/45 text-zinc-100",
        accent: "text-pink-300",
      };
    }
    if (s.includes("KAZU")) {
      return {
        bg: "bg-[#141a22] border-sky-500/25 hover:border-sky-500/45 text-zinc-100",
        accent: "text-sky-300",
      };
    }
    if (s.includes("PRIEST") || s.includes("LINH MỤC")) {
      return {
        bg: "bg-[#1b1915] border-amber-500/25 hover:border-amber-500/45 text-zinc-100",
        accent: "text-amber-300",
      };
    }
    return {
      bg: "bg-[#181622] border-violet-500/25 hover:border-violet-500/45 text-zinc-100",
      accent: "text-violet-300",
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

  // SFX Cue markers (Matte Finish)
  const sfxMarkers = [
    {
      id: "sfx_1",
      label: "✨ Whoosh",
      type: "Chuyển cảnh",
      startTime: 0.0,
      duration: Math.min(1.2, totalDur * 0.15),
      color:
        "bg-[#181522] border-purple-500/25 text-zinc-200 hover:border-purple-500/45",
      accent: "text-purple-300",
    },
    {
      id: "sfx_2",
      label: "🔔 Bell",
      type: "Chuông lễ đường",
      startTime: Math.min(5.2, totalDur * 0.5),
      duration: Math.min(1.5, totalDur * 0.15),
      color:
        "bg-[#1a1814] border-amber-500/25 text-zinc-200 hover:border-amber-500/45",
      accent: "text-amber-300",
    },
    {
      id: "sfx_3",
      label: "💓 Heartbeat",
      type: "Nhịp tim cảm xúc",
      startTime: Math.min(8.1, totalDur * 0.78),
      duration: Math.min(1.8, totalDur * 0.2),
      color:
        "bg-[#1c1416] border-rose-500/25 text-zinc-200 hover:border-rose-500/45",
      accent: "text-rose-300",
    },
  ];

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

          {/* Track 1 Label: Thoại */}
          <div className="flex-1 min-h-0 border-b border-white/[0.06] px-2.5 flex flex-col justify-center gap-0.5 text-white/80">
            <div className="flex items-center gap-1.5 text-xs font-semibold">
              <span>🎙️</span>
              <span className="truncate">Thoại</span>
            </div>
            <span className="text-[9px] text-white/40 font-mono uppercase tracking-wider">
              Voice
            </span>
          </div>

          {/* Track 2 Label: BGM */}
          <div className="flex-1 min-h-0 border-b border-white/[0.06] px-2.5 flex flex-col justify-center gap-0.5 text-white/80">
            <div className="flex items-center gap-1.5 text-xs font-semibold">
              <span>🎵</span>
              <span className="truncate">BGM</span>
            </div>
            <span className="text-[9px] text-white/40 font-mono uppercase tracking-wider">
              Music
            </span>
          </div>

          {/* Track 3 Label: SFX */}
          <div className="flex-1 min-h-0 px-2.5 flex flex-col justify-center gap-0.5 text-white/80">
            <div className="flex items-center gap-1.5 text-xs font-semibold">
              <span>⚡</span>
              <span className="truncate">SFX</span>
            </div>
            <span className="text-[9px] text-white/40 font-mono uppercase tracking-wider">
              Effects
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

          {/* 2. Track 1: Thoại (Voice Clips) */}
          <div className="flex-1 min-h-0 relative border-b border-white/[0.06] px-1 py-1.5">
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
                      {clip.speaker_label}
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

          {/* 3. Track 2: BGM (Nhạc nền Manga) */}
          <div className="flex-1 min-h-0 relative border-b border-white/[0.06] px-1 py-1.5">
            <div
              className="absolute inset-y-1.5 rounded-lg border border-emerald-500/25 bg-[#111815] text-zinc-200 px-3 py-2 flex items-center justify-between overflow-hidden cursor-pointer shadow-sm hover:border-emerald-500/40 transition"
              style={{ left: "0%", right: "0%" }}
            >
              <div className="flex flex-col justify-center h-full min-w-0 mr-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm">🎵</span>
                  <span className="text-xs font-semibold truncate text-emerald-300/90">
                    Cathedral Romance (BGM Loop)
                  </span>
                  <span className="text-[9px] font-mono text-emerald-400/70 bg-emerald-950/50 px-1.5 py-0.5 rounded border border-emerald-800/30 shrink-0">
                    100% Vol
                  </span>
                </div>
                <span className="text-[10px] text-zinc-400 font-mono mt-0.5 truncate">
                  Bản phối lofi cảm xúc tự động lặp lại theo độ dài trang truyện
                </span>
              </div>

              {/* Decorative Audio Waveform */}
              <div className="flex items-center gap-1 opacity-50 pointer-events-none shrink-0 pr-2">
                <span className="w-[2px] h-3 bg-emerald-400/80 rounded-full animate-pulse" />
                <span className="w-[2px] h-6 bg-emerald-400/80 rounded-full" />
                <span className="w-[2px] h-4 bg-emerald-400/80 rounded-full" />
                <span className="w-[2px] h-8 bg-emerald-400/80 rounded-full animate-pulse" />
                <span className="w-[2px] h-5 bg-emerald-400/80 rounded-full" />
                <span className="w-[2px] h-9 bg-emerald-400/80 rounded-full" />
                <span className="w-[2px] h-6 bg-emerald-400/80 rounded-full animate-pulse" />
                <span className="w-[2px] h-4 bg-emerald-400/80 rounded-full" />
                <span className="w-[2px] h-7 bg-emerald-400/80 rounded-full" />
                <span className="w-[2px] h-3 bg-emerald-400/80 rounded-full" />
              </div>
            </div>
          </div>

          {/* 4. Track 3: SFX (Hiệu ứng âm thanh) */}
          <div className="flex-1 min-h-0 relative px-1 py-1.5">
            {sfxMarkers.map((sfx) => {
              const leftPct = (sfx.startTime / totalDur) * 100;
              const widthPct = Math.max(4, (sfx.duration / totalDur) * 100);

              return (
                <div
                  key={sfx.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSeek(sfx.startTime);
                    const matchingVisual =
                      timeline.visual_clips.find(
                        (v) =>
                          sfx.startTime >= v.start_time &&
                          sfx.startTime < v.end_time,
                      ) || timeline.visual_clips[0];
                    if (matchingVisual && onSelectClip) {
                      onSelectClip(matchingVisual.clip_id);
                    }
                  }}
                  className={`absolute top-1.5 bottom-1.5 rounded-lg border px-2.5 py-1.5 flex flex-col justify-between overflow-hidden transition cursor-pointer ${sfx.color}`}
                  style={{
                    left: `${leftPct}%`,
                    width: `calc(${widthPct}% - 3px)`,
                  }}
                  title={`${sfx.label} (${sfx.duration.toFixed(1)}s)`}
                >
                  <div className="flex items-center justify-between w-full">
                    <span
                      className={`text-xs font-bold truncate leading-none ${sfx.accent}`}
                    >
                      {sfx.label}
                    </span>
                    <span className="text-[10px] font-mono opacity-60 shrink-0 ml-1">
                      {sfx.duration.toFixed(1)}s
                    </span>
                  </div>
                  <span className="text-[10px] text-zinc-400 font-mono truncate leading-none">
                    {sfx.type}
                  </span>
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
