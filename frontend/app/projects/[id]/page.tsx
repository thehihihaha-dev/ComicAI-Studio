"use client";

import React, { use, useEffect, useState, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import VideoPreview from "@/app/editor/components/VideoPreview";
import Inspector from "@/app/editor/components/Inspector";
import Timeline from "@/app/editor/components/Timeline";
import ExportModal from "@/app/editor/components/ExportModal";
import { TimelineContract } from "@/app/editor/types";

interface PageItem {
  id: string;
  page_order: number;
  filename: string;
  file_path: string;
  url: string;
  duration_label: string;
  status: "completed" | "processing" | "ready";
}

interface ProjectInfo {
  id: string;
  name: string;
  content_type: string;
  status?: string;
}

const DEFAULT_BENCHMARK_PROJECT_ID = "92961605-5553-4df1-b74e-9a3bed5e14f5";

const DEFAULT_BENCHMARK_PAGES: PageItem[] = [
  {
    id: "p01",
    page_order: 1,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-2.jpg",
    file_path:
      "uploads/92961605-5553-4df1-b74e-9a3bed5e14f5_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-2.jpg",
    url: "http://127.0.0.1:8000/uploads/92961605-5553-4df1-b74e-9a3bed5e14f5_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-2.jpg",
    duration_label: "10.63s",
    status: "completed",
  },
  {
    id: "p02",
    page_order: 2,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-4.jpg",
    file_path:
      "uploads/33c28b2d-f096-4025-b6b7-7a3c8c7ba1df_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-4.jpg",
    url: "http://127.0.0.1:8000/uploads/33c28b2d-f096-4025-b6b7-7a3c8c7ba1df_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-4.jpg",
    duration_label: "12.40s",
    status: "completed",
  },
  {
    id: "p03",
    page_order: 3,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-5.jpg",
    file_path:
      "uploads/ab627e40-5851-4a6e-9e7a-03d3968087cb_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-5.jpg",
    url: "http://127.0.0.1:8000/uploads/ab627e40-5851-4a6e-9e7a-03d3968087cb_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-5.jpg",
    duration_label: "14.80s",
    status: "completed",
  },
  {
    id: "p04",
    page_order: 4,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-6.jpg",
    file_path:
      "uploads/dab0676a-07e3-4195-b20c-511f57e3ddc6_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-6.jpg",
    url: "http://127.0.0.1:8000/uploads/dab0676a-07e3-4195-b20c-511f57e3ddc6_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-6.jpg",
    duration_label: "11.20s",
    status: "completed",
  },
  {
    id: "p05",
    page_order: 5,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-7.jpg",
    file_path:
      "uploads/69f9acdd-e51f-4be2-90dd-cbc7e5882aa7_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-7.jpg",
    url: "http://127.0.0.1:8000/uploads/69f9acdd-e51f-4be2-90dd-cbc7e5882aa7_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-7.jpg",
    duration_label: "25.99s",
    status: "completed",
  },
  {
    id: "p06",
    page_order: 6,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-8.jpg",
    file_path:
      "uploads/7d88f531-5f78-41ce-a7b3-a07bacbfc2ed_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-8.jpg",
    url: "http://127.0.0.1:8000/uploads/7d88f531-5f78-41ce-a7b3-a07bacbfc2ed_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-8.jpg",
    duration_label: "13.50s",
    status: "completed",
  },
  {
    id: "p07",
    page_order: 7,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-10.jpg",
    file_path:
      "uploads/a3c72490-a7b2-402a-88c9-8cc874cab45f_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-10.jpg",
    url: "http://127.0.0.1:8000/uploads/a3c72490-a7b2-402a-88c9-8cc874cab45f_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-10.jpg",
    duration_label: "15.10s",
    status: "completed",
  },
  {
    id: "p08",
    page_order: 8,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-11.jpg",
    file_path:
      "uploads/e5748324-096a-4ad0-b341-cf373fdfc0f8_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-11.jpg",
    url: "http://127.0.0.1:8000/uploads/e5748324-096a-4ad0-b341-cf373fdfc0f8_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-11.jpg",
    duration_label: "12.80s",
    status: "completed",
  },
  {
    id: "p09",
    page_order: 9,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-12.jpg",
    file_path:
      "uploads/67027536-7450-4e7d-a5c1-5647a98f1f98_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-12.jpg",
    url: "http://127.0.0.1:8000/uploads/67027536-7450-4e7d-a5c1-5647a98f1f98_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-12.jpg",
    duration_label: "14.00s",
    status: "completed",
  },
  {
    id: "p10",
    page_order: 10,
    filename: "vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-13.jpg",
    file_path:
      "uploads/df112711-adb2-46ff-b083-e425160778c8_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-13.jpg",
    url: "http://127.0.0.1:8000/uploads/df112711-adb2-46ff-b083-e425160778c8_vo-trong-game-cua-toi-la-idol-noi-tieng-ngoai-doi-13.jpg",
    duration_label: "16.50s",
    status: "completed",
  },
];

function createSyntheticContract(
  pageOrder: number,
  projectId: string,
  imagePath: string,
): TimelineContract {
  const fallbackDuration = pageOrder === 5 ? 25.99 : 12.0;
  return {
    version: "day18_timeline_contract.v1",
    project_id: projectId,
    page_id: pageOrder,
    source_image_path: imagePath,
    image_dimensions: [900, 1280],
    canvas_size: [1080, 1920],
    fps: 30.0,
    total_duration: fallbackDuration,
    metadata: {},
    visual_clips: [
      {
        clip_id: `CLIP_P${String(pageOrder).padStart(2, "0")}_01`,
        panel_id: `PANEL_P${String(pageOrder).padStart(2, "0")}_01`,
        bbox: [100, 100, 800, 600],
        shot_type: "wide",
        start_time: 0.0,
        end_time: fallbackDuration / 2,
        duration: fallbackDuration / 2,
        motion: {
          zoom_start: 1.0,
          zoom_end: 1.06,
          pan_start: [0, 0],
          pan_end: [0, 0],
          easing: "smoothstep",
        },
        background: {
          blur_radius: 51,
          darkness: 0.45,
          border_width: 4,
          border_color: [255, 255, 255],
        },
      },
      {
        clip_id: `CLIP_P${String(pageOrder).padStart(2, "0")}_02`,
        panel_id: `PANEL_P${String(pageOrder).padStart(2, "0")}_02`,
        bbox: [50, 500, 850, 1100],
        shot_type: "medium",
        start_time: fallbackDuration / 2,
        end_time: fallbackDuration,
        duration: fallbackDuration / 2,
        motion: {
          zoom_start: 1.02,
          zoom_end: 1.08,
          pan_start: [0, 0],
          pan_end: [0, -10],
          easing: "smoothstep",
        },
        background: {
          blur_radius: 51,
          darkness: 0.45,
          border_width: 4,
          border_color: [255, 255, 255],
        },
      },
    ],
    audio_clips: [
      {
        clip_id: `D_P${String(pageOrder).padStart(2, "0")}_01`,
        dialogue_id: `D_P${String(pageOrder).padStart(2, "0")}_01`,
        speaker_label: "RIN",
        voice_id: "vi-VN-HoaiMyNeural",
        text: `Lời thoại phân cảnh 1 của trang ${pageOrder}`,
        start_time: 0.2,
        end_time: fallbackDuration / 2 - 0.3,
        duration: fallbackDuration / 2 - 0.5,
        file_path: `artifacts/audio/day17/raw/D_P${String(pageOrder).padStart(2, "0")}_01.mp3`,
      },
      {
        clip_id: `D_P${String(pageOrder).padStart(2, "0")}_02`,
        dialogue_id: `D_P${String(pageOrder).padStart(2, "0")}_02`,
        speaker_label: "KAZU",
        voice_id: "vi-VN-NamMinhNeural",
        text: `Lời thoại phân cảnh 2 của trang ${pageOrder}`,
        start_time: fallbackDuration / 2 + 0.2,
        end_time: fallbackDuration - 0.3,
        duration: fallbackDuration / 2 - 0.5,
        file_path: `artifacts/audio/day17/raw/D_P${String(pageOrder).padStart(2, "0")}_02.mp3`,
      },
    ],
  };
}

export default function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const projectId = id || DEFAULT_BENCHMARK_PROJECT_ID;

  const [projectInfo, setProjectInfo] = useState<ProjectInfo>({
    id: projectId,
    name: "Vợ trong game của tôi là Idol nổi tiếng ngoài đời",
    content_type: "short",
    status: "ready",
  });
  const [pages, setPages] = useState<PageItem[]>(DEFAULT_BENCHMARK_PAGES);
  const [selectedPageOrder, setSelectedPageOrder] = useState<number>(1);
  const [timeline, setTimeline] = useState<TimelineContract | null>(null);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [pageLoading, setPageLoading] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const cachedContractsRef = useRef<Record<number, TimelineContract>>({});

  // 1. Fetch Project Metadata
  useEffect(() => {
    async function loadProjectInfo() {
      try {
        const res = await fetch(`http://127.0.0.1:8000/projects/${projectId}`, {
          cache: "no-store",
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.name) {
            setProjectInfo({
              id: data.id || projectId,
              name: data.name,
              content_type: data.content_type || "short",
              status: data.status || "ready",
            });
          }
        }
      } catch (err) {
        console.warn("Could not fetch project info, using fallback:", err);
      }
    }
    void loadProjectInfo();
  }, [projectId]);

  // 2. Fetch Project Assets
  useEffect(() => {
    async function loadAssets() {
      try {
        const res = await fetch(
          `http://127.0.0.1:8000/assets/project/${projectId}?page=1&limit=50`,
          { cache: "no-store" },
        );
        if (res.ok) {
          const data = await res.json();
          if (data.items && data.items.length > 0) {
            interface BackendAssetItem {
              id?: string;
              page_order?: number;
              filename: string;
              file_path: string;
              url: string;
            }
            const mapped: PageItem[] = data.items.map(
              (item: BackendAssetItem, idx: number) => ({
                id: item.id || `p${idx + 1}`,
                page_order: item.page_order || idx + 1,
                filename: item.filename,
                file_path: item.file_path,
                url: item.url,
                duration_label:
                  item.page_order === 1
                    ? "10.63s"
                    : item.page_order === 5
                      ? "25.99s"
                      : `${(10 + ((item.page_order || 1) % 5) * 2.5).toFixed(2)}s`,
                status: "completed",
              }),
            );
            setPages(mapped);
          } else if (projectId === DEFAULT_BENCHMARK_PROJECT_ID) {
            setPages(DEFAULT_BENCHMARK_PAGES);
          }
        }
      } catch (err) {
        console.warn(
          "Backend assets fetch failed, using default benchmark assets:",
          err,
        );
        if (projectId === DEFAULT_BENCHMARK_PROJECT_ID) {
          setPages(DEFAULT_BENCHMARK_PAGES);
        }
      }
    }
    void loadAssets();
  }, [projectId]);

  // 3. Preload Initial Timeline Contract
  useEffect(() => {
    async function loadInitialPage() {
      try {
        if (projectId === DEFAULT_BENCHMARK_PROJECT_ID) {
          const res = await fetch("/timeline_contract_page_01.json");
          if (res.ok) {
            const data: TimelineContract = await res.json();
            cachedContractsRef.current[1] = data;
            setTimeline(data);
            if (data.visual_clips.length > 0) {
              setSelectedClipId(data.visual_clips[0].clip_id);
            }
            return;
          }
        }

        // Fetch draft from backend API
        const targetPage = pages[0];
        const res = await fetch("http://127.0.0.1:8000/api/v1/editor/draft", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            image_path: targetPage?.file_path || "uploads/page_1.jpg",
            project_id: projectId,
            page_order: 1,
          }),
        });

        if (res.ok) {
          const data: TimelineContract = await res.json();
          cachedContractsRef.current[1] = data;
          setTimeline(data);
          if (data.visual_clips.length > 0) {
            setSelectedClipId(data.visual_clips[0].clip_id);
          }
        } else {
          const fallback = createSyntheticContract(
            1,
            projectId,
            targetPage?.file_path || "page_01.jpg",
          );
          cachedContractsRef.current[1] = fallback;
          setTimeline(fallback);
          if (fallback.visual_clips.length > 0) {
            setSelectedClipId(fallback.visual_clips[0].clip_id);
          }
        }
      } catch (err) {
        console.warn("Initial timeline load fallback:", err);
        const fallback = createSyntheticContract(
          1,
          projectId,
          pages[0]?.file_path || "page_01.jpg",
        );
        cachedContractsRef.current[1] = fallback;
        setTimeline(fallback);
        if (fallback.visual_clips.length > 0) {
          setSelectedClipId(fallback.visual_clips[0].clip_id);
        }
      }
    }
    void loadInitialPage();
  }, [projectId, pages]);

  // 4. Switch active page
  const handleSelectPage = async (pageOrder: number) => {
    if (pageOrder === selectedPageOrder && timeline) return;

    setSelectedPageOrder(pageOrder);
    setCurrentTime(0);
    setIsPlaying(false);

    if (cachedContractsRef.current[pageOrder]) {
      const cached = cachedContractsRef.current[pageOrder];
      setTimeline(cached);
      if (cached.visual_clips.length > 0) {
        setSelectedClipId(cached.visual_clips[0].clip_id);
      }
      return;
    }

    setPageLoading(true);
    const targetPage = pages.find((p) => p.page_order === pageOrder);

    try {
      if (pageOrder === 1 && projectId === DEFAULT_BENCHMARK_PROJECT_ID) {
        const res = await fetch("/timeline_contract_page_01.json");
        if (res.ok) {
          const data: TimelineContract = await res.json();
          cachedContractsRef.current[1] = data;
          setTimeline(data);
          if (data.visual_clips.length > 0) {
            setSelectedClipId(data.visual_clips[0].clip_id);
          }
          return;
        }
      }

      // Request draft generation from backend API
      const res = await fetch("http://127.0.0.1:8000/api/v1/editor/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_path: targetPage?.file_path || `uploads/page_${pageOrder}.jpg`,
          project_id: projectId,
          page_order: pageOrder,
        }),
      });

      if (res.ok) {
        const data: TimelineContract = await res.json();
        cachedContractsRef.current[pageOrder] = data;
        setTimeline(data);
        if (data.visual_clips.length > 0) {
          setSelectedClipId(data.visual_clips[0].clip_id);
        }
      } else {
        throw new Error(`Draft API responded with ${res.status}`);
      }
    } catch (err) {
      console.warn(
        `Falling back to synthesized contract for page ${pageOrder}:`,
        err,
      );
      const syntheticContract = createSyntheticContract(
        pageOrder,
        projectId,
        targetPage?.file_path || "page_01.jpg",
      );
      cachedContractsRef.current[pageOrder] = syntheticContract;
      setTimeline(syntheticContract);
      if (syntheticContract.visual_clips.length > 0) {
        setSelectedClipId(syntheticContract.visual_clips[0].clip_id);
      }
    } finally {
      setPageLoading(false);
    }
  };

  // 5. Ingest new comic page image via upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setIsPlaying(false);

    try {
      const newPageOrder = pages.length + 1;
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_id", projectId);
      formData.append("page_order", String(newPageOrder));

      const res = await fetch("http://127.0.0.1:8000/api/v1/editor/draft", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Draft generation failed with status: ${res.status}`);
      }

      const newTimeline: TimelineContract = await res.json();
      const newPageItem: PageItem = {
        id: `p${newPageOrder}`,
        page_order: newPageOrder,
        filename: file.name,
        file_path: newTimeline.source_image_path,
        url: `http://127.0.0.1:8000/${newTimeline.source_image_path}`,
        duration_label: `${newTimeline.total_duration.toFixed(2)}s`,
        status: "completed",
      };

      setPages((prev) => [...prev, newPageItem]);
      cachedContractsRef.current[newPageOrder] = newTimeline;
      setSelectedPageOrder(newPageOrder);
      setTimeline(newTimeline);
      setCurrentTime(0);
      if (newTimeline.visual_clips.length > 0) {
        setSelectedClipId(newTimeline.visual_clips[0].clip_id);
      }
    } catch (err) {
      console.error("Upload failed:", err);
      alert(
        "Nạp ảnh mới thất bại. Vui lòng kiểm tra backend server đang chạy tại port 8000.",
      );
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  // Helper: Format seconds to MM:SS
  const formatTimecode = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  // Auto-sync selected clip with current playback time for WYSIWYG Inspector sync
  useEffect(() => {
    if (!timeline || timeline.visual_clips.length === 0) return;
    const clipAtTime = timeline.visual_clips.find(
      (c) => currentTime >= c.start_time && currentTime < c.end_time,
    );
    if (clipAtTime && clipAtTime.clip_id !== selectedClipId) {
      requestAnimationFrame(() => {
        setSelectedClipId(clipAtTime.clip_id);
      });
    }
  }, [currentTime, timeline, selectedClipId]);

  if (!timeline) {
    return (
      <div className="min-h-screen bg-[#09090c] text-white flex flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
        <p className="text-xs text-white/60 font-mono">
          Đang khởi tạo Studio Workspace...
        </p>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-[#0a0a0e] text-white flex flex-col h-screen overflow-hidden select-none">
      {/* 1. Header trên cùng: Tinh giản, bỏ badge WORKSPACE, giữ duy nhất nút tím Xuất Video */}
      <header className="h-13 shrink-0 px-4 border-b border-white/10 flex items-center justify-between bg-[#0e0e13]">
        <div className="flex items-center gap-3">
          {/* Nút quay về Dashboard */}
          <Link
            href="/"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/70 hover:text-white transition text-xs font-medium border border-white/10"
            title="Về Home"
          >
            <span>←</span>
            <span>Home</span>
          </Link>

          <div>
            <span className="text-sm font-bold tracking-tight bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
              ComicAI Studio
            </span>
            <p className="text-[11px] text-white/40 truncate max-w-[240px] leading-tight">
              {projectInfo.name}
            </p>
          </div>
        </div>

        {/* Center Page Indicator Pill */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-medium text-white/80">
            Trang {String(selectedPageOrder).padStart(2, "0")} /{" "}
            {String(pages.length).padStart(2, "0")}
          </span>
          <span className="text-white/30">·</span>
          <span className="font-mono text-white/60">
            {timeline.total_duration.toFixed(2)}s
          </span>
        </div>

        {/* Action Controls: Ẩn input file, giữ DUY NHẤT nút tím Xuất Video */}
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileUpload}
            className="hidden"
          />

          <button
            type="button"
            onClick={() => setIsExportOpen(true)}
            className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 text-xs font-bold text-white shadow-lg shadow-violet-500/20 transition flex items-center gap-1.5 cursor-pointer"
          >
            <span>🪄</span>
            <span>Xuất Video (Render MP4)</span>
          </button>
        </div>
      </header>

      {/* 2. Cấu trúc Layout 2 khối chính (Cột trái độc lập h-full, Cột phải chia 2 tầng) */}
      <div className="flex-1 min-h-0 flex flex-row overflow-hidden">
        {/* KHỐI CỘT TRÁI (Sidebar Trang truyện h-full độc lập, không bị timeline cắt ngang) */}
        <aside className="w-56 shrink-0 border-r border-white/[0.08] bg-[#0f0f12] flex flex-col h-full overflow-hidden">
          {/* Tiêu đề cột trái: Bố trí nút [+ Thêm truyện] nhỏ gọn ngay cạnh chữ Trang truyện */}
          <div className="h-11 shrink-0 px-3.5 border-b border-white/[0.08] flex items-center justify-between bg-[#111116]">
            <div className="flex items-center gap-1.5">
              <h2 className="text-xs font-semibold text-white/90">
                Trang truyện
              </h2>
              <span className="text-[10px] text-white/30 font-mono">
                ({pages.length})
              </span>
            </div>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="px-2 py-0.5 rounded-md bg-violet-600/20 hover:bg-violet-600/35 border border-violet-500/40 text-[11px] font-medium text-violet-300 hover:text-violet-200 transition flex items-center gap-1 cursor-pointer"
              title="Thêm trang truyện mới"
            >
              <span>+</span>
              <span>Thêm truyện</span>
            </button>
          </div>

          {/* Lưới 2 cột thumbnail gọn gàng */}
          <div className="flex-1 overflow-y-auto p-3 overscroll-contain [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-width:thin]">
            <div className="grid grid-cols-2 gap-2.5">
              {pages.map((p) => {
                const isSelected = p.page_order === selectedPageOrder;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleSelectPage(p.page_order)}
                    className={`group relative aspect-[3/4] w-full rounded-lg overflow-hidden border bg-[#151518] transition text-left cursor-pointer ${
                      isSelected
                        ? "border-violet-500 ring-2 ring-violet-500/30 shadow-lg shadow-violet-950/40"
                        : "border-white/[0.08] hover:border-white/25"
                    }`}
                  >
                    <div className="relative h-full w-full bg-[#0b0b0d]">
                      <Image
                        src={p.page_order === 1 ? "/page_01.jpg" : p.url}
                        alt={p.filename}
                        fill
                        unoptimized
                        sizes="120px"
                        className="object-contain"
                      />
                      {pageLoading && isSelected && (
                        <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                          <div className="h-4 w-4 rounded-full border-2 border-violet-400 border-t-transparent animate-spin" />
                        </div>
                      )}
                    </div>

                    <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/90 via-black/50 to-transparent px-2 pb-1 pt-4">
                      <span className="text-[11px] font-medium text-white/90 font-mono">
                        {String(p.page_order).padStart(2, "0")}
                      </span>
                      <span className="text-[11px] text-emerald-400">✓</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        {/* KHỐI BÊN PHẢI (Chia làm 2 tầng: Tầng Trên & Tầng Dưới) */}
        <section className="flex-1 min-w-0 flex flex-col h-full overflow-hidden bg-[#08080a]">
          {/* TẦNG TRÊN (Canvas Player bên trái + Bảng Inspector 3 tab bên phải) */}
          <div className="flex-1 min-h-0 flex flex-row overflow-hidden border-b border-white/[0.08]">
            {/* Bên trái: Khung Canvas Player 9:16 thu nhỏ vừa mắt kèm thanh phát tối giản */}
            <div className="flex-1 min-w-0 flex flex-col items-center justify-between p-2.5 sm:p-3 overflow-hidden bg-[#070709]">
              <div className="flex-1 min-h-0 w-full max-w-[400px] flex items-center justify-center overflow-hidden">
                <VideoPreview
                  timeline={timeline}
                  currentTime={currentTime}
                  isPlaying={isPlaying}
                  onTimeUpdate={(t) => setCurrentTime(t)}
                  onTogglePlay={() => setIsPlaying(!isPlaying)}
                  selectedClipId={selectedClipId}
                />
              </div>

              {/* Thanh phát tối giản ngay dưới khung tranh */}
              <div className="w-full max-w-[420px] flex h-8 shrink-0 items-center gap-2.5 rounded-lg border border-white/[0.08] bg-[#0e0e12] px-3 text-white/50 mt-1.5">
                <button
                  type="button"
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="flex h-6 w-6 items-center justify-center rounded border border-white/10 hover:bg-white/10 text-white transition text-xs cursor-pointer"
                  aria-label={isPlaying ? "Tạm dừng" : "Phát"}
                >
                  {isPlaying ? "⏸" : "▶"}
                </button>

                <div className="relative flex-1 flex items-center">
                  <input
                    type="range"
                    min="0"
                    max={timeline.total_duration || 1}
                    step="0.01"
                    value={currentTime}
                    onChange={(e) => setCurrentTime(parseFloat(e.target.value))}
                    className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                  />
                </div>

                <span className="font-mono text-[11px] text-white/60">
                  {formatTimecode(currentTime)}
                </span>
              </div>
            </div>

            {/* Bên phải: Bảng Inspector gồm 3 tab (Thoại Manga, Kịch bản AI, Hiệu ứng) */}
            <aside className="w-[380px] shrink-0 border-l border-white/[0.08] bg-[#101013] flex flex-col overflow-hidden">
              <Inspector
                timeline={timeline}
                selectedClipId={selectedClipId}
                currentTime={currentTime}
                projectId={projectId}
                onUpdateTimeline={(updated) => setTimeline(updated)}
                onSeek={(t) => setCurrentTime(t)}
                onSelectClip={(id) => setSelectedClipId(id)}
              />
            </aside>
          </div>

          {/* TẦNG DƯỚI (Bàn dựng âm thanh kiểu CapCut gấp đôi chiều cao tràn ngang toàn bộ khối bên phải) */}
          <div className="h-[280px] lg:h-[300px] shrink-0 bg-[#0a0a0d] flex flex-col overflow-hidden">
            <Timeline
              timeline={timeline}
              currentTime={currentTime}
              onSeek={(t) => setCurrentTime(t)}
              selectedClipId={selectedClipId}
              onSelectClip={(id) => setSelectedClipId(id)}
            />
          </div>
        </section>
      </div>

      {/* Video Export Modal */}
      <ExportModal
        timeline={timeline}
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
      />
    </main>
  );
}
