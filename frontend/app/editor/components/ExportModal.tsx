"use client";

import React, { useState } from "react";
import { TimelineContract, RenderResponse } from "../types";

interface ExportModalProps {
  timeline: TimelineContract;
  isOpen: boolean;
  onClose: () => void;
}

export default function ExportModal({
  timeline,
  isOpen,
  onClose,
}: ExportModalProps) {
  const [isRendering, setIsRendering] = useState(false);
  const [renderResult, setRenderResult] = useState<RenderResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleStartRender = async () => {
    setIsRendering(true);
    setErrorMsg(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/editor/render", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          timeline: timeline,
          output_filename: `render_${timeline.project_id}_p${timeline.page_id}.mp4`,
        }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Server returned status ${res.status}: ${errText}`);
      }

      const data: RenderResponse = await res.json();
      setRenderResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
    } finally {
      setIsRendering(false);
    }
  };

  const getVideoDownloadUrl = (url: string) => {
    if (url.startsWith("http")) return url;
    return `http://127.0.0.1:8000${url.startsWith("/") ? "" : "/"}${url}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-[540px] bg-[#121218] border border-white/20 rounded-2xl p-6 shadow-2xl flex flex-col gap-5 text-white">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🎬</span>
            <h2 className="text-base font-bold">Xuất Video Hoạt Họa 9:16 (Export MP4)</h2>
          </div>
          <button
            onClick={onClose}
            className="text-white/40 hover:text-white text-lg p-1"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        {!renderResult ? (
          <div className="flex flex-col gap-4 text-xs">
            <p className="text-white/70 leading-relaxed">
              Hệ thống sẽ tổng hợp toàn bộ các phân cảnh camera Ken Burns, phông nền mờ Gaussian và track giọng đọc Microsoft Neural thành tệp video MP4 dọc chuẩn phát sóng TikTok / Reels / Shorts.
            </p>

            <div className="bg-white/5 rounded-lg p-3 border border-white/10 grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div>
                <span className="text-white/40 block">Độ phân giải:</span>
                <span className="text-white font-semibold">1080 x 1920 (9:16 Dọc)</span>
              </div>
              <div>
                <span className="text-white/40 block">Tốc độ khung hình:</span>
                <span className="text-white font-semibold">{timeline.fps} FPS</span>
              </div>
              <div>
                <span className="text-white/40 block">Thời lượng:</span>
                <span className="text-white font-semibold">{timeline.total_duration.toFixed(2)}s</span>
              </div>
              <div>
                <span className="text-white/40 block">Bộ mã hóa:</span>
                <span className="text-white font-semibold">H.264 / AAC 128k</span>
              </div>
            </div>

            {errorMsg && (
              <div className="p-3 rounded-lg bg-red-900/40 border border-red-500/50 text-red-200 text-xs">
                ⚠️ Lỗi kết xuất: {errorMsg}
              </div>
            )}

            <button
              onClick={handleStartRender}
              disabled={isRendering}
              className={`w-full py-3 rounded-xl font-bold text-sm transition flex items-center justify-center gap-2 shadow-xl ${
                isRendering
                  ? "bg-white/10 text-white/40 cursor-not-allowed"
                  : "bg-violet-600 hover:bg-violet-500 text-white"
              }`}
            >
              {isRendering ? (
                <>
                  <span className="h-4 w-4 rounded-full border-2 border-white/20 border-t-white animate-spin" />
                  <span>Đang kết xuất video trên server...</span>
                </>
              ) : (
                <>
                  <span>🚀 Bắt đầu Kết xuất MP4</span>
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-4 text-xs">
            <div className="p-3 rounded-lg bg-emerald-900/40 border border-emerald-500/50 text-emerald-200 flex items-center gap-2">
              <span>✅</span>
              <span className="font-semibold">Kết xuất video thành công!</span>
            </div>

            {/* Video Player Preview */}
            <div className="relative aspect-[9/16] max-h-[300px] mx-auto rounded-lg overflow-hidden border border-white/20 bg-black shadow-lg">
              <video
                src={getVideoDownloadUrl(renderResult.video_url)}
                controls
                autoPlay
                className="w-full h-full object-contain"
              />
            </div>

            <div className="bg-white/5 rounded-lg p-3 border border-white/10 grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div>
                <span className="text-white/40 block">Dung lượng file:</span>
                <span className="text-white font-semibold">
                  {(renderResult.file_size_bytes / 1024 / 1024).toFixed(2)} MB
                </span>
              </div>
              <div>
                <span className="text-white/40 block">Độ lệch A/V:</span>
                <span className="text-emerald-400 font-semibold">
                  {renderResult.audio_drift_sec.toFixed(4)}s (Chuẩn)
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3 mt-2">
              <a
                href={getVideoDownloadUrl(renderResult.video_url)}
                download
                className="flex-1 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold text-center transition shadow-lg"
              >
                ⬇️ Tải Video MP4 về máy
              </a>
              <button
                onClick={onClose}
                className="px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white transition"
              >
                Đóng
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

