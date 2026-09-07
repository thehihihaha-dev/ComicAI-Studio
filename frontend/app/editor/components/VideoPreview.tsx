"use client";

import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import {
  DEFAULT_AUDIO_CONFIG,
  TimelineContract,
  VisualClip,
  resolveAudioUrl,
  resolveImageUrl,
} from "../types";

export interface VideoPreviewHandle {
  togglePlay: () => void;
  play: () => void;
  pause: () => void;
}

interface VideoPreviewProps {
  timeline: TimelineContract;
  currentTime: number;
  isPlaying: boolean;
  onTimeUpdate: (time: number) => void;
  onTogglePlay: () => void;
  selectedClipId?: string | null;
  activePageImage?: string | null;
}

// Persistent image cache across renders and page switches to prevent tearing
const imageElementCache = new Map<string, HTMLImageElement>();

function findLoadedCandidateImage(
  candidateUrls: (string | null | undefined)[],
  onNeedRepaint?: () => void,
): HTMLImageElement | null {
  const cleanUrls: string[] = [];
  for (const raw of candidateUrls) {
    if (raw) {
      const resolved = resolveImageUrl(raw);
      if (!cleanUrls.includes(resolved)) {
        cleanUrls.push(resolved);
      }
    }
  }
  if (!cleanUrls.includes("/page_01.jpg")) {
    cleanUrls.push("/page_01.jpg");
  }

  // 1. Kick off preloading for all candidate URLs not yet cached
  for (const url of cleanUrls) {
    if (!imageElementCache.has(url)) {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.src = url;
      img.onload = () => {
        imageElementCache.set(url, img);
        if (onNeedRepaint) onNeedRepaint();
      };
      img.onerror = () => {
        const fallbackImg = new Image();
        fallbackImg.src = url;
        fallbackImg.onload = () => {
          imageElementCache.set(url, fallbackImg);
          if (onNeedRepaint) onNeedRepaint();
        };
        imageElementCache.set(url, fallbackImg);
      };
      imageElementCache.set(url, img);
    }
  }

  // 2. Return the highest-priority candidate that is already fully loaded
  for (const url of cleanUrls) {
    const cached = imageElementCache.get(url);
    if (cached && cached.complete && cached.naturalWidth > 0) {
      return cached;
    }
  }

  const p1 = imageElementCache.get("/page_01.jpg");
  if (p1 && p1.complete && p1.naturalWidth > 0) {
    return p1;
  }

  return null;
}

function isAiReviewClip(c: {
  source?: string;
  speaker_label?: string;
  voice_id?: string;
}): boolean {
  if (c.source === "ai_review_script") return true;
  if (c.source === "manga_dialogue") return false;
  const speaker = (c.speaker_label || "").toUpperCase();
  const voice = (c.voice_id || "").toLowerCase();
  if (
    speaker.includes("NAMMINH") ||
    speaker.includes("AI") ||
    speaker.includes("REVIEW") ||
    speaker.includes("HOOK") ||
    speaker.includes("BODY") ||
    speaker.includes("CTA") ||
    voice.includes("namminh")
  ) {
    return true;
  }
  return !c.source;
}

function findActiveVoiceClip(
  t: number,
  clips: TimelineContract["audio_clips"],
): { clip: TimelineContract["audio_clips"][0]; offset: number } | null {
  if (!clips || clips.length === 0) return null;
  for (const c of clips) {
    const dur =
      c.duration > 0 ? c.duration : Math.max(0.1, c.end_time - c.start_time);
    if (isAiReviewClip(c) && t >= c.start_time && t < c.start_time + dur) {
      return { clip: c, offset: Math.max(0, t - c.start_time) };
    }
  }
  return null;
}

