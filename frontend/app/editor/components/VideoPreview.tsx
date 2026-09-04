"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { TimelineContract, VisualClip } from "../types";

interface VideoPreviewProps {
  timeline: TimelineContract;
  currentTime: number;
  isPlaying: boolean;
  onTimeUpdate: (time: number) => void;
  onTogglePlay: () => void;
  selectedClipId?: string | null;
}

// Image cache across renders and page switches to prevent tearing or reloading
const imageElementCache = new Map<string, HTMLImageElement>();

export default function VideoPreview({
  timeline,
  currentTime,
  isPlaying,
  onTimeUpdate,
  onTogglePlay,
}: VideoPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const animationFrameRef = useRef<number | null>(null);
  const currentTimeRef = useRef(currentTime);

  useEffect(() => {
    currentTimeRef.current = currentTime;
  }, [currentTime]);

  // 1. Resolve source image URL (backend static upload or local public fallback)
  const getImageUrl = useCallback(() => {
    if (!timeline.source_image_path) return "/page_01.jpg";
    if (timeline.source_image_path.startsWith("http"))
      return timeline.source_image_path;
    if (
      timeline.source_image_path === "/page_01.jpg" ||
      timeline.source_image_path === "page_01.jpg"
    ) {
      return "/page_01.jpg";
    }
    const cleanPath = timeline.source_image_path.replace(/^backend\//, "");
    return `http://127.0.0.1:8000/${cleanPath}`;
  }, [timeline.source_image_path]);

  // 2. Load Source Image with persistent cache
  useEffect(() => {
    const url = getImageUrl();
    if (imageElementCache.has(url)) {
      const cached = imageElementCache.get(url)!;
      imageRef.current = cached;
      requestAnimationFrame(() => {
        setImageLoaded(true);
      });
      return;
    }

    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = url;
    img.onload = () => {
      imageElementCache.set(url, img);
      imageRef.current = img;
      setImageLoaded(true);
    };
    img.onerror = () => {
      // Fallback to local public page_01.jpg
      const fallbackUrl = "/page_01.jpg";
      if (imageElementCache.has(fallbackUrl)) {
        const cached = imageElementCache.get(fallbackUrl)!;
        imageRef.current = cached;
        requestAnimationFrame(() => {
          setImageLoaded(true);
        });
        return;
      }
      const fallbackImg = new Image();
      fallbackImg.src = fallbackUrl;
      fallbackImg.onload = () => {
        imageElementCache.set(fallbackUrl, fallbackImg);
        imageRef.current = fallbackImg;
        setImageLoaded(true);
      };
    };
  }, [getImageUrl, timeline.page_id]);

  // 3. Resolve Audio URL
  const getAudioUrl = () => {
    if (timeline.page_id === 5) {
      return "http://127.0.0.1:8000/artifacts/audio/day17/previews/page_05_full.mp3";
    }
    return "/page_01_full.mp3";
  };

  // 4. Handle Audio Playback Sync
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      if (Math.abs(audio.currentTime - currentTime) > 0.15) {
        audio.currentTime = currentTime;
      }
      audio.play().catch(() => {});
    } else {
      audio.pause();
      audio.currentTime = currentTime;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (Math.abs(audio.currentTime - currentTime) > 0.25) {
      audio.currentTime = currentTime;
    }
  }, [currentTime]);

  // 5. Render Canvas Frame at Current Time
  const renderFrame = useCallback(
    (t: number) => {
      const canvas = canvasRef.current;
      const img = imageRef.current;
      if (!canvas || !img || !img.complete || img.naturalWidth === 0) return;

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

      let activeClip: VisualClip = clips[clips.length - 1];
      for (const clip of clips) {
        if (t >= clip.start_time && t < clip.end_time) {
          activeClip = clip;
          break;
        }
      }

      const [bx1, by1, bx2, by2] = activeClip.bbox;
      const cropW = Math.max(1, bx2 - bx1);
      const cropH = Math.max(1, by2 - by1);

      // Ken Burns cubic smoothstep easing calculation:
      // t_norm = (currentTime - clip.start_time) / clip.duration
      // w(t) = 3t^2 - 2t^3
      const dur = Math.max(0.001, activeClip.duration);
      const progress = Math.min(
        1.0,
        Math.max(0.0, (t - activeClip.start_time) / dur),
      );
      const wt = progress * progress * (3.0 - 2.0 * progress);

      const m = activeClip.motion;
      const currentZoom = m.zoom_start + (m.zoom_end - m.zoom_start) * wt;
      const panX = Math.round(
        m.pan_start[0] + (m.pan_end[0] - m.pan_start[0]) * wt,
      );
      const panY = Math.round(
        m.pan_start[1] + (m.pan_end[1] - m.pan_start[1]) * wt,
      );

      // Step A: Draw Gaussian-blurred darkened backdrop
      ctx.save();
      ctx.fillStyle = "#09090c";
      ctx.fillRect(0, 0, canvasW, canvasH);

      const blurRadius = Math.max(0, activeClip.background.blur_radius || 51);
      const darkness = Math.min(
        1.0,
        Math.max(0.0, activeClip.background.darkness ?? 0.45),
      );
      ctx.filter = `blur(${Math.round(blurRadius / 2.5)}px) brightness(${darkness})`;
      ctx.drawImage(
        img,
        bx1,
        by1,
        cropW,
        cropH,
        -50,
        -50,
        canvasW + 100,
        canvasH + 100,
      );
      ctx.restore();

      // Step B: Draw Foreground panel with Ken Burns scaling & pan
      const maxFgW = 980;
      const maxFgH = 1500;
      const baseScale = Math.min(maxFgW / cropW, maxFgH / cropH);
      const finalScale = baseScale * currentZoom;

      const fgW = Math.round(cropW * finalScale);
      const fgH = Math.round(cropH * finalScale);

      const centerX = canvasW / 2 + panX;
      const centerY = canvasH / 2 + panY;

      const x1 = Math.round(centerX - fgW / 2);
      const y1 = Math.round(centerY - fgH / 2);

      // Draw subtle border
      const bWidth = activeClip.background.border_width ?? 4;
      if (bWidth > 0) {
        ctx.save();
        const borderColor = activeClip.background.border_color || [
          255, 255, 255,
        ];
        ctx.strokeStyle = `rgba(${borderColor.join(",")}, 0.95)`;
        ctx.lineWidth = bWidth * 2;
        ctx.strokeRect(x1, y1, fgW, fgH);
        ctx.restore();
      }

      // Draw image crop
      ctx.drawImage(img, bx1, by1, cropW, cropH, x1, y1, fgW, fgH);
    },
    [timeline],
  );

  // 6. Continuous Animation Loop when Playing
  useEffect(() => {
    if (!isPlaying) {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      return;
    }

    let lastTimestamp = performance.now();
    let localTime = currentTimeRef.current;

    const loop = (now: number) => {
      const deltaSec = Math.min(0.1, (now - lastTimestamp) / 1000.0);
      lastTimestamp = now;

      // Follow hardware audio time if available and playing
      const audio = audioRef.current;
      if (audio && !audio.paused && !audio.ended && audio.currentTime > 0) {
        localTime = audio.currentTime;
      } else {
        localTime += deltaSec;
      }

      if (localTime >= timeline.total_duration) {
        const finalTime = timeline.total_duration;
        onTimeUpdate(finalTime);
        renderFrame(finalTime);
        onTogglePlay(); // stop playback at end
        return;
      }

      onTimeUpdate(localTime);
      renderFrame(localTime);
      animationFrameRef.current = requestAnimationFrame(loop);
    };

    animationFrameRef.current = requestAnimationFrame(loop);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [
    isPlaying,
    timeline.total_duration,
    renderFrame,
    onTimeUpdate,
    onTogglePlay,
  ]);

  // 7. Instant WYSIWYG Repaint: whenever motion, background, subtitles, or time change in paused state
  useEffect(() => {
    if (!isPlaying) {
      renderFrame(currentTime);
    }
  }, [timeline, currentTime, isPlaying, imageLoaded, renderFrame]);

  return (
    <div className="relative flex items-center justify-center h-full w-full">
      {/* Hidden audio element for physical sound sync */}
      <audio
        ref={audioRef}
        src={getAudioUrl()}
        preload="auto"
        onEnded={onTogglePlay}
      />

      {/* 9:16 Canvas Viewport */}
      <div className="relative aspect-[9/16] h-full max-h-full rounded-xl overflow-hidden border border-zinc-800/80 shadow-2xl shadow-black/80 bg-black flex items-center justify-center">
        <canvas
          ref={canvasRef}
          width={1080}
          height={1920}
          className="w-full h-full object-contain"
        />
      </div>
    </div>
  );
}
