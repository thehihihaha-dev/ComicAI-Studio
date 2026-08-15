"use client";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import ReviewQueue from "./ReviewQueue";
export interface Asset {
  id: string;
  project_id: string;
  filename: string;
  file_type: string;
  file_path: string;
  page_order: number;
  created_at: string;
  status: string;
  ocr_text: string | null;
  ocr_blocks: {
    text: string;
    confidence: number;
    box: number[][];
  }[];
  vision_status: string;

  vision_regions: {
    id: number;
    type: string;
    block_ids: number[];
    recovered?: boolean;
    confidence?: number;
  }[];

  reading_order: number[];
  dialogue_status: string;

  dialogues: {
    order: number;
    region_id: number;
    raw_text: string;
    clean_text: string;
    confidence: number;
    needs_review: boolean;
    reason: string;
    ocr_confidence: number;
    text_similarity: number;
    correction_score: number;
    decision: string;
    verified_text?: string | null;
    recovered_text?: string | null;
    human_verified?: boolean;
  }[];
  url: string;
}
export default function AssetUploader({ projectId, selectedAssetId, onSelectAsset, onAssetsChange }: { projectId: string; selectedAssetId: string | null; onSelectAsset: (assetId: string) => void; onAssetsChange: (assets: Asset[]) => void }) {
  const PAGE_LIMIT = 30;
  const [files, setFiles] = useState<File[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [totalAssets, setTotalAssets] = useState(0);
  const [nextPage, setNextPage] = useState(2);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [activeAsset, setActiveAsset] = useState<Asset | null>(null);
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const holdTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const longPressTriggered = useRef(false);
  const thumbnailScrollRef = useRef<HTMLDivElement | null>(null);
  const dragPointerId = useRef<number | null>(null);
  const dragStart = useRef({ assetId: "", x: 0, y: 0 });
  const dragPointer = useRef({ x: 0, y: 0 });
  const dragVisitedAssetIds = useRef(new Set<string>());
  const isDraggingSelection = useRef(false);
  const suppressNextClick = useRef(false);
  const autoScrollFrame = useRef<number | null>(null);
  const [ocrProgress, setOcrProgress] = useState({
    status: "idle",
    total: 0,
    completed: 0,
    processing: 0,
    failed: 0,
    percent: 0,
  });
  useEffect(() => {
    fetch(
      `http://127.0.0.1:8000/assets/project/${projectId}?page=1&limit=${PAGE_LIMIT}`,
    )
      .then((response) => response.json())
      .then((data) => {
        setAssets(data.items);
        onAssetsChange(data.items);
        setTotalAssets(data.total);
        setNextPage(2);
        setHasMore(data.page < data.total_pages);
      });
  }, [projectId, onAssetsChange]);
  useEffect(() => {
    async function loadProgress() {
      const response = await fetch(
        `http://127.0.0.1:8000/assets/project/${projectId}/progress`,
        {
          cache: "no-store",
        },
      );

      const data = await response.json();
      setOcrProgress(data);
    }

    loadProgress();

    const interval = setInterval(loadProgress, 2000);

    return () => clearInterval(interval);
  }, [projectId]);
  useEffect(() => () => {
    if (holdTimer.current) clearTimeout(holdTimer.current);
    if (autoScrollFrame.current !== null) cancelAnimationFrame(autoScrollFrame.current);
  }, []);
  async function loadAssets() {
    const response = await fetch(
      `http://127.0.0.1:8000/assets/project/${projectId}?page=1&limit=${PAGE_LIMIT}`,
      {
        cache: "no-store",
      },
    );

    const data = await response.json();

    setAssets(data.items);
    onAssetsChange(data.items);
    setTotalAssets(data.total);
    setNextPage(2);
    setHasMore(data.page < data.total_pages);
  }
  async function loadMoreAssets() {
    if (!hasMore || loadingMore) return;
    setLoadingMore(true);
    try {
      const response = await fetch(`http://127.0.0.1:8000/assets/project/${projectId}?page=${nextPage}&limit=${PAGE_LIMIT}`, { cache: "no-store" });
      const data = await response.json();
      const known = new Set(assets.map((asset) => asset.id));
      const merged = [...assets, ...data.items.filter((asset: Asset) => !known.has(asset.id))];
      setAssets(merged);
      onAssetsChange(merged);
      setNextPage((current) => current + 1);
      setHasMore(data.page < data.total_pages);
    } finally {
      setLoadingMore(false);
    }
  }
  async function uploadFiles() {
    setUploading(true);
    setMessage("");

    try {
      const formData = new FormData();
      formData.append("project_id", projectId);

      files.forEach((file) => {
        formData.append("files", file);
      });

      const response = await fetch("http://127.0.0.1:8000/assets/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const data = await response.json();
      console.log(data);

      await loadAssets();

      setFiles([]);
      setMessage(`Uploaded ${files.length} images successfully.`);
    } catch (error) {
      console.error(error);
      setMessage("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }
  async function startOcrProcessing() {
    setMessage("Starting image analysis...");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/assets/project/${projectId}/process`,
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to start OCR");
      }

      const data = await response.json();

      if (data.queued === 0) {
        setMessage("No new images need processing.");
      } else {
        setMessage(`Analyzing ${data.queued} images...`);
      }
    } catch (error) {
      console.error(error);
      setMessage("Could not start image analysis.");
    }
  }
  async function pollLayoutStatus(assetId: string) {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/assets/project/${projectId}?page=1&limit=${PAGE_LIMIT}&t=${Date.now()}`,
          {
            cache: "no-store",
          },
        );

        const data = await response.json();

        const currentAsset = data.items.find(
          (asset: Asset) => asset.id === assetId,
        );

        if (!currentAsset) return;

        if (
          currentAsset.vision_status === "completed" ||
          currentAsset.vision_status === "no_dialogue" ||
          currentAsset.vision_status === "failed"
        ) {
          clearInterval(interval);
          await loadAssets();
        }
      } catch (error) {
        console.error("Layout polling error:", error);
      }
    }, 2000);
  }

  async function analyzeLayout(assetId: string) {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/assets/${assetId}/analyze-layout`,
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to start layout analysis");
      }

      // Đổi UI sang processing ngay
      setAssets((currentAssets) => currentAssets.map((asset) =>
        asset.id === assetId ? { ...asset, vision_status: "processing" } : asset,
      ));

      pollLayoutStatus(assetId);
    } catch (error) {
      console.error("Layout analysis error:", error);
      setMessage("Could not analyze layout.");
    }
  }
  async function pollDialogueStatus(assetId: string) {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/assets/project/${projectId}?page=1&limit=${PAGE_LIMIT}&t=${Date.now()}`,
          { cache: "no-store" },
        );
        const data = await response.json();
        const currentAsset = data.items.find(
          (asset: Asset) => asset.id === assetId,
        );

        if (!currentAsset) return;

        if (
          currentAsset.dialogue_status === "completed" ||
          currentAsset.dialogue_status === "needs_review" ||
          currentAsset.dialogue_status === "failed"
        ) {
          clearInterval(interval);
          await loadAssets();
        }
      } catch (error) {
        console.error("Dialogue polling error:", error);
      }
    }, 2000);
  }

  async function buildDialogues(assetId: string) {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/assets/${assetId}/build-dialogues`,
        { method: "POST" },
      );

      if (!response.ok) {
        throw new Error("Failed to start dialogue analysis");
      }

      setAssets((currentAssets) => currentAssets.map((asset) =>
        asset.id === assetId ? { ...asset, dialogue_status: "processing" } : asset,
      ));
      void pollDialogueStatus(assetId);
    } catch (error) {
      console.error("Dialogue analysis error:", error);
      setMessage("Could not analyze dialogues.");
    }
  }
  async function deleteAsset(asset: Asset) {
    if (!window.confirm(`Xóa Trang ${asset.page_order}?`)) return;
    const response = await fetch(`http://127.0.0.1:8000/assets/${asset.id}`, { method: "DELETE" });
    if (!response.ok) { setMessage("Không thể xóa trang."); return; }
    setActiveAsset(null); setOpenMenuId(null); await loadAssets();
  }
  function toggleSelectedAsset(assetId: string) {
    setSelectedAssets((current) => current.includes(assetId) ? current.filter((id) => id !== assetId) : [...current, assetId]);
  }
  function addDragSelection(assetId: string) {
    if (dragVisitedAssetIds.current.has(assetId)) return;
    dragVisitedAssetIds.current.add(assetId);
    setSelectedAssets((current) => current.includes(assetId) ? current : [...current, assetId]);
  }
  function selectAssetAtPointer(x: number, y: number) {
    const scrollArea = thumbnailScrollRef.current;
    const target = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-thumbnail-asset-id]");
    if (!scrollArea || !target || !scrollArea.contains(target)) return;
    const assetId = target.dataset.thumbnailAssetId;
    if (assetId) addDragSelection(assetId);
  }
  function stopSelectionDrag() {
    dragPointerId.current = null;
    isDraggingSelection.current = false;
    dragVisitedAssetIds.current.clear();
    if (autoScrollFrame.current !== null) cancelAnimationFrame(autoScrollFrame.current);
    autoScrollFrame.current = null;
  }
  function runAutoScroll() {
    const scrollArea = thumbnailScrollRef.current;
    if (!scrollArea || !isDraggingSelection.current) {
      autoScrollFrame.current = null;
      return;
    }

    const bounds = scrollArea.getBoundingClientRect();
    const edgeSize = 72;
    const { x, y } = dragPointer.current;
    let speed = 0;
    if (y < bounds.top + edgeSize) speed = -Math.ceil(14 * Math.min(1, (bounds.top + edgeSize - y) / edgeSize));
    if (y > bounds.bottom - edgeSize) speed = Math.ceil(14 * Math.min(1, (y - (bounds.bottom - edgeSize)) / edgeSize));
    if (speed !== 0) {
      scrollArea.scrollTop += speed;
      selectAssetAtPointer(x, y);
    }
    autoScrollFrame.current = requestAnimationFrame(runAutoScroll);
  }
  function beginSelectionPointer(event: ReactPointerEvent<HTMLElement>, assetId: string) {
    if (selectedAssets.length === 0 || event.button !== 0) {
      if (event.button !== 0) return;
      startLongPress(assetId);
      return;
    }
    event.preventDefault();
    dragPointerId.current = event.pointerId;
    dragStart.current = { assetId, x: event.clientX, y: event.clientY };
    dragPointer.current = { x: event.clientX, y: event.clientY };
    dragVisitedAssetIds.current.clear();
    isDraggingSelection.current = false;
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function moveSelectionPointer(event: ReactPointerEvent<HTMLElement>) {
    if (dragPointerId.current !== event.pointerId) return;
    dragPointer.current = { x: event.clientX, y: event.clientY };
    const distance = Math.hypot(event.clientX - dragStart.current.x, event.clientY - dragStart.current.y);
    if (!isDraggingSelection.current && distance >= 5) {
      isDraggingSelection.current = true;
      addDragSelection(dragStart.current.assetId);
      autoScrollFrame.current = requestAnimationFrame(runAutoScroll);
    }
    if (isDraggingSelection.current) selectAssetAtPointer(event.clientX, event.clientY);
  }
  function endSelectionPointer(event: ReactPointerEvent<HTMLElement>) {
    cancelLongPress();
    if (dragPointerId.current !== event.pointerId) return;
    if (isDraggingSelection.current) suppressNextClick.current = true;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    stopSelectionDrag();
  }
  function startLongPress(assetId: string) {
    longPressTriggered.current = false;
    holdTimer.current = setTimeout(() => {
      longPressTriggered.current = true;
      setSelectedAssets((current) => current.includes(assetId) ? current : [...current, assetId]);
    }, 1000);
  }
  function cancelLongPress() {
    if (holdTimer.current) clearTimeout(holdTimer.current);
    holdTimer.current = null;
  }
  function handleAssetClick(assetId: string) {
    if (suppressNextClick.current) {
      suppressNextClick.current = false;
      return;
    }
    if (longPressTriggered.current) {
      longPressTriggered.current = false;
      return;
    }
    if (selectedAssets.length > 0) {
      toggleSelectedAsset(assetId);
      return;
    }

    const asset = assets.find((item) => item.id === assetId);
    onSelectAsset(assetId);
    if (asset) {
      setTechnicalOpen(false);
      setActiveAsset(asset);
    }
  }
  async function deleteSelectedAssets() {
    if (!selectedAssets.length || !window.confirm(`Xóa ${selectedAssets.length} trang đã chọn?`)) return;
    const response = await fetch("http://127.0.0.1:8000/assets/batch/", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify(selectedAssets) });
    if (!response.ok) { setMessage("Không thể xóa các trang đã chọn."); return; }
    setSelectedAssets([]);
    await loadAssets();
  }

  const failedCount = assets.filter((asset) => asset.status === "failed" || asset.vision_status === "failed" || asset.dialogue_status === "failed").length;
  const reviewCount = assets.filter((asset) => asset.dialogue_status === "needs_review").length;
  const problemCount = failedCount + reviewCount;
  const processing = assets.some((asset) => asset.status === "processing" || asset.vision_status === "processing" || asset.dialogue_status === "processing") || ocrProgress.status === "processing";

  return <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
    <div className="shrink-0 border-b border-white/[0.08] p-4">
      <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">Trang truyện</h2><span className="text-xs text-white/30">{totalAssets}</span></div>
      <div className="mt-3 grid gap-2">
        <label className="flex cursor-pointer items-center justify-center rounded-lg border border-white/10 py-2 text-xs text-white/55 transition hover:bg-white/5 hover:text-white">+ Thêm trang<input type="file" accept="image/*" multiple className="hidden" onChange={(event) => event.target.files && setFiles(Array.from(event.target.files))} /></label>
        {files.length > 0 && <button onClick={uploadFiles} disabled={uploading} className="rounded-lg bg-white py-2 text-xs font-medium text-black disabled:opacity-50">{uploading ? "Đang tải..." : `Tải lên ${files.length} trang`}</button>}
        {totalAssets > 0 && ocrProgress.status !== "processing" && <button onClick={startOcrProcessing} className="rounded-lg border border-violet-400/25 py-2 text-xs text-violet-200 hover:bg-violet-500/10">{ocrProgress.status === "completed" ? "Phân tích lại" : "✦ Phân tích"}</button>}
      </div>
      {message && <p className="mt-2 text-xs leading-5 text-white/35">{message}</p>}
      {processing && <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-violet-400" style={{ width: `${ocrProgress.percent}%` }} /></div>}
      {problemCount > 0 && <p className={`mt-2 text-xs ${failedCount ? "text-red-400" : "text-amber-300"}`}>{failedCount ? `${failedCount} trang thất bại` : `${reviewCount} trang cần kiểm tra`}</p>}
    </div>

    {selectedAssets.length > 0 && <div className="flex shrink-0 items-center justify-between border-b border-violet-400/20 bg-violet-500/[0.08] px-3 py-2"><span className="text-xs text-violet-200">Đã chọn {selectedAssets.length} trang</span><div className="flex gap-2"><button onClick={() => { stopSelectionDrag(); setSelectedAssets([]); }} className="text-xs text-white/40 hover:text-white">Hủy</button><button onClick={() => void deleteSelectedAssets()} className="rounded-md bg-red-500/15 px-2 py-1 text-xs text-red-300 hover:bg-red-500/25">Xóa</button></div></div>}
    <div ref={thumbnailScrollRef} className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain p-3 [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-gutter:stable] [scrollbar-width:thin]" onScroll={(event) => { const target = event.currentTarget; if (target.scrollHeight - target.scrollTop - target.clientHeight < 240) void loadMoreAssets(); }}>
      <div className="grid auto-rows-max grid-cols-2 content-start gap-3">
      {assets.map((asset) => <article key={asset.id} data-thumbnail-asset-id={asset.id} onPointerDown={(event) => beginSelectionPointer(event, asset.id)} onPointerMove={moveSelectionPointer} onPointerUp={endSelectionPointer} onPointerCancel={endSelectionPointer} onPointerLeave={() => { if (selectedAssets.length === 0) cancelLongPress(); }} onClick={() => handleAssetClick(asset.id)} className={`group relative h-32 shrink-0 cursor-pointer touch-pan-y select-none overflow-hidden rounded-lg border bg-[#151518] transition ${selectedAssets.includes(asset.id) ? "border-violet-400 bg-violet-500/10 ring-1 ring-violet-400/30" : selectedAssetId === asset.id ? "border-violet-400/70 shadow-[0_0_0_1px_rgba(139,92,246,0.12)]" : "border-white/[0.08] hover:border-white/25"}`}>
        <div className="relative h-full w-full bg-[#0b0b0d]"><Image src={asset.url} alt={asset.filename} fill unoptimized loading="lazy" draggable={false} sizes="160px" className="pointer-events-none object-contain" /></div>
        <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/90 via-black/60 to-transparent px-3 pb-2.5 pt-9"><span className="text-xs font-medium">{String(asset.page_order).padStart(2, "0")}</span><span title={friendlyStatus(asset)} className={`text-xs ${statusTone(asset)}`}>{statusIcon(asset)}</span></div>
        {selectedAssets.includes(asset.id) && <span className="absolute left-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-violet-500 text-[11px] text-white">✓</span>}
        <button onClick={(event) => { event.stopPropagation(); setOpenMenuId((current) => current === asset.id ? null : asset.id); }} className="absolute right-1.5 top-1.5 flex h-7 w-8 items-center justify-center rounded-md bg-black/45 text-sm text-white/55 opacity-0 backdrop-blur-sm transition group-hover:opacity-100" aria-label={`Tùy chọn trang ${asset.page_order}`}>•••</button>
        {openMenuId === asset.id && <div onClick={(event) => event.stopPropagation()} className="absolute right-2 top-9 z-10 min-w-44 rounded-lg border border-white/10 bg-[#202024] p-1 shadow-2xl"><button onClick={() => { setActiveAsset(asset); setTechnicalOpen(false); setOpenMenuId(null); }} className="w-full rounded-md px-2.5 py-2 text-left text-xs hover:bg-white/10">Xem nội dung</button><button onClick={() => void analyzeLayout(asset.id)} className="w-full rounded-md px-2.5 py-2 text-left text-xs hover:bg-white/10">Phân tích lại</button><button onClick={() => { setActiveAsset(asset); setTechnicalOpen(true); setOpenMenuId(null); }} className="w-full rounded-md px-2.5 py-2 text-left text-xs hover:bg-white/10">Chi tiết kỹ thuật</button><button onClick={() => void deleteAsset(asset)} className="w-full rounded-md px-2.5 py-2 text-left text-xs text-red-400 hover:bg-red-500/10">Xóa trang</button></div>}
      </article>)}
      {loadingMore && <div className="col-span-2 py-3 text-center text-xs text-white/25">Đang tải thêm...</div>}
      </div>
    </div>

    <details className="max-h-[35%] shrink-0 overflow-y-auto border-t border-white/[0.08] p-3"><summary className="cursor-pointer text-[11px] text-white/25">Developer tools</summary><ReviewQueue projectId={projectId} /></details>
    {activeAsset && <PageModal asset={activeAsset} technicalOpen={technicalOpen} onTechnical={() => setTechnicalOpen((current) => !current)} onClose={() => setActiveAsset(null)} onLayout={() => void analyzeLayout(activeAsset.id)} onDialogue={() => void buildDialogues(activeAsset.id)} />}
  </div>;
}

