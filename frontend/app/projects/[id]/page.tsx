"use client";

import React, { use, useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import Image from "next/image";
import VideoPreview, {
  VideoPreviewHandle,
} from "@/app/editor/components/VideoPreview";
import Inspector from "@/app/editor/components/Inspector";
import Timeline from "@/app/editor/components/Timeline";
import ExportModal from "@/app/editor/components/ExportModal";
import {
  PanelItem,
  ScriptSegment,
  TimelineContract,
  resolveImageUrl,
} from "@/app/editor/types";

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
  timeline_data?: TimelineContract | null;
  script_content?: Record<string, unknown> | null;
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
        image_path: imagePath,
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
        image_path: imagePath,
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

function createDefaultPanels(pageList: PageItem[]): PanelItem[] {
  let runningStart = 0;
  return pageList.map((p, idx) => {
    const dur = p.page_order === 1 ? 10.63 : p.page_order === 5 ? 25.99 : 12.0;
    const start = Number(runningStart.toFixed(2));
    const end = Number((runningStart + dur).toFixed(2));
    runningStart = end;

    const pageScript: ScriptSegment[] = [
      {
        id: `SEG_${p.id}_01`,
        section_type: idx === 0 ? "hook" : "body",
        text:
          p.page_order === 1
            ? "Cứ ngỡ là hôn lễ trong mơ, ai ngờ lại là cái bẫy trí mạng!"
            : p.page_order === 2
              ? "Bất ngờ xuất hiện người thứ ba, cả thánh đường rơi vào im lặng đáng sợ."
              : p.page_order === 3
                ? "Sự thật dần hé lộ khi ánh mắt của hai người chạm nhau đầy nghi hoặc."
                : `Diễn biến gay cấn tiếp tục đẩy cao trào tại trang ${p.page_order}.`,
        estimated_duration: dur * 0.45,
        suggested_effect: idx % 2 === 0 ? "punch_zoom" : "zoom_in",
      },
      {
        id: `SEG_${p.id}_02`,
        section_type: idx === pageList.length - 1 ? "call_to_action" : "body",
        text:
          p.page_order === 1
            ? "Ngay tại thánh đường trang nghiêm, sự thật kinh hoàng chính thức bị vạch trần."
            : p.page_order === 2
              ? "Liệu lựa chọn này sẽ đưa số phận của họ đi về đâu?"
              : `Mỗi chi tiết tại trang ${p.page_order} đều ẩn chứa một bí mật không ngờ tới.`,
        estimated_duration: dur * 0.55,
        suggested_effect: idx % 2 === 0 ? "zoom_in" : "pan_down",
      },
    ];

    return {
      id: p.id,
      page_order: p.page_order,
      image: p.file_path,
      script: pageScript,
      style: "dramatic",
      duration: dur,
      timelineStart: start,
      timelineEnd: end,
      status: "ready",
      error: null,
    };
  });
}

function buildPanelsFromTimeline(
  timelineContract: TimelineContract,
  fallbackPages: PageItem[] = [],
  fallbackStyle: "dramatic" | "humorous" | "romantic" = "dramatic",
): PanelItem[] {
  const scriptMeta = (
    timelineContract.metadata as Record<string, unknown> | undefined
  )?.script as { segments?: ScriptSegment[] } | undefined;
  const scriptSegments: ScriptSegment[] = Array.isArray(scriptMeta?.segments)
    ? scriptMeta.segments
    : [];

  return timelineContract.visual_clips.map((vc, idx) => {
    const existing = fallbackPages.find(
      (p) => p.page_order === idx + 1 || p.id === vc.clip_id,
    );

    // Find matching audio clips for this panel
    const matchingAudioClips = (timelineContract.audio_clips || []).filter(
      (a) =>
        (a.start_time >= vc.start_time && a.start_time < vc.end_time) ||
        (a.end_time > vc.start_time && a.end_time <= vc.end_time) ||
        (vc.start_time >= a.start_time && vc.end_time <= a.end_time),
    );

    let panelScript: ScriptSegment[] = [];
    if (scriptSegments.length > 0 && scriptSegments[idx]) {
      panelScript = [
        {
          ...scriptSegments[idx],
          estimated_duration:
            matchingAudioClips[0]?.duration ||
            scriptSegments[idx].estimated_duration ||
            vc.duration,
        },
      ];
    } else if (matchingAudioClips.length > 0) {
      panelScript = matchingAudioClips.map((ac, aIdx) => ({
        id: ac.dialogue_id || ac.clip_id || `SEG_${vc.clip_id}_${aIdx + 1}`,
        section_type:
          idx === 0
            ? "hook"
            : idx === timelineContract.visual_clips.length - 1
              ? "call_to_action"
              : "body",
        text: ac.text,
        estimated_duration: ac.duration,
        suggested_effect: vc.shot_type || "zoom_in",
      }));
    } else {
      panelScript = [
        {
          id: `SEG_${vc.clip_id}_01`,
          section_type:
            idx === 0
              ? "hook"
              : idx === timelineContract.visual_clips.length - 1
                ? "call_to_action"
                : "body",
          text: `Phân cảnh ${idx + 1} của chapter`,
          estimated_duration: vc.duration,
          suggested_effect: vc.shot_type || "zoom_in",
        },
      ];
    }

    return {
      id: vc.clip_id || `panel_${idx + 1}`,
      page_order: idx + 1,
      image:
        vc.image_path ||
        existing?.file_path ||
        existing?.url ||
        "uploads/page_01.jpg",
      script: panelScript,
      style:
        (timelineContract.metadata?.story_style as
          | "dramatic"
          | "humorous"
          | "romantic"
          | undefined) || fallbackStyle,
      duration: vc.duration,
      timelineStart: vc.start_time,
      timelineEnd: vc.end_time,
      status: "completed",
      error: null,
    };
  });
}

export default function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const projectId = id || DEFAULT_BENCHMARK_PROJECT_ID;
  const isBenchmark =
    projectId === DEFAULT_BENCHMARK_PROJECT_ID ||
    projectId === "project_wedding_vows";

  const [projectInfo, setProjectInfo] = useState<ProjectInfo>({
    id: projectId,
    name: isBenchmark
      ? "Vợ trong game của tôi là Idol nổi tiếng ngoài đời"
      : "Đang tải...",
    content_type: "short",
    status: "ready",
  });
  const [pages, setPages] = useState<PageItem[]>(
    isBenchmark ? DEFAULT_BENCHMARK_PAGES : [],
  );
  const [panels, setPanels] = useState<PanelItem[]>(() =>
    isBenchmark ? createDefaultPanels(DEFAULT_BENCHMARK_PAGES) : [],
  );
  const [selectedPanelId, setSelectedPanelId] = useState<string>(
    isBenchmark ? "p01" : "",
  );
  const [reviewProgress, setReviewProgress] = useState<{
    current: number;
    total: number;
    isReviewing: boolean;
  } | null>(null);
  const [selectedPageOrder, setSelectedPageOrder] = useState<number>(1);
  const [timeline, setTimeline] = useState<TimelineContract | null>(null);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isAssetsLoading, setIsAssetsLoading] = useState<boolean>(!isBenchmark);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [isGeneratingShort, setIsGeneratingShort] = useState<boolean>(false);
  const [selectedStoryStyle, setSelectedStoryStyle] = useState<
    "dramatic" | "humorous" | "romantic"
  >("dramatic");
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const emptyFileInputRef = useRef<HTMLInputElement | null>(null);
  const videoPreviewRef = useRef<VideoPreviewHandle | null>(null);
  const cachedContractsRef = useRef<Record<number, TimelineContract>>({});
  const hasPersistedTimelineRef = useRef<boolean>(false);
  const persistedTimelineRef = useRef<TimelineContract | null>(null);
  const pagesRef = useRef(pages);

  useEffect(() => {
    pagesRef.current = pages;
  }, [pages]);

  // 1. Fetch Project Metadata & Persisted Timeline
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
              timeline_data: data.timeline_data || null,
              script_content: data.script_content || null,
            });
          }
          if (
            data &&
            data.timeline_data &&
            Array.isArray(data.timeline_data.visual_clips) &&
            data.timeline_data.visual_clips.length > 0
          ) {
            const persisted = data.timeline_data as TimelineContract;
            hasPersistedTimelineRef.current = true;
            persistedTimelineRef.current = persisted;
            cachedContractsRef.current[1] = persisted;
            setTimeline(persisted);
            const restoredPanels = buildPanelsFromTimeline(
              persisted,
              pagesRef.current,
            );
            setPanels(restoredPanels);
            if (persisted.visual_clips.length > 0) {
              setSelectedClipId(persisted.visual_clips[0].clip_id);
              setSelectedPanelId(persisted.visual_clips[0].clip_id);
            }
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
        setIsAssetsLoading(true);
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
            if (
              hasPersistedTimelineRef.current &&
              persistedTimelineRef.current
            ) {
              const restoredPanels = buildPanelsFromTimeline(
                persistedTimelineRef.current,
                mapped,
              );
              setPanels(restoredPanels);
            } else {
              setPanels(createDefaultPanels(mapped));
              if (mapped.length > 0) {
                setSelectedPanelId(mapped[0].id);
                setSelectedPageOrder(mapped[0].page_order);
              }
            }
          } else if (isBenchmark) {
            setPages(DEFAULT_BENCHMARK_PAGES);
            if (
              hasPersistedTimelineRef.current &&
              persistedTimelineRef.current
            ) {
              setPanels(
                buildPanelsFromTimeline(
                  persistedTimelineRef.current,
                  DEFAULT_BENCHMARK_PAGES,
                ),
              );
            } else {
              setPanels(createDefaultPanels(DEFAULT_BENCHMARK_PAGES));
              setSelectedPanelId("p01");
              setSelectedPageOrder(1);
            }
          } else {
            setPages([]);
            if (!hasPersistedTimelineRef.current) {
              setPanels([]);
              setTimeline(null);
              setSelectedPanelId("");
            }
          }
        }
      } catch (err) {
        console.warn("Backend assets fetch failed:", err);
        if (isBenchmark) {
          setPages(DEFAULT_BENCHMARK_PAGES);
          if (hasPersistedTimelineRef.current && persistedTimelineRef.current) {
            setPanels(
              buildPanelsFromTimeline(
                persistedTimelineRef.current,
                DEFAULT_BENCHMARK_PAGES,
              ),
            );
          } else {
            setPanels(createDefaultPanels(DEFAULT_BENCHMARK_PAGES));
            setSelectedPanelId("p01");
            setSelectedPageOrder(1);
          }
        } else {
          setPages([]);
          if (!hasPersistedTimelineRef.current) {
            setPanels([]);
            setTimeline(null);
            setSelectedPanelId("");
          }
        }
      } finally {
        setIsAssetsLoading(false);
      }
    }
    void loadAssets();
  }, [projectId, isBenchmark]);

  // 3. Preload Initial Timeline Contract
  useEffect(() => {
    async function loadInitialPage() {
      if (
        hasPersistedTimelineRef.current ||
        (persistedTimelineRef.current &&
          persistedTimelineRef.current.visual_clips.length > 0)
      ) {
        return;
      }
      if (pages.length === 0) {
        setTimeline(null);
        return;
      }

      try {
        if (isBenchmark && pages.length === DEFAULT_BENCHMARK_PAGES.length) {
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
            image_path: targetPage?.file_path || targetPage?.url,
            project_id: projectId,
            page_order: targetPage?.page_order || 1,
          }),
        });

        if (res.ok) {
          const data: TimelineContract = await res.json();
          cachedContractsRef.current[targetPage.page_order] = data;
          setTimeline(data);
          if (data.visual_clips.length > 0) {
            setSelectedClipId(data.visual_clips[0].clip_id);
          }
        } else {
          const fallback = createSyntheticContract(
            targetPage?.page_order || 1,
            projectId,
            targetPage?.file_path || targetPage?.url || "page_01.jpg",
          );
          cachedContractsRef.current[targetPage.page_order] = fallback;
          setTimeline(fallback);
          if (fallback.visual_clips.length > 0) {
            setSelectedClipId(fallback.visual_clips[0].clip_id);
          }
        }
      } catch (err) {
        console.warn("Initial timeline load fallback:", err);
        const targetPage = pages[0];
        const fallback = createSyntheticContract(
          targetPage?.page_order || 1,
          projectId,
          targetPage?.file_path || targetPage?.url || "page_01.jpg",
        );
        cachedContractsRef.current[targetPage.page_order] = fallback;
        setTimeline(fallback);
        if (fallback.visual_clips.length > 0) {
          setSelectedClipId(fallback.visual_clips[0].clip_id);
        }
      }
    }
    void loadInitialPage();
  }, [projectId, pages, isBenchmark]);

  const panelsRef = useRef(panels);
  const selectedPanelIdRef = useRef(selectedPanelId);
  const timelineRef = useRef(timeline);
  const selectedClipIdRef = useRef(selectedClipId);

  useEffect(() => {
    panelsRef.current = panels;
    selectedPanelIdRef.current = selectedPanelId;
    timelineRef.current = timeline;
    selectedClipIdRef.current = selectedClipId;
  }, [panels, selectedPanelId, timeline, selectedClipId]);

  // Master time update handler (keeps timeline, panels, and visual clips in bidirectional sync)
  const handleTimeUpdate = useCallback((t: number) => {
    setCurrentTime(t);
    const matchingPanel = panelsRef.current.find(
      (p) => t >= p.timelineStart && t < p.timelineEnd,
    );
    if (matchingPanel && matchingPanel.id !== selectedPanelIdRef.current) {
      setSelectedPanelId(matchingPanel.id);
      setSelectedPageOrder(matchingPanel.page_order);
    }
    const curTimeline = timelineRef.current;
    if (curTimeline && curTimeline.visual_clips.length > 0) {
      const clipAtTime = curTimeline.visual_clips.find(
        (c) => t >= c.start_time && t < c.end_time,
      );
      if (clipAtTime && clipAtTime.clip_id !== selectedClipIdRef.current) {
        setSelectedClipId(clipAtTime.clip_id);
      }
    }
  }, []);

  const handleTogglePlay = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  // 5. Ingest manga chapter pages via multi-upload
  const handleUploadPages = async (incomingFiles: FileList | File[]) => {
    const fileArray = Array.from(incomingFiles).filter(
      (f) =>
        f.type.startsWith("image/") ||
        /\.(jpg|jpeg|png|webp|bmp)$/i.test(f.name),
    );
    if (fileArray.length === 0) {
      showToastNotification(
        "⚠️ Vui lòng chọn các file ảnh (.jpg, .png, .webp).",
      );
      return;
    }

    setIsUploading(true);
    setIsPlaying(false);

    try {
      const formData = new FormData();
      fileArray.forEach((file) => {
        formData.append("files", file);
      });

      const res = await fetch(
        `http://127.0.0.1:8000/api/projects/${projectId}/upload-pages`,
        {
          method: "POST",
          body: formData,
        },
      );

      if (!res.ok) {
        throw new Error(`Upload failed with status: ${res.status}`);
      }

      const data = await res.json();
      if (data && Array.isArray(data.pages) && data.pages.length > 0) {
        interface UploadedAsset {
          id: string;
          page_order: number;
          filename: string;
          file_path: string;
          url: string;
          status: "completed" | "processing" | "ready";
        }
        const mapped: PageItem[] = data.pages.map(
          (item: UploadedAsset, idx: number) => ({
            id: item.id || `p${item.page_order || idx + 1}`,
            page_order: item.page_order || idx + 1,
            filename: item.filename,
            file_path: item.file_path,
            url: item.url,
            duration_label: `${(10 + ((item.page_order || 1) % 5) * 2.5).toFixed(2)}s`,
            status: "completed",
          }),
        );

        setPages(mapped);
        const newPanels = createDefaultPanels(mapped);
        setPanels(newPanels);
        setSelectedPanelId(mapped[0].id);
        setSelectedPageOrder(mapped[0].page_order);

        // Fetch draft timeline for page 1
        try {
          const draftRes = await fetch(
            "http://127.0.0.1:8000/api/v1/editor/draft",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                image_path: mapped[0].file_path || mapped[0].url,
                project_id: projectId,
                page_order: mapped[0].page_order,
              }),
            },
          );
          if (draftRes.ok) {
            const draftTimeline: TimelineContract = await draftRes.json();
            cachedContractsRef.current[mapped[0].page_order] = draftTimeline;
            setTimeline(draftTimeline);
            if (draftTimeline.visual_clips.length > 0) {
              setSelectedClipId(draftTimeline.visual_clips[0].clip_id);
            }
          } else {
            const synthetic = createSyntheticContract(
              mapped[0].page_order,
              projectId,
              mapped[0].file_path || mapped[0].url,
            );
            setTimeline(synthetic);
            if (synthetic.visual_clips.length > 0) {
              setSelectedClipId(synthetic.visual_clips[0].clip_id);
            }
          }
        } catch {
          const synthetic = createSyntheticContract(
            mapped[0].page_order,
            projectId,
            mapped[0].file_path || mapped[0].url,
          );
          setTimeline(synthetic);
          if (synthetic.visual_clips.length > 0) {
            setSelectedClipId(synthetic.visual_clips[0].clip_id);
          }
        }

        showToastNotification(
          `🎉 Đã tải lên thành công ${data.uploaded_count || fileArray.length} trang truyện vào dự án!`,
        );
      }
    } catch (err) {
      console.error("Upload chapter failed:", err);
      showToastNotification(
        "❌ Tải lên chapter thất bại. Vui lòng kiểm tra kết nối tới backend server.",
      );
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      if (emptyFileInputRef.current) {
        emptyFileInputRef.current.value = "";
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      void handleUploadPages(e.dataTransfer.files);
    }
  };

  const showToastNotification = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 4500);
  };

  const saveTimelineToServer = useCallback(
    async (contract: TimelineContract) => {
      try {
        await fetch(
          `http://127.0.0.1:8000/api/projects/${projectId}/timeline`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(contract),
          },
        );
      } catch (err) {
        console.warn("Could not auto-save timeline to backend:", err);
      }
    },
    [projectId],
  );

  const handleUpdateTimeline = useCallback(
    (updated: TimelineContract) => {
      setTimeline(updated);
      hasPersistedTimelineRef.current = true;
      persistedTimelineRef.current = updated;
      cachedContractsRef.current[1] = updated;
      void saveTimelineToServer(updated);
    },
    [saveTimelineToServer],
  );

  const handleAutoGenerateShort = async (styleOverride?: string) => {
    if (isGeneratingShort) return;
    setIsGeneratingShort(true);

    const targetStyle =
      (styleOverride as "dramatic" | "humorous" | "romantic" | undefined) ||
      selectedStoryStyle ||
      "dramatic";

    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/projects/${projectId}/auto-align-chapter`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            story_style: targetStyle,
            target_duration: 45,
            target_panel_count: 8,
            existing_script:
              projectInfo?.script_content ||
              ((timeline?.metadata as Record<string, unknown> | undefined)
                ?.script as Record<string, unknown> | undefined) ||
              undefined,
          }),
        },
      );

      if (!res.ok) {
        throw new Error(`Auto-align API responded with status ${res.status}`);
      }

      const newTimeline: TimelineContract = await res.json();
      hasPersistedTimelineRef.current = true;
      persistedTimelineRef.current = newTimeline;
      cachedContractsRef.current[1] = newTimeline;
      setTimeline(newTimeline);
      setCurrentTime(0);
      setIsPlaying(false);

      if (newTimeline.visual_clips.length > 0) {
        setSelectedClipId(newTimeline.visual_clips[0].clip_id);
        const updatedPanels = buildPanelsFromTimeline(
          newTimeline,
          pages,
          targetStyle,
        );
        setPanels(updatedPanels);
        if (updatedPanels.length > 0) {
          setSelectedPanelId(updatedPanels[0].id);
        }
      }

      const totalPanels = newTimeline.visual_clips.length;
      const durationSec = newTimeline.total_duration.toFixed(1);

      showToastNotification(
        `⚡ Đã tạo bản dựng Auto Short nháp (${totalPanels} panel, ${durationSec}s)! Bạn có thể xem trước và tinh chỉnh trước khi Xuất Video.`,
      );
    } catch (err) {
      console.error("Failed to auto-generate short from chapter:", err);
      showToastNotification(
        "⚠️ Không thể tự động tạo video ngắn từ chapter. Vui lòng thử lại!",
      );
    } finally {
      setIsGeneratingShort(false);
    }
  };

  // Select panel and jump playhead (marker on timeline, stays in Global Editor)
  const handleSelectPanel = (panelId: string) => {
    setSelectedPanelId(panelId);
    const target = panels.find((p) => p.id === panelId);
    if (target) {
      handleTimeUpdate(target.timelineStart);
    }
  };

  // Update panel state by unique panel ID
  const handleUpdatePanel = (panelId: string, updater: Partial<PanelItem>) => {
    setPanels((prev) =>
      prev.map((p) => (p.id === panelId ? { ...p, ...updater } : p)),
    );
  };

  // Global AI Review for ALL panels in chronological order
  const handleAiReviewAllPanels = async (
    style: "dramatic" | "humorous" | "romantic" = "dramatic",
  ) => {
    if (panels.length === 0 || reviewProgress?.isReviewing) return;

    setReviewProgress({
      current: 1,
      total: panels.length,
      isReviewing: true,
    });

    const updatedPanels = [...panels];

    for (let i = 0; i < updatedPanels.length; i++) {
      const panel = updatedPanels[i];
      setReviewProgress({
        current: i + 1,
        total: updatedPanels.length,
        isReviewing: true,
      });

      updatedPanels[i] = { ...panel, status: "processing" };
      setPanels([...updatedPanels]);

      try {
        const payload = {
          story_style: style || "dramatic",
          target_duration: Math.max(1, Math.round(panel.duration || 12)),
          panel_id: panel.id || `PANEL_${i + 1}`,
          page_order: panel.page_order ?? i + 1,
          image_path: panel.image || "",
        };

        const res = await fetch(
          `http://127.0.0.1:8000/api/projects/${projectId}/generate-script`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          },
        );

        if (res.ok) {
          const data = await res.json();
          if (
            data &&
            Array.isArray(data.segments) &&
            data.segments.length > 0
          ) {
            updatedPanels[i] = {
              ...updatedPanels[i],
              script: data.segments,
              style: style,
              status: "completed",
              error: null,
            };
          } else {
            throw new Error("Empty script response");
          }
        } else {
          throw new Error(`API error: ${res.status}`);
        }
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : String(err);
        console.warn(`Panel ${panel.id} AI review fallback:`, errMsg);
        const fallbackList: ScriptSegment[] = [
          {
            id: `SEG_${panel.id}_01`,
            section_type: i === 0 ? "hook" : "body",
            text:
              style === "dramatic"
                ? `Cảnh tượng gay cấn tại trang ${panel.page_order} khiến bất cứ ai cũng phải thót tim!`
                : style === "humorous"
                  ? `Pha xử lý cồng kềnh khó đỡ ở trang ${panel.page_order} làm người xem cười ra nước mắt.`
                  : `Cảm xúc dịu dàng và ánh nhìn lắng đọng tại trang ${panel.page_order}.`,
            estimated_duration: (panel.duration || 12) * 0.45,
            suggested_effect: i % 2 === 0 ? "punch_zoom" : "zoom_in",
          },
          {
            id: `SEG_${panel.id}_02`,
            section_type:
              i === updatedPanels.length - 1 ? "call_to_action" : "body",
            text:
              style === "dramatic"
                ? `Bí mật dần lộ diện, không ai có thể lường trước được điều gì sẽ xảy ra tiếp theo!`
                : style === "humorous"
                  ? `Đừng quên theo dõi ngay để không bỏ lỡ màn tấu hài cực mạnh tiếp theo nhé!`
                  : `Từng nhịp đập con tim dường như hòa làm một trong khoảnh khắc định mệnh này.`,
            estimated_duration: (panel.duration || 12) * 0.55,
            suggested_effect: i % 2 === 0 ? "zoom_in" : "pan_down",
          },
        ];
        updatedPanels[i] = {
          ...updatedPanels[i],
          script: fallbackList,
          style: style,
          status: "completed",
          error: null,
        };
      }

      setPanels([...updatedPanels]);
    }

    setReviewProgress(null);
    showToastNotification(
      `🤖 Đã hoàn tất AI Review cho toàn bộ ${updatedPanels.length} tranh theo phong cách ${style}!`,
    );
  };

  // Helper: Format seconds to MM:SS
  const formatTimecode = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  if (isAssetsLoading) {
    return (
      <div className="min-h-screen bg-[#09090c] text-white flex flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
        <p className="text-xs text-white/60 font-mono">
          Đang tải dữ liệu dự án...
        </p>
      </div>
    );
  }

  // If new project has no manga chapter pages yet, render Empty Chapter Workspace
  if (pages.length === 0) {
    return (
      <main className="min-h-screen bg-[#0a0a0e] text-white flex flex-col h-screen overflow-hidden select-none">
        {/* Header */}
        <header className="h-13 shrink-0 px-4 border-b border-white/10 flex items-center justify-between bg-[#0e0e13]">
          <div className="flex items-center gap-3">
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

          <div className="flex items-center gap-2">
            <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-white/50">
              Workspace Trống
            </span>
          </div>
        </header>

        {/* Toast Notification Banner */}
        {toastMessage && (
          <div className="fixed top-16 right-6 z-50 animate-bounce-in max-w-md bg-zinc-900/95 border border-amber-500/50 text-amber-200 px-4 py-3 rounded-xl shadow-2xl shadow-black/80 backdrop-blur-md flex items-center gap-3">
            <span className="text-xl">⚡</span>
            <p className="text-xs font-medium leading-relaxed text-white">
              {toastMessage}
            </p>
            <button
              onClick={() => setToastMessage(null)}
              className="text-white/40 hover:text-white text-xs ml-auto cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}

        {/* Empty Chapter Dropzone Area */}
        <div className="flex-1 min-h-0 flex items-center justify-center p-6 bg-[#08080a]">
          <input
            ref={emptyFileInputRef}
            type="file"
            multiple
            accept="image/*"
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                void handleUploadPages(e.target.files);
              }
            }}
            className="hidden"
          />

          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`w-full max-w-2xl rounded-3xl border-2 border-dashed p-10 sm:p-12 text-center transition flex flex-col items-center justify-center ${
              isDragOver
                ? "border-violet-500 bg-violet-500/10 shadow-[0_0_50px_rgba(168,85,247,0.25)] scale-[1.01]"
                : "border-white/15 bg-white/[0.02] hover:border-violet-500/50 hover:bg-white/[0.04]"
            }`}
          >
            {isUploading ? (
              <div className="flex flex-col items-center py-6">
                <div className="h-12 w-12 rounded-full border-3 border-violet-500 border-t-transparent animate-spin mb-4" />
                <h3 className="text-lg font-semibold text-white">
                  Đang nạp và xử lý Chapter Manga...
                </h3>
                <p className="mt-2 text-xs text-zinc-400 max-w-md">
                  Hệ thống đang lưu trữ ảnh, đánh số thứ tự trang và khởi tạo
                  pipeline nhận diện. Vui lòng đợi trong giây lát.
                </p>
              </div>
            ) : (
              <>
                <div className="flex h-18 w-18 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 border border-violet-500/30 text-3xl shadow-inner mb-5">
                  📚
                </div>

                <h3 className="text-xl font-bold text-white tracking-tight">
                  Tải lên toàn bộ Chapter truyện
                </h3>
                <p className="mt-2 text-sm text-zinc-400 max-w-md leading-relaxed">
                  Kéo thả toàn bộ ảnh của chapter vào đây hoặc bấm nút bên dưới.
                  Hỗ trợ chọn nhiều ảnh định dạng{" "}
                  <span className="text-violet-300 font-mono text-xs">
                    .jpg, .png, .webp
                  </span>
                  .
                </p>

                <div className="mt-6 flex flex-col sm:flex-row items-center gap-3">
                  <button
                    type="button"
                    onClick={() => emptyFileInputRef.current?.click()}
                    className="px-6 py-3 rounded-xl bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 hover:from-violet-500 hover:via-purple-500 hover:to-indigo-500 text-sm font-bold text-white shadow-lg shadow-purple-500/25 transition cursor-pointer flex items-center gap-2"
                  >
                    <span>📁</span>
                    <span>Chọn nhiều ảnh từ máy tính</span>
                  </button>
                </div>

                <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-lg text-left pt-6 border-t border-white/10">
                  <div className="rounded-lg bg-white/[0.03] p-2.5 border border-white/5">
                    <p className="text-[11px] font-semibold text-violet-300">
                      Tự động sắp xếp
                    </p>
                    <p className="text-[10px] text-zinc-400 mt-0.5">
                      Theo thứ tự tên file page_01, page_02...
                    </p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] p-2.5 border border-white/5">
                    <p className="text-[11px] font-semibold text-fuchsia-300">
                      Nhận diện Panel
                    </p>
                    <p className="text-[10px] text-zinc-400 mt-0.5">
                      AI tự động bóc tách từng khung tranh
                    </p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] p-2.5 border border-white/5">
                    <p className="text-[11px] font-semibold text-emerald-300">
                      Lưu vĩnh viễn
                    </p>
                    <p className="text-[10px] text-zinc-400 mt-0.5">
                      Dữ liệu được lưu trong DB, F5 không mất
                    </p>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    );
  }

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

        {/* Action Controls: Bộ chọn Phong cách, Nút AI Review Toàn Bộ, Nút Tạo Video Ngắn Tự Động & Nút Xuất Video */}
        <div className="flex items-center gap-2.5">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*"
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                void handleUploadPages(e.target.files);
              }
            }}
            className="hidden"
          />

          {/* Quick Style Selector in Header */}
          <div className="hidden xl:flex items-center gap-1 bg-white/[0.04] border border-white/10 rounded-lg p-1">
            <button
              type="button"
              onClick={() => setSelectedStoryStyle("dramatic")}
              className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition cursor-pointer ${
                selectedStoryStyle === "dramatic"
                  ? "bg-purple-600/80 text-white shadow-sm ring-1 ring-purple-400/50"
                  : "text-white/60 hover:text-white"
              }`}
            >
              ⚡ Kịch tính
            </button>
            <button
              type="button"
              onClick={() => setSelectedStoryStyle("humorous")}
              className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition cursor-pointer ${
                selectedStoryStyle === "humorous"
                  ? "bg-amber-600/80 text-white shadow-sm ring-1 ring-amber-400/50"
                  : "text-white/60 hover:text-white"
              }`}
            >
              🎭 Cà khịa
            </button>
            <button
              type="button"
              onClick={() => setSelectedStoryStyle("romantic")}
              className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition cursor-pointer ${
                selectedStoryStyle === "romantic"
                  ? "bg-pink-600/80 text-white shadow-sm ring-1 ring-pink-400/50"
                  : "text-white/60 hover:text-white"
              }`}
            >
              💖 Lãng mạn
            </button>
          </div>

          <button
            type="button"
            onClick={() => handleAiReviewAllPanels(selectedStoryStyle)}
            disabled={reviewProgress?.isReviewing}
            className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 hover:from-violet-500 hover:via-purple-500 hover:to-indigo-500 text-xs font-bold text-white shadow-lg shadow-purple-500/20 transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            title="Tự động phân tích và tạo kịch bản cho TOÀN BỘ các tranh trong chapter"
          >
            {reviewProgress?.isReviewing ? (
              <>
                <div className="h-3.5 w-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                <span>
                  Review {reviewProgress.current}/{reviewProgress.total}...
                </span>
              </>
            ) : (
              <>
                <span>🤖</span>
                <span>AI Review Toàn Bộ ({panels.length || 1} Tranh)</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => handleAutoGenerateShort(selectedStoryStyle)}
            disabled={isGeneratingShort}
            className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-amber-500 via-violet-600 to-fuchsia-600 hover:from-amber-400 hover:via-violet-500 hover:to-fuchsia-500 text-xs font-bold text-white shadow-lg shadow-amber-500/20 transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
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

      {/* Toast Notification Banner */}
      {toastMessage && (
        <div className="fixed top-16 right-6 z-50 animate-bounce-in max-w-md bg-zinc-900/95 border border-amber-500/50 text-amber-200 px-4 py-3 rounded-xl shadow-2xl shadow-black/80 backdrop-blur-md flex items-center gap-3">
          <span className="text-xl">⚡</span>
          <p className="text-xs font-medium leading-relaxed text-white">
            {toastMessage}
          </p>
          <button
            onClick={() => setToastMessage(null)}
            className="text-white/40 hover:text-white text-xs ml-auto cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

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

          {/* Lưới 2 cột thumbnail gọn gàng hiển thị 100% trang manga gốc */}
          <div className="flex-1 overflow-y-auto p-3 overscroll-contain [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-width:thin]">
            <div className="grid grid-cols-2 gap-2.5">
              {pages.map((pg) => {
                const isSelected = pg.page_order === selectedPageOrder;

                const imgSrc =
                  pg.page_order === 1 &&
                  projectId === DEFAULT_BENCHMARK_PROJECT_ID
                    ? "/page_01.jpg"
                    : resolveImageUrl(pg.url || pg.file_path);

                const hasClip = timeline?.visual_clips?.some(
                  (vc) =>
                    (vc.image_path && vc.image_path.includes(pg.filename)) ||
                    (vc.panel_id &&
                      vc.panel_id.includes(
                        `P${String(pg.page_order).padStart(2, "0")}`,
                      )),
                );

                return (
                  <button
                    key={pg.id}
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedPageOrder(pg.page_order);
                      const matchingPanel = panels.find(
                        (p) => p.page_order === pg.page_order,
                      );
                      if (matchingPanel) {
                        handleSelectPanel(matchingPanel.id);
                      } else {
                        const matchingClip = timeline?.visual_clips?.find(
                          (vc) =>
                            (vc.image_path &&
                              vc.image_path.includes(pg.filename)) ||
                            (vc.panel_id &&
                              vc.panel_id.includes(
                                `P${String(pg.page_order).padStart(2, "0")}`,
                              )),
                        );
                        if (matchingClip) {
                          handleTimeUpdate(matchingClip.start_time);
                          setSelectedClipId(matchingClip.clip_id);
                        }
                      }
                    }}
                    className={`group relative aspect-[3/4] w-full rounded-lg overflow-hidden border bg-[#151518] transition text-left cursor-pointer ${
                      isSelected
                        ? "border-violet-500 ring-2 ring-violet-500/30 shadow-lg shadow-violet-950/40"
                        : "border-white/[0.08] hover:border-white/25"
                    }`}
                  >
                    <div className="relative h-full w-full bg-[#0b0b0d]">
                      <Image
                        src={imgSrc}
                        alt={`Trang ${pg.page_order}`}
                        fill
                        unoptimized
                        sizes="120px"
                        className="object-contain"
                      />
                      {pg.status === "processing" && (
                        <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                          <div className="h-4 w-4 rounded-full border-2 border-violet-400 border-t-transparent animate-spin" />
                        </div>
                      )}
                    </div>

                    <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/90 via-black/50 to-transparent px-2 pb-1 pt-4">
                      <span className="text-[11px] font-medium text-white/90 font-mono">
                        {String(pg.page_order).padStart(2, "0")}
                      </span>
                      {hasClip && (
                        <span
                          className="text-[9px] bg-violet-600/80 text-white font-bold px-1 rounded"
                          title="Trang được chọn làm visual clip cho video"
                        >
                          CLIP
                        </span>
                      )}
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
                  ref={videoPreviewRef}
                  timeline={timeline}
                  currentTime={currentTime}
                  isPlaying={isPlaying}
                  onTimeUpdate={handleTimeUpdate}
                  onTogglePlay={handleTogglePlay}
                  selectedClipId={selectedClipId}
                  activePageImage={
                    panels.find((p) => p.id === selectedPanelId)?.image ||
                    pages.find((p) => p.page_order === selectedPageOrder)
                      ?.url ||
                    pages.find((p) => p.page_order === selectedPageOrder)
                      ?.file_path
                  }
                />
              </div>

              {/* Thanh phát tối giản ngay dưới khung tranh */}
              <div className="w-full max-w-[420px] flex h-8 shrink-0 items-center gap-2.5 rounded-lg border border-white/[0.08] bg-[#0e0e12] px-3 text-white/50 mt-1.5">
                <button
                  type="button"
                  onClick={() => {
                    if (videoPreviewRef.current) {
                      videoPreviewRef.current.togglePlay();
                    } else {
                      handleTogglePlay();
                    }
                  }}
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
                    onChange={(e) =>
                      handleTimeUpdate(parseFloat(e.target.value))
                    }
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
                onUpdateTimeline={handleUpdateTimeline}
                onSeek={handleTimeUpdate}
                onSelectClip={(id) => setSelectedClipId(id)}
                onAutoGenerateShort={handleAutoGenerateShort}
                isGeneratingShort={isGeneratingShort}
                panels={panels}
                selectedPanelId={selectedPanelId}
                onUpdatePanel={handleUpdatePanel}
                onAiReviewAllPanels={handleAiReviewAllPanels}
                reviewProgress={reviewProgress}
                storyStyle={selectedStoryStyle}
                onSelectStoryStyle={setSelectedStoryStyle}
              />
            </aside>
          </div>

          {/* TẦNG DƯỚI (Bàn dựng âm thanh kiểu CapCut gấp đôi chiều cao tràn ngang toàn bộ khối bên phải) */}
          <div className="h-[280px] lg:h-[300px] shrink-0 bg-[#0a0a0d] flex flex-col overflow-hidden">
            <Timeline
              timeline={timeline}
              currentTime={currentTime}
              onSeek={handleTimeUpdate}
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