const VideoPreview = forwardRef<VideoPreviewHandle, VideoPreviewProps>(
  function VideoPreview(
    {
      timeline,
      currentTime,
      isPlaying,
      onTimeUpdate,
      onTogglePlay,
      activePageImage,
    },
    ref,
  ) {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const voiceAudioRef = useRef<HTMLAudioElement | null>(null);
    const currentPlayingClipUrlRef = useRef<string>("");
    const [imagesLoadedKey, setImagesLoadedKey] = useState(0);
    const animationFrameRef = useRef<number | null>(null);
    const currentTimeRef = useRef(currentTime);
    const onTimeUpdateRef = useRef(onTimeUpdate);
    const onTogglePlayRef = useRef(onTogglePlay);
    const timelineRef = useRef(timeline);
    const renderFrameRef = useRef<((t: number) => void) | null>(null);

    useEffect(() => {
      onTimeUpdateRef.current = onTimeUpdate;
      onTogglePlayRef.current = onTogglePlay;
      timelineRef.current = timeline;
    }, [onTimeUpdate, onTogglePlay, timeline]);

    const handleImageLoaded = useCallback(() => {
      setImagesLoadedKey((k) => k + 1);
    }, []);

    // Preload initial image candidates immediately on mount or timeline change
    useEffect(() => {
      const candidates: (string | undefined | null)[] = [
        timeline.source_image_path,
        activePageImage,
        "/page_01.jpg",
      ];
      if (timeline.visual_clips) {
        for (const c of timeline.visual_clips) {
          if (c.image_path) candidates.push(c.image_path);
          if (c.page_image_path) candidates.push(c.page_image_path);
        }
      }
      findLoadedCandidateImage(candidates, handleImageLoaded);
    }, [timeline, activePageImage, handleImageLoaded]);

    useEffect(() => {
      currentTimeRef.current = currentTime;
    }, [currentTime]);

    // Imperative audio unlock & play within user gesture context
    const handlePlay = useCallback(() => {
      console.log("[Audio Debug] Trigger play (handlePlay user gesture):", {
        currentTime: currentTimeRef.current,
        isPlaying,
        voiceSrc: voiceAudioRef.current?.src,
        voiceReadyState: voiceAudioRef.current?.readyState,
      });

      const vAudio = voiceAudioRef.current;
      const active = findActiveVoiceClip(
        currentTimeRef.current,
        timelineRef.current.audio_clips,
      );

      if (vAudio && active) {
        const url = resolveAudioUrl(
          active.clip.audio_url || active.clip.file_path,
        );
        if (url) {
          if (!vAudio.src.includes(url) && !url.includes(vAudio.src)) {
            vAudio.src = url;
          }
          vAudio.currentTime = active.offset;
          vAudio.muted = false;
          vAudio.volume = DEFAULT_AUDIO_CONFIG.masterVoiceVolume;
          vAudio.play().catch((err) => {
            console.warn("Voice playback blocked:", err);
          });
          currentPlayingClipUrlRef.current = url;
        }
      }

      if (!isPlaying) {
        onTogglePlayRef.current();
      }
    }, [isPlaying]);

    const handlePause = useCallback(() => {
      if (voiceAudioRef.current && !voiceAudioRef.current.paused) {
        voiceAudioRef.current.pause();
      }
      currentPlayingClipUrlRef.current = "";
      if (isPlaying) {
        onTogglePlay();
      }
    }, [isPlaying, onTogglePlay]);

    const handleTogglePlay = useCallback(() => {
      if (isPlaying) {
        handlePause();
      } else {
        handlePlay();
      }
    }, [isPlaying, handlePlay, handlePause]);

    useImperativeHandle(
      ref,
      () => ({
        togglePlay: handleTogglePlay,
        play: handlePlay,
        pause: handlePause,
      }),
      [handleTogglePlay, handlePlay, handlePause],
    );

    // 4. Render Canvas Frame at Current Time
    const renderFrame = useCallback(
      (t: number) => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const canvasW = canvas.width; // 1080
        const canvasH = canvas.height; // 1920

        // Find active visual clip
        const clips = timeline.visual_clips;
        if (clips.length === 0) {
          ctx.fillStyle = "#0a0a0e";
          ctx.fillRect(0, 0, canvasW, canvasH);
          return;
        }

        let activeClip: VisualClip = clips[0];
        for (const clip of clips) {
          const clipEnd = clip.end_time || clip.start_time + clip.duration;
          if (t >= clip.start_time && t < clipEnd) {
            activeClip = clip;
            break;
          }
        }
        if (t >= clips[clips.length - 1].end_time) {
          activeClip = clips[clips.length - 1];
        }

        // Resolve panel image using resilient candidate search prioritizing active clip image
        const candidateUrls = [
          activeClip?.image_path,
          activeClip?.page_image_path,
          activePageImage,
          timeline.source_image_path,
          "/page_01.jpg",
        ];
        const img = findLoadedCandidateImage(candidateUrls, handleImageLoaded);

        if (!img || !img.complete || img.naturalWidth === 0) {
          ctx.fillStyle = "#09090c";
          ctx.fillRect(0, 0, canvasW, canvasH);
          return;
        }

        let [bx1, by1, bx2, by2] = activeClip.bbox || [
          0,
          0,
          img.naturalWidth,
          img.naturalHeight,
        ];
        // Handle normalized coordinates [0..1]
        if (bx2 <= 1.05 && by2 <= 1.05) {
          bx1 = Math.round(bx1 * img.naturalWidth);
          by1 = Math.round(by1 * img.naturalHeight);
          bx2 = Math.round(bx2 * img.naturalWidth);
          by2 = Math.round(by2 * img.naturalHeight);
        }

        // Clamp bbox to image boundaries safely
        const cl_x1 = Math.max(0, Math.min(img.naturalWidth - 1, bx1));
        const cl_y1 = Math.max(0, Math.min(img.naturalHeight - 1, by1));
        const cl_x2 = Math.max(cl_x1 + 1, Math.min(img.naturalWidth, bx2));
        const cl_y2 = Math.max(cl_y1 + 1, Math.min(img.naturalHeight, by2));
        const cropW = Math.max(1, cl_x2 - cl_x1);
        const cropH = Math.max(1, cl_y2 - cl_y1);

        // Ken Burns cubic smoothstep easing calculation:
        // t_norm = (currentTime - clip.start_time) / clip.duration
        // w(t) = 3t^2 - 2t^3
        const dur = Math.max(0.001, activeClip.duration);
        const progress = Math.min(
          1.0,
          Math.max(0.0, (t - activeClip.start_time) / dur),
        );
        const wt = progress * progress * (3.0 - 2.0 * progress);

        const m = activeClip.motion || {
          zoom_start: 1.0,
          zoom_end: 1.05,
          pan_start: [0, 0],
          pan_end: [0, 0],
        };

        const isPunch =
          activeClip.shot_type?.toLowerCase().includes("punch") ||
          activeClip.clip_id?.toLowerCase().includes("punch") ||
          (m.zoom_end > 1.2 && m.pan_end[1] === 0);

        let currentZoom: number;
        let panX: number;
        let panY: number;

        if (isPunch) {
          const tPunch = Math.min(
            1.0,
            Math.max(0.0, (t - activeClip.start_time) / 0.4),
          );
          const wtPunch = tPunch * tPunch * (3.0 - 2.0 * tPunch);
          currentZoom =
            m.zoom_start +
            (m.zoom_end - m.zoom_start) * wtPunch +
            0.01 * progress;
          panX = Math.round(
            m.pan_start[0] + (m.pan_end[0] - m.pan_start[0]) * wtPunch,
          );
          panY = Math.round(
            m.pan_start[1] + (m.pan_end[1] - m.pan_start[1]) * wtPunch,
          );
        } else {
          currentZoom = m.zoom_start + (m.zoom_end - m.zoom_start) * wt;
          panX = Math.round(
            m.pan_start[0] + (m.pan_end[0] - m.pan_start[0]) * wt,
          );
          panY = Math.round(
            m.pan_start[1] + (m.pan_end[1] - m.pan_start[1]) * wt,
          );
        }

        // Step A: Draw Gaussian-blurred darkened backdrop
        ctx.save();
        ctx.fillStyle = "#09090c";
        ctx.fillRect(0, 0, canvasW, canvasH);

        const blurRadius = Math.max(
          0,
          activeClip.background?.blur_radius || 51,
        );
        const darkness = Math.min(
          1.0,
          Math.max(0.0, activeClip.background?.darkness ?? 0.45),
        );
        ctx.filter = `blur(${Math.round(blurRadius / 2.5)}px) brightness(${darkness})`;
        ctx.drawImage(
          img,
          cl_x1,
          cl_y1,
          cropW,
          cropH,
          -50,
          -50,
          canvasW + 100,
          canvasH + 100,
        );
        ctx.restore();

        // Step B: Draw Foreground panel with Ken Burns scaling & pan
        const maxFgW = 1040;
        const maxFgH = 1680;
        const baseScale = Math.min(maxFgW / cropW, maxFgH / cropH) * 1.18;
        const finalScale = baseScale * currentZoom;

        const fgW = Math.round(cropW * finalScale);
        const fgH = Math.round(cropH * finalScale);

        const centerX = canvasW / 2 + panX;
        const centerY = canvasH / 2 + panY;

        const x1 = Math.round(centerX - fgW / 2);
        const y1 = Math.round(centerY - fgH / 2);

        // Draw subtle border
        const bWidth = activeClip.background?.border_width ?? 4;
        if (bWidth > 0) {
          ctx.save();
          const borderColor = activeClip.background?.border_color || [
            255, 255, 255,
          ];
          ctx.strokeStyle = `rgba(${borderColor.join(",")}, 0.95)`;
          ctx.lineWidth = bWidth * 2;
          ctx.strokeRect(x1, y1, fgW, fgH);
          ctx.restore();
        }

        // Draw image crop
        ctx.drawImage(img, cl_x1, cl_y1, cropW, cropH, x1, y1, fgW, fgH);
      },
      [timeline, activePageImage, handleImageLoaded],
    );

    useEffect(() => {
      renderFrameRef.current = renderFrame;
    }, [renderFrame]);

    // 5. Continuous Animation Loop when Playing (Timeline currentTime is master clock)
    useEffect(() => {
      if (!isPlaying) {
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
          animationFrameRef.current = null;
        }
        voiceAudioRef.current?.pause();
        currentPlayingClipUrlRef.current = "";
        return;
      }

      let lastTimestamp = performance.now();
      let localTime = currentTimeRef.current;
      const voiceAudio = voiceAudioRef.current;

      // Start audio tracks ONCE when isPlaying transitions to true
      console.log("[Audio Debug] Trigger play (isPlaying effect):", {
        currentTime: currentTimeRef.current,
        isPlaying,
        voiceSrc: voiceAudioRef.current?.src,
        voiceReadyState: voiceAudioRef.current?.readyState,
      });

      // Synchronize initial active clip immediately on start
      const initialActive = findActiveVoiceClip(
        localTime,
        timelineRef.current.audio_clips,
      );
      if (voiceAudio && initialActive) {
        const url = resolveAudioUrl(
          initialActive.clip.audio_url || initialActive.clip.file_path,
        );
        if (url) {
          if (!voiceAudio.src.includes(url) && !url.includes(voiceAudio.src)) {
            voiceAudio.src = url;
          }
          voiceAudio.currentTime = initialActive.offset;
          voiceAudio.muted = false;
          voiceAudio.volume = DEFAULT_AUDIO_CONFIG.masterVoiceVolume;
          voiceAudio.play().catch(() => {});
          currentPlayingClipUrlRef.current = url;
        }
      }

      const loop = (now: number) => {
        const deltaSec = Math.min(0.1, (now - lastTimestamp) / 1000.0);
        lastTimestamp = now;

        // Master clock is timeline currentTime (deltaSec accumulation)
        localTime += deltaSec;

        const totalDuration = timelineRef.current.total_duration;
        if (localTime >= totalDuration) {
          const finalTime = totalDuration;
          onTimeUpdateRef.current(finalTime);
          renderFrameRef.current?.(finalTime);
          voiceAudioRef.current?.pause();
          currentPlayingClipUrlRef.current = "";
          onTogglePlayRef.current(); // stop playback at end
          return;
        }

        onTimeUpdateRef.current(localTime);
        renderFrameRef.current?.(localTime);

        // Synchronize Voice Track per active AI Review clip without audio reload loop
        const active = findActiveVoiceClip(
          localTime,
          timelineRef.current.audio_clips,
        );
        if (voiceAudio) {
          if (active) {
            const url = resolveAudioUrl(
              active.clip.audio_url || active.clip.file_path,
            );
            if (url) {
              const currentSrc =
                voiceAudio.getAttribute("src") || voiceAudio.src || "";
              // Only update src and start playback if switching to a genuinely new audio file
              if (!currentSrc.includes(url) && !url.includes(currentSrc)) {
                voiceAudio.src = url;
                voiceAudio.currentTime = active.offset;
                voiceAudio.play().catch(() => {});
                currentPlayingClipUrlRef.current = url;
              } else {
                // Discrete clip: resync only if drift > 0.3s
                if (Math.abs(voiceAudio.currentTime - active.offset) > 0.3) {
                  voiceAudio.currentTime = active.offset;
                }
                if (voiceAudio.paused) {
                  voiceAudio.play().catch(() => {});
                }
              }
            } else {
              if (!voiceAudio.paused) {
                voiceAudio.pause();
              }
              currentPlayingClipUrlRef.current = "";
            }
          } else {
            // Pause in gaps between clips
            if (!voiceAudio.paused) {
              voiceAudio.pause();
            }
            currentPlayingClipUrlRef.current = "";
          }
        }

        animationFrameRef.current = requestAnimationFrame(loop);
      };

      animationFrameRef.current = requestAnimationFrame(loop);

      return () => {
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
          animationFrameRef.current = null;
        }
      };
    }, [isPlaying]);

    // 6. Seeking & Instant WYSIWYG Repaint: whenever currentTime changes while paused
    useEffect(() => {
      if (isPlaying) return;
      renderFrame(currentTime);

      const voiceAudio = voiceAudioRef.current;
      if (!voiceAudio) return;

      const active = findActiveVoiceClip(currentTime, timeline.audio_clips);
      if (active) {
        const url = resolveAudioUrl(
          active.clip.audio_url || active.clip.file_path,
        );
        if (url) {
          if (!voiceAudio.src.includes(url) && !url.includes(voiceAudio.src)) {
            voiceAudio.src = url;
          }
          voiceAudio.currentTime = active.offset;
          currentPlayingClipUrlRef.current = url;
          return;
        }
      }

      if (!voiceAudio.paused) {
        voiceAudio.pause();
      }
      currentPlayingClipUrlRef.current = "";
    }, [
      currentTime,
      isPlaying,
      imagesLoadedKey,
      renderFrame,
      timeline.audio_clips,
    ]);

    // 7. Cleanup on unmount & audio event diagnostics
    useEffect(() => {
      const vAudio = voiceAudioRef.current;
      const onVPlay = () =>
        console.log("[Audio Debug] HTML <audio voice> 'play' event:", {
          src: vAudio?.src,
          currentTime: vAudio?.currentTime,
        });
      vAudio?.addEventListener("play", onVPlay);

      return () => {
        vAudio?.removeEventListener("play", onVPlay);
        if (vAudio) {
          vAudio.pause();
          vAudio.src = "";
        }
      };
    }, []);

    return (
      <div className="relative flex items-center justify-center h-full w-full">
        {/* Single-Track Audio Engine: Strictly AI Review Voice */}
        <audio ref={voiceAudioRef} preload="auto" muted={false} />

        {/* 9:16 Canvas Viewport */}
        <div
          onClick={handleTogglePlay}
          className="relative aspect-[9/16] h-full max-h-full rounded-xl overflow-hidden border border-zinc-800/80 shadow-2xl shadow-black/80 bg-black flex items-center justify-center cursor-pointer group select-none"
        >
          <canvas
            ref={canvasRef}
            width={1080}
            height={1920}
            className="w-full h-full object-contain"
          />
          {!isPlaying && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/25 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <div className="w-12 h-12 rounded-full bg-violet-600/90 text-white flex items-center justify-center shadow-lg transform transition-transform group-hover:scale-110">
                <span className="text-xl ml-0.5">▶</span>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  },
);

export default VideoPreview;