function statusIcon(asset: Asset) { const status = friendlyStatus(asset); if (status.includes("Sẵn sàng")) return "✓"; if (status.includes("Đang")) return "◌"; if (status.includes("Cần")) return "!"; if (status.includes("thất bại")) return "×"; return "○"; }

function friendlyStatus(asset: Asset) { if (asset.status === "failed" || asset.vision_status === "failed" || asset.dialogue_status === "failed") return "● Xử lý thất bại"; if (asset.dialogue_status === "needs_review") return "● Cần kiểm tra"; if (asset.status === "processing" || asset.vision_status === "processing" || asset.dialogue_status === "processing") return "◌ Đang đọc..."; if (asset.vision_status === "no_dialogue") return "○ Không có thoại"; if (asset.vision_status === "completed" && asset.dialogue_status === "completed") return "✓ Sẵn sàng"; return "○ Chưa xử lý"; }
function statusTone(asset: Asset) { const status = friendlyStatus(asset); return status.includes("Sẵn sàng") ? "text-emerald-400" : status.includes("Không có") ? "text-slate-400" : status.includes("thất bại") ? "text-red-400" : status.includes("Cần") ? "text-amber-400" : status.includes("Đang") ? "text-violet-300" : "text-white/35"; }
function finalDialogueText(dialogue: Asset["dialogues"][number]) { return dialogue.verified_text || dialogue.recovered_text || dialogue.clean_text || dialogue.raw_text; }

function PageModal({ asset, technicalOpen, onTechnical, onClose, onLayout, onDialogue }: { asset: Asset; technicalOpen: boolean; onTechnical: () => void; onClose: () => void; onLayout: () => void; onDialogue: () => void }) {
  const dialogues = [...(asset.dialogues ?? [])].sort((a, b) => a.order - b.order);
  return <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/75 p-0 backdrop-blur-sm sm:items-center sm:p-6" onMouseDown={onClose}><div className="max-h-[100dvh] w-full overflow-y-auto rounded-t-3xl border border-white/10 bg-[#111115] p-5 sm:max-h-[90vh] sm:max-w-5xl sm:rounded-3xl sm:p-7" onMouseDown={(event) => event.stopPropagation()}><div className="flex items-center justify-between"><div><p className="text-xs text-white/35">{asset.filename}</p><h3 className="mt-1 text-xl font-semibold">Trang {asset.page_order}</h3></div><button onClick={onClose} className="h-10 w-10 rounded-full border border-white/10 text-white/60 hover:bg-white/10">×</button></div><div className="mt-6 grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(300px,0.9fr)]"><div className="relative min-h-[55vh] overflow-hidden rounded-2xl bg-black/30"><Image src={asset.url} alt={asset.filename} fill unoptimized sizes="(max-width: 768px) 100vw, 55vw" className="object-contain" /></div><div><h4 className="text-sm font-medium text-white/70">Nội dung đã đọc</h4>{asset.vision_status === "no_dialogue" ? <p className="mt-4 rounded-xl border border-sky-400/15 bg-sky-500/5 p-4 text-sm text-sky-200">ComicAI không phát hiện hội thoại trên trang này.</p> : dialogues.length ? <div className="mt-3 space-y-2">{dialogues.map((dialogue) => <div key={dialogue.region_id} className="flex gap-3 rounded-xl border border-white/8 bg-white/[0.025] p-3"><span className="text-xs font-semibold text-violet-300">{String(dialogue.order).padStart(2, "0")}</span><p className="text-sm leading-6 text-white/75">{finalDialogueText(dialogue)}</p></div>)}</div> : <p className="mt-4 text-sm text-white/40">Trang này chưa có nội dung hội thoại đã xử lý.</p>}<p className={`mt-5 text-sm ${statusTone(asset)}`}>{friendlyStatus(asset)}</p><div className="mt-4 flex flex-wrap gap-2"><button onClick={onTechnical} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/55 hover:text-white">{technicalOpen ? "Ẩn kỹ thuật" : "Chi tiết kỹ thuật"}</button><button onClick={onLayout} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/55 hover:text-white">Phân tích layout lại</button>{asset.vision_status === "completed" && <button onClick={onDialogue} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/55 hover:text-white">Phân tích thoại lại</button>}</div>{technicalOpen && <div className="mt-4 space-y-3 rounded-xl border border-white/10 bg-black/20 p-4 text-xs text-white/45"><p>OCR: {asset.status}</p><p>Vision: {asset.vision_status}</p><p>Dialogue: {asset.dialogue_status}</p><p>Regions: {asset.vision_regions?.length ?? 0}</p><p>Reading order: {asset.reading_order?.join(" → ") || "—"}</p><details><summary className="cursor-pointer text-white/60">Raw OCR</summary><pre className="mt-2 whitespace-pre-wrap">{asset.ocr_text || "—"}</pre></details></div>}</div></div></div></div>;
}
