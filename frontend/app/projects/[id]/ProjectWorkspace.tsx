"use client";

import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AssetUploader, { type Asset } from "./AssetUploader";
import ReviewQueue, { type ReviewItem } from "./ReviewQueue";

type RightTab = "story" | "script";
type StoryUiState =
  | "STORY_INPUT_BLOCKED"
  | "STORY_NOT_ANALYZED"
  | "STORY_LOADING"
  | "STORY_PARTIAL"
  | "STORY_READY"
  | "STORY_REVIEWING"
  | "STORY_REVIEWED"
  | "STORY_AWAITING_APPROVAL"
  | "STORY_APPROVED"
  | "STORY_APPROVAL_INVALID"
  | "STORY_STALE"
  | "STORY_ERROR";
type Source = { asset_id: string; page_order: number; region_ids: number[] };
type Claim = { id: string; text: string; sources: Source[] };
type StoryEvent = {
  id: string;
  summary?: string;
  story_role: "main_story" | "supporting_context";
  claims: Claim[];
  unsupported_claims?: unknown[];
  script_ready?: boolean;
  provenance?: "ai_grounded" | "human_edited" | "human_added";
};
type UnresolvedEvidence = {
  asset_id: string;
  page_order: number;
  region_id: number;
  text_role: string;
  evidence_text: string;
};
type Reliability = {
  reliability_version?: string;
  analysis_attempts?: number;
  coverage: {
    coverage_score?: number;
    covered_regions: number;
    non_story_relevant_regions: number;
    unresolved_regions: number;
    important_uncovered_regions: UnresolvedEvidence[];
  };
  grounded_result: {
    events: StoryEvent[];
    main_progression: string[];
    issues?: unknown[];
  };
};
type Segment = { id: string; type: string; text: string; source_event_ids: string[]; source_claim_ids: string[]; provenance?: "ai_generated" | "human_edited" };
type ScriptResult = { segments: Segment[]; summary: { word_count: number; estimated_duration_seconds?: number } };
type ScriptRecord = {
  status: "empty" | "generated" | "edited" | "approved" | "stale";
  stale?: boolean;
  style?: string;
  script_approved: boolean;
  approval_invalidated?: boolean;
  source_story_fingerprint?: string;
  source_story_approved_at?: string;
  script_fingerprint?: string;
  approved_at?: string | null;
  final_script: ScriptResult | null;
};
type RegionEvidence = {
  asset_id: string;
  region_id: number;
  bbox: [number, number, number, number];
  text_role: string;
  image_size: { width: number; height: number };
};
type SourceInspection = {
  assetId: string;
  regionIds: number[];
  regions: RegionEvidence[];
  eventId?: string;
  unresolvedKey?: string;
  kind: "event" | "unresolved";
};
type PersistedStory = {
  status: "none" | "partial" | "ready" | "stale";
  stale: boolean;
  result: unknown;
};
type StoryReview = {
  status: "none" | "in_progress" | "reviewed" | "stale";
  stale: boolean;
  source_revision: string;
  review_source_revision: string | null;
  ai_status: "partial" | "ready";
  resolved_by_human: number;
  unresolved_total: number;
  unresolved_remaining: number;
  human_added_event_ids: string[];
  review_complete: boolean;
  final_story_ready: boolean;
  story_approved: boolean;
  approval_invalidated: boolean;
  final_story_fingerprint: string;
  approved_story_fingerprint: string | null;
  approved_at: string | null;
  final_story: Reliability;
};

function storyReviewUiState(review: StoryReview): StoryUiState {
  if (review.stale) return "STORY_STALE";
  if (review.story_approved) return "STORY_APPROVED";
  if (review.approval_invalidated) return "STORY_APPROVAL_INVALID";
  if (review.final_story_ready) return "STORY_AWAITING_APPROVAL";
  if (review.status === "in_progress") return "STORY_REVIEWING";
  return review.ai_status === "ready" ? "STORY_READY" : "STORY_PARTIAL";
}

function isReliabilityResult(value: unknown): value is Reliability {
  if (!value || typeof value !== "object") return false;
  const result = value as Partial<Reliability>;
  return Boolean(
    result.coverage
    && typeof result.coverage.unresolved_regions === "number"
    && Array.isArray(result.coverage.important_uncovered_regions)
    && result.grounded_result
    && Array.isArray(result.grounded_result.events)
    && Array.isArray(result.grounded_result.main_progression),
  );
}

function isStoryScriptUsable(story: Reliability) {
  return story.coverage.unresolved_regions === 0
    && story.grounded_result.events.some(
      (event) => event.story_role === "main_story" && event.script_ready === true,
    );
}

export default function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [rightTab, setRightTab] = useState<RightTab>("story");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [story, setStory] = useState<Reliability | null>(null);
  const [storyReview, setStoryReview] = useState<StoryReview | null>(null);
  const [storyInputStatus, setStoryInputStatus] = useState<"loading" | "ready" | "blocked">("loading");
  const [storyState, setStoryState] = useState<StoryUiState>("STORY_NOT_ANALYZED");
  const [lastStableStoryState, setLastStableStoryState] = useState<StoryUiState>("STORY_NOT_ANALYZED");
  const [storyError, setStoryError] = useState("");
  const [inspection, setInspection] = useState<SourceInspection | null>(null);
  const [style, setStyle] = useState("natural");
  const [script, setScript] = useState<ScriptResult | null>(null);
  const [scriptRecord, setScriptRecord] = useState<ScriptRecord | null>(null);
  const [scriptLoading, setScriptLoading] = useState(false);
  const [scriptError, setScriptError] = useState("");
  const [assetRefreshToken, setAssetRefreshToken] = useState(0);

  const selectedAsset = assets.find((asset) => asset.id === selectedAssetId) ?? null;
  const handleAssets = useCallback((items: Asset[]) => {
    setAssets(items);
    setSelectedAssetId((current) => current && items.some((item) => item.id === current) ? current : items[0]?.id ?? null);
  }, []);
  const selectPage = useCallback((pageOrder: number, clearInspection = true) => {
    const asset = assets.find((item) => item.page_order === pageOrder);
    if (asset) {
      setSelectedAssetId(asset.id);
      if (clearInspection) setInspection(null);
    }
  }, [assets]);

  const refreshStoryInput = useCallback(async (preserveStory = false) => {
    try {
      const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/story-input`, { cache: "no-store" });
      if (!response.ok) throw new Error();
      const ready = (await response.json()).status === "ready";
      setStoryInputStatus(ready ? "ready" : "blocked");
      setStoryError("");
      if (!ready && !preserveStory) setStoryState("STORY_INPUT_BLOCKED");
      return ready;
    } catch {
      setStoryInputStatus("blocked");
      if (!preserveStory) setStoryState("STORY_ERROR");
      setStoryError("Không thể phân tích câu chuyện lúc này.");
      return false;
    }
  }, [projectId]);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch(`http://127.0.0.1:8000/projects/${projectId}/story-input`, { cache: "no-store" }),
      fetch(`http://127.0.0.1:8000/projects/${projectId}/story-analysis`, { cache: "no-store" }),
      fetch(`http://127.0.0.1:8000/projects/${projectId}/story-review`, { cache: "no-store" }),
      fetch(`http://127.0.0.1:8000/projects/${projectId}/short-script`, { cache: "no-store" }),
    ])
      .then(async ([inputResponse, storyResponse, reviewResponse, scriptResponse]) => {
        if (!inputResponse.ok || !storyResponse.ok) throw new Error();
        return Promise.all([
          inputResponse.json(),
          storyResponse.json(),
          reviewResponse.ok ? reviewResponse.json() : Promise.resolve(null),
          scriptResponse.ok ? scriptResponse.json() : Promise.resolve(null),
        ]);
      })
      .then(([input, persisted, review, restoredScript]: [Record<string, unknown>, PersistedStory, StoryReview | null, ScriptRecord | null]) => {
        if (!active) return;
        const ready = input.status === "ready";
        setStoryInputStatus(ready ? "ready" : "blocked");
        setStoryError("");
        if (review?.final_story && isReliabilityResult(review.final_story)) {
          const restoredState = storyReviewUiState(review);
          setStory(review.final_story);
          setStoryReview(review);
          setStoryState(restoredState);
          setLastStableStoryState(restoredState);
        } else if (persisted.result && isReliabilityResult(persisted.result)) {
          const restoredState: StoryUiState = persisted.stale
            ? "STORY_STALE"
            : persisted.status === "ready" ? "STORY_READY" : "STORY_PARTIAL";
          setStory(persisted.result);
          setStoryState(restoredState);
          setLastStableStoryState(restoredState);
        } else {
          setStoryState(ready ? "STORY_NOT_ANALYZED" : "STORY_INPUT_BLOCKED");
          setLastStableStoryState(ready ? "STORY_NOT_ANALYZED" : "STORY_INPUT_BLOCKED");
        }
        if (restoredScript?.final_script) {
          setScriptRecord(restoredScript);
          setScript(restoredScript.final_script);
          if (restoredScript.style) setStyle(restoredScript.style);
        } else {
          setScriptRecord(restoredScript);
        }
      })
      .catch(() => {
        if (!active) return;
        setStoryInputStatus("blocked");
        setStoryState("STORY_ERROR");
        setStoryError("Không thể phân tích câu chuyện lúc này.");
      });
    return () => { active = false; };
  }, [projectId]);

  const loadStory = useCallback(async (verifiedReady = false) => {
    if (!verifiedReady && storyInputStatus !== "ready") return;
    setStoryState("STORY_LOADING"); setStoryError("");
    setScriptRecord((current) => current ? { ...current, stale: true, status: "stale", script_approved: false } : current);
    try {
      const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/story-analysis`, { method: "POST" });
      if (!response.ok) throw new Error();
      const result: unknown = await response.json();
      if (!isReliabilityResult(result)) throw new Error("Invalid Story Analysis response");
      const reviewResponse = await fetch(`http://127.0.0.1:8000/projects/${projectId}/story-review`, { cache: "no-store" });
      const review = reviewResponse.ok ? await reviewResponse.json() as StoryReview : null;
      const displayed = review?.final_story && isReliabilityResult(review.final_story) ? review.final_story : result;
      setStory(displayed);
      setStoryReview(review);
      const nextState: StoryUiState = review
        ? storyReviewUiState(review)
        : isStoryScriptUsable(result) ? "STORY_READY" : "STORY_PARTIAL";
      setStoryState(nextState);
      setLastStableStoryState(nextState);
    } catch {
      setStoryState(story ? lastStableStoryState : "STORY_ERROR");
      setStoryError(story ? "Không thể cập nhật câu chuyện lúc này." : "Không thể phân tích câu chuyện lúc này.");
    }
  }, [lastStableStoryState, projectId, story, storyInputStatus]);

  const inspectSource = useCallback(async (
    source: Source,
    selection: { eventId?: string; unresolvedKey?: string; kind: "event" | "unresolved" },
  ) => {
    const asset = assets.find((item) => item.id === source.asset_id);
    if (!asset) return;
    setSelectedAssetId(asset.id);
    const regionIds = [...new Set(source.region_ids)];
    const responses = await Promise.all(
      regionIds.map(async (regionId) => {
        const response = await fetch(`http://127.0.0.1:8000/assets/${source.asset_id}/regions/${regionId}`);
        return response.ok ? await response.json() as RegionEvidence : null;
      }),
    );
    setInspection({
      assetId: asset.id,
      regionIds,
      regions: responses.filter((item): item is RegionEvidence => item !== null),
      ...selection,
    });
  }, [assets]);

  const markStoryStale = useCallback(() => {
    if (!story) return;
    setStoryState("STORY_STALE");
    setLastStableStoryState("STORY_STALE");
    setScriptRecord((current) => current ? { ...current, stale: true, status: "stale", script_approved: false } : current);
  }, [story]);

  const applyStoryReview = useCallback((review: StoryReview) => {
    setStoryReview(review);
    setStory(review.final_story);
    const nextState = storyReviewUiState(review);
    setStoryState(nextState);
    setLastStableStoryState(nextState);
    setScriptRecord((current) => current && (
      !review.story_approved
      || current.source_story_fingerprint !== review.final_story_fingerprint
      || current.source_story_approved_at !== review.approved_at
    ) ? { ...current, stale: true, status: "stale", script_approved: false } : current);
  }, []);

  const saveEventEdit = useCallback(async (eventId: string, text: string) => {
    if (!storyReview) throw new Error("Story review is not available");
    const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/story-review/events/${encodeURIComponent(eventId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source_revision: storyReview.source_revision }),
    });
    if (!response.ok) throw new Error();
    applyStoryReview(await response.json() as StoryReview);
  }, [applyStoryReview, projectId, storyReview]);

  const resolveEvidence = useCallback(async (item: UnresolvedEvidence, action: "add" | "dismiss", text?: string) => {
    if (!storyReview) throw new Error("Story review is not available");
    const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/story-review/unresolved/${encodeURIComponent(item.asset_id)}/${item.region_id}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_revision: storyReview.source_revision, ...(action === "add" ? { text } : {}) }),
    });
    if (!response.ok) throw new Error();
    applyStoryReview(await response.json() as StoryReview);
  }, [applyStoryReview, projectId, storyReview]);

  const approveStory = useCallback(async () => {
    const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/story-review/approve`, { method: "POST" });
    if (!response.ok) throw new Error();
    applyStoryReview(await response.json() as StoryReview);
  }, [applyStoryReview, projectId]);

  const storyUsable = Boolean(storyReview?.final_story_ready && storyReview.story_approved && !storyReview.stale);
  const scriptLockReason = storyState === "STORY_STALE"
    ? "Câu chuyện đã thay đổi và cần phân tích lại."
    : storyReview?.final_story_ready
      ? "Hãy duyệt câu chuyện trước khi tạo kịch bản."
      : "ComicAI cần bạn kiểm tra thêm nội dung trước.";

  async function generateScript() {
    if (!storyUsable) return;
    setScriptLoading(true); setScriptError("");
    try {
      const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/short-script`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ style }) });
      if (!response.ok) throw new Error();
      const result = (await response.json()) as ScriptRecord;
      if (!result.final_script) throw new Error();
      setScriptRecord(result);
      setScript(result.final_script);
    } catch { setScriptError("ComicAI chưa có đủ thông tin chắc chắn để tạo kịch bản. Hãy kiểm tra phần Câu chuyện."); }
    finally { setScriptLoading(false); }
  }

  const saveScriptSegment = useCallback(async (segmentId: string, text: string) => {
    const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/short-script/segments/${encodeURIComponent(segmentId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error();
    const result = await response.json() as ScriptRecord;
    setScriptRecord(result);
    setScript(result.final_script);
  }, [projectId]);

  const approveScript = useCallback(async () => {
    const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/short-script/approve`, { method: "POST" });
    if (!response.ok) throw new Error();
    const result = await response.json() as ScriptRecord;
    setScriptRecord(result);
    setScript(result.final_script);
  }, [projectId]);

  const eventPages = useMemo(() => {
    const result = new Map<string, number[]>();
    for (const event of story?.grounded_result.events ?? []) {
      result.set(event.id, [...new Set(event.claims.flatMap((claim) => claim.sources.map((source) => source.page_order)))]);
    }
    return result;
  }, [story]);

  return <div className="grid border-x border-white/[0.08] lg:h-auto lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(220px,21%)_minmax(0,1fr)_minmax(300px,27%)] lg:grid-rows-2 lg:overflow-hidden">
    <aside className="flex h-full min-h-0 flex-col overflow-hidden border-b border-white/[0.08] bg-[#0f0f12] lg:row-span-2 lg:border-b-0 lg:border-r">
      <AssetUploader projectId={projectId} selectedAssetId={selectedAssetId} onSelectAsset={(assetId) => { setSelectedAssetId(assetId); setInspection(null); }} onAssetsChange={handleAssets} onSourceChanged={markStoryStale} refreshToken={assetRefreshToken} />
    </aside>

    <section className="flex min-h-[45vh] min-w-0 flex-col overflow-hidden border-b border-white/[0.08] bg-[#08080a] lg:col-start-2 lg:row-start-1 lg:min-h-0">
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden p-4 lg:p-6">
          {selectedAsset ? <PagePreview asset={selectedAsset} inspection={inspection?.assetId === selectedAsset.id ? inspection : null} onClear={() => setInspection(null)} /> : <div className="text-sm text-white/30">Chọn một trang để xem trước</div>}
        </div>
        <div className="flex h-12 shrink-0 items-center gap-4 border-t border-white/[0.08] bg-[#0d0d10] px-5 text-white/25">
          <button disabled className="flex h-7 w-7 items-center justify-center rounded-md border border-white/10 text-xs" aria-label="Phát video — chưa khả dụng">▶</button>
          <div className="h-1 flex-1 rounded-full bg-white/[0.08]" />
          <span className="font-mono text-xs">00:00</span>
        </div>
      </div>
    </section>

    <aside className="flex min-h-[560px] min-w-0 flex-col overflow-hidden border-t border-white/[0.08] bg-[#101013] lg:col-start-3 lg:row-start-1 lg:min-h-0 lg:border-b lg:border-l lg:border-t-0">
      <nav className="flex h-12 items-center border-b border-white/[0.08] px-5" aria-label="Bảng nội dung">
        {([['story', 'Câu chuyện'], ['script', 'Kịch bản']] as const).map(([id, label]) => <button key={id} onClick={() => setRightTab(id)} className={`relative mr-6 text-sm transition ${rightTab === id ? "text-white after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-violet-500" : "text-white/35 hover:text-white/65"}`}>{label}</button>)}
        <ReviewQueue projectId={projectId} onSelectItem={(item: ReviewItem) => { setSelectedAssetId(item.asset_id); setInspection(null); }} onVerified={() => { setAssetRefreshToken((current) => current + 1); markStoryStale(); void refreshStoryInput(true); }} />
      </nav>
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {rightTab === "story" ? <StoryPanel story={story} review={storyReview} state={storyState} stableState={lastStableStoryState} canAnalyze={storyInputStatus === "ready"} readinessLoading={storyInputStatus === "loading"} error={storyError} inspection={inspection} onAnalyze={() => void loadStory()} onInspectSource={inspectSource} onSaveEvent={saveEventEdit} onResolveEvidence={resolveEvidence} onApproveStory={approveStory} /> : <ScriptPanel storyUsable={storyUsable} lockReason={scriptLockReason} style={style} onStyle={setStyle} script={script} record={scriptRecord} loading={scriptLoading} error={scriptError} eventPages={eventPages} onGenerate={() => void generateScript()} onSaveSegment={saveScriptSegment} onApprove={approveScript} onSelectPage={selectPage} />}
      </div>
    </aside>
    <section className="flex min-h-[40vh] min-w-0 flex-col bg-[#0c0c0f] lg:col-span-2 lg:col-start-2 lg:row-start-2 lg:min-h-0">
      <div className="flex h-10 items-center border-b border-white/[0.06] px-4">
        <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-white/20">Công cụ chỉnh sửa</span>
      </div>
    </section>
  </div>;
}

function PagePreview({ asset, inspection, onClear }: { asset: Asset; inspection: SourceInspection | null; onClear: () => void }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [viewport, setViewport] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const update = () => setViewport({ width: container.clientWidth, height: container.clientHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);
  const imageSize = inspection?.regions[0]?.image_size;
  const scale = imageSize
    ? Math.min(viewport.width / imageSize.width, viewport.height / imageSize.height)
    : 0;
  const imageWidth = imageSize ? imageSize.width * scale : 0;
  const imageHeight = imageSize ? imageSize.height * scale : 0;
  const offsetX = (viewport.width - imageWidth) / 2;
  const offsetY = (viewport.height - imageHeight) / 2;
  return <div ref={containerRef} className="relative h-full w-full" onClick={() => inspection && onClear()}>
    <Image src={asset.url} alt={asset.filename} fill unoptimized sizes="(max-width: 1024px) 100vw, 55vw" className="object-contain" />
    {inspection?.regions.map((region) => {
      const [left, top, right, bottom] = region.bbox;
      return <span key={region.region_id} aria-label={`Vùng nguồn ${region.region_id}`} className="pointer-events-none absolute rounded border-2 border-violet-400 bg-violet-500/20 shadow-[0_0_0_2px_rgba(0,0,0,0.35),0_0_18px_rgba(139,92,246,0.45)]" style={{ left: offsetX + left * scale, top: offsetY + top * scale, width: Math.max(2, (right - left) * scale), height: Math.max(2, (bottom - top) * scale) }} />;
    })}
    {inspection && <button onClick={(event) => { event.stopPropagation(); onClear(); }} className="absolute right-3 top-3 rounded-lg border border-violet-300/30 bg-black/70 px-3 py-1.5 text-xs text-violet-100 backdrop-blur-sm">Đóng đánh dấu</button>}
  </div>;
}

function StoryPanel({ story, review, state, stableState, canAnalyze, readinessLoading, error, inspection, onAnalyze, onInspectSource, onSaveEvent, onResolveEvidence, onApproveStory }: { story: Reliability | null; review: StoryReview | null; state: StoryUiState; stableState: StoryUiState; canAnalyze: boolean; readinessLoading: boolean; error: string; inspection: SourceInspection | null; onAnalyze: () => void; onInspectSource: (source: Source, selection: { eventId?: string; unresolvedKey?: string; kind: "event" | "unresolved" }) => void; onSaveEvent: (eventId: string, text: string) => Promise<void>; onResolveEvidence: (item: UnresolvedEvidence, action: "add" | "dismiss", text?: string) => Promise<void>; onApproveStory: () => Promise<void> }) {
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [approvalError, setApprovalError] = useState("");
  const loading = state === "STORY_LOADING";
  const displayState = loading && story ? stableState : state;
  const safeEvents = story?.grounded_result.events.filter((event) => event.script_ready === true && !event.unsupported_claims?.length) ?? [];
  const byId = new Map(safeEvents.map((event) => [event.id, event]));
  const mainEvents = story?.grounded_result.main_progression.map((id) => byId.get(id)).filter((event): event is StoryEvent => Boolean(event)) ?? [];
  const supportingEvents = safeEvents.filter((event) => event.story_role === "supporting_context");
  const unresolved = story?.coverage.important_uncovered_regions ?? [];
  const selectedUnresolvedIndex = unresolved.findIndex((item) => inspection?.unresolvedKey === `${item.asset_id}-${item.region_id}`);
  const inspectUnresolved = (item: UnresolvedEvidence) => onInspectSource({ asset_id: item.asset_id, page_order: item.page_order, region_ids: [item.region_id] }, { unresolvedKey: `${item.asset_id}-${item.region_id}`, kind: "unresolved" });
  const resolveAndAdvance = async (item: UnresolvedEvidence, action: "add" | "dismiss", text?: string) => {
    const index = unresolved.findIndex((candidate) => candidate.asset_id === item.asset_id && candidate.region_id === item.region_id);
    const next = unresolved[index + 1] ?? unresolved[index - 1];
    await onResolveEvidence(item, action, text);
    if (next) inspectUnresolved(next);
  };
  const progress = review?.unresolved_total ? Math.round((review.resolved_by_human / review.unresolved_total) * 100) : 100;
  return <div className="pb-2">
    <div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-medium uppercase tracking-[0.18em] text-white/30">Câu chuyện AI hiểu</p>{story && <><p className={`mt-2 text-xs ${displayState === "STORY_APPROVED" || displayState === "STORY_AWAITING_APPROVAL" ? "text-emerald-400" : displayState === "STORY_STALE" || displayState === "STORY_APPROVAL_INVALID" ? "text-violet-300" : "text-amber-300"}`}>{displayState === "STORY_APPROVED" ? "✓ Câu chuyện đã được duyệt" : displayState === "STORY_APPROVAL_INVALID" ? "↻ Câu chuyện đã thay đổi, cần duyệt lại" : displayState === "STORY_AWAITING_APPROVAL" ? "✓ Đã xử lý toàn bộ nội dung" : displayState === "STORY_REVIEWING" ? `◐ ${review?.resolved_by_human ?? 0}/${review?.unresolved_total ?? 0} đoạn đã kiểm tra` : displayState === "STORY_READY" ? "✓ Câu chuyện đã được phân tích" : displayState === "STORY_STALE" ? "↻ Câu chuyện cần phân tích lại" : "⚠ Câu chuyện còn nội dung cần kiểm tra"}</p><p className="mt-1 text-[11px] text-white/30">{mainEvents.length} sự kiện · {review?.resolved_by_human ?? 0}/{review?.unresolved_total ?? unresolved.length} đoạn đã kiểm tra</p></>}</div>{(story || canAnalyze) && <button onClick={onAnalyze} disabled={loading || !canAnalyze} className="shrink-0 rounded-lg border border-violet-400/20 px-2.5 py-1.5 text-xs text-violet-200 hover:bg-violet-500/10 disabled:opacity-50">{loading ? "Đang phân tích…" : story ? "Phân tích lại" : "✦ Phân tích câu chuyện"}</button>}</div>
    {story && review && review.unresolved_total > 0 && <div className="mt-3"><div className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]"><div className="h-full rounded-full bg-violet-500 transition-all" style={{ width: `${progress}%` }} /></div></div>}
    {loading && <div aria-label="ComicAI đang phân tích câu chuyện" className="mt-4 rounded-lg border border-violet-400/15 bg-violet-500/[0.05] p-3 text-xs text-violet-200">ComicAI đang cập nhật câu chuyện. Bản gần nhất vẫn được giữ cho đến khi hoàn tất.</div>}
    {state === "STORY_ERROR" && <div className="mt-5 rounded-lg border border-red-400/15 bg-red-400/[0.06] p-3"><p className="text-sm leading-6 text-red-100">{error || "Không thể phân tích câu chuyện lúc này."}</p><details className="mt-2 text-[10px] text-white/25"><summary className="cursor-pointer">Chi tiết dành cho nhà phát triển</summary><p className="mt-1">Yêu cầu Story Analysis không thành công.</p></details></div>}
    {story && error && state !== "STORY_ERROR" && <div className="mt-4 rounded-lg border border-red-400/15 bg-red-400/[0.05] p-3 text-sm text-red-100">{error}</div>}
    {!story && !loading && state !== "STORY_ERROR" && <div className="mt-12 text-center"><h3 className="text-sm font-medium text-white/70">Câu chuyện</h3><p className="mx-auto mt-2 max-w-xs text-sm leading-6 text-white/30">{readinessLoading ? "Đang kiểm tra các trang truyện..." : state === "STORY_INPUT_BLOCKED" ? "ComicAI chưa thể phân tích câu chuyện. Hãy kiểm tra các trang truyện." : "ComicAI sẽ đọc các trang đã xử lý và tóm tắt diễn biến chính của câu chuyện."}</p>{canAnalyze && state === "STORY_NOT_ANALYZED" && <button onClick={onAnalyze} className="mt-5 rounded-lg bg-violet-500 px-4 py-2.5 text-sm font-medium hover:bg-violet-400">✦ Phân tích câu chuyện</button>}</div>}
    {story && state !== "STORY_ERROR" && <>
      {review?.final_story_ready && <section className="mt-5 rounded-xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4"><p className="text-xs font-medium text-emerald-200">Câu chuyện hoàn chỉnh</p><p className="mt-1 text-xs text-white/35">Kiểm tra các sự kiện và nguồn trước khi duyệt.</p>{!review.story_approved && <button disabled={approvalLoading || state === "STORY_STALE"} onClick={async () => { setApprovalLoading(true); setApprovalError(""); try { await onApproveStory(); } catch { setApprovalError("Không thể duyệt câu chuyện lúc này."); } finally { setApprovalLoading(false); } }} className="mt-3 w-full rounded-lg bg-emerald-500 px-3 py-2.5 text-sm font-medium text-black hover:bg-emerald-400 disabled:opacity-50">{approvalLoading ? "Đang duyệt…" : "✓ Duyệt câu chuyện"}</button>}{review.story_approved && <p className="mt-3 text-sm text-emerald-300">✓ Câu chuyện đã được duyệt. Kịch bản đã mở khóa.</p>}{approvalError && <p className="mt-2 text-xs text-red-200">{approvalError}</p>}</section>}
      <div className="mt-6">{mainEvents.map((event, index) => <StoryEventCard key={event.id} event={event} index={index} selected={inspection?.eventId === event.id} onInspectSource={onInspectSource} onSave={onSaveEvent} disabled={state === "STORY_STALE"} />)}</div>
      {supportingEvents.length > 0 && <section className="mt-7"><h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-white/30">Bối cảnh</h3><div className="mt-2">{supportingEvents.map((event, index) => <StoryEventCard key={event.id} event={event} index={index} selected={inspection?.eventId === event.id} onInspectSource={onInspectSource} onSave={onSaveEvent} disabled={state === "STORY_STALE"} compact />)}</div></section>}
      {unresolved.length > 0 && <section className="mt-7 rounded-xl border border-amber-300/10 bg-amber-300/[0.035] p-4"><details open><summary className="cursor-pointer list-none"><div className="flex items-center justify-between gap-3"><div><h3 className="text-sm font-medium text-amber-100">⚠ Nội dung chưa được sử dụng</h3><p className="mt-1 text-xs text-white/30">Hãy quyết định rõ từng đoạn trước khi hoàn tất câu chuyện.</p></div><span className="rounded-full bg-amber-300/10 px-2 py-1 text-xs text-amber-200">{unresolved.length} đoạn</span></div></summary>{selectedUnresolvedIndex >= 0 && <div className="mt-3 flex justify-end gap-2"><button disabled={selectedUnresolvedIndex <= 0} onClick={() => inspectUnresolved(unresolved[selectedUnresolvedIndex - 1])} className="rounded border border-white/10 px-2.5 py-1 text-xs text-white/45 disabled:opacity-25">Trước</button><button disabled={selectedUnresolvedIndex >= unresolved.length - 1} onClick={() => inspectUnresolved(unresolved[selectedUnresolvedIndex + 1])} className="rounded border border-white/10 px-2.5 py-1 text-xs text-white/45 disabled:opacity-25">Tiếp</button></div>}<div className="mt-4 space-y-2">{unresolved.map((item) => <UnresolvedCard key={`${item.asset_id}-${item.region_id}`} item={item} selected={inspection?.unresolvedKey === `${item.asset_id}-${item.region_id}`} disabled={state === "STORY_STALE"} onInspect={onInspectSource} onResolve={resolveAndAdvance} />)}</div></details></section>}
      <details className="mt-5 border-t border-white/[0.06] pt-3 text-[10px] text-white/25"><summary className="cursor-pointer hover:text-white/45">Chi tiết dành cho nhà phát triển</summary><div className="mt-2 space-y-1"><p>Review: {review?.status ?? "—"} · Final ready: {String(review?.final_story_ready ?? false)} · Approved: {String(review?.story_approved ?? false)}</p><p>Source revision: {review?.source_revision ?? "—"} · Review revision: {review?.review_source_revision ?? "—"}</p><p>Fingerprint: {review?.final_story_fingerprint ?? "—"}</p><p>Approved fingerprint: {review?.approved_story_fingerprint ?? "—"} · At: {review?.approved_at ?? "—"}</p><p>Human events: {review?.human_added_event_ids.join(", ") || "—"}</p>{inspection && <p>Selected region IDs: {inspection.regionIds.join(", ") || "—"}</p>}</div></details>
    </>}
  </div>;
}

function StoryEventCard({ event, index, selected, onInspectSource, onSave, disabled, compact = false }: { event: StoryEvent; index: number; selected: boolean; onInspectSource: (source: Source, selection: { eventId?: string; kind: "event" | "unresolved" }) => void; onSave: (eventId: string, text: string) => Promise<void>; disabled: boolean; compact?: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(event.summary || event.claims.map((claim) => claim.text).join(" "));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const grouped = new Map<string, Source>();
  for (const source of event.claims.flatMap((claim) => claim.sources)) {
    const key = `${source.asset_id}-${source.page_order}`;
    const current = grouped.get(key);
    grouped.set(key, current ? { ...current, region_ids: [...new Set([...current.region_ids, ...source.region_ids])] } : { ...source, region_ids: [...new Set(source.region_ids)] });
  }
  const sources = [...grouped.values()];
  const label = event.provenance === "human_added" ? "+ Người dùng thêm" : event.provenance === "human_edited" ? "✎ Đã chỉnh sửa" : "✓ Đã xác minh";
  return <article className={`border-b px-2 transition ${selected ? "border-violet-400/30 bg-violet-500/[0.07]" : "border-white/[0.08]"} ${compact ? "py-3" : "py-5 first:pt-1"}`}><div className="flex gap-3"><span className="mt-0.5 text-xs font-semibold text-violet-300">{String(index + 1).padStart(2, "0")}</span><div className="min-w-0 flex-1">{editing ? <div><textarea value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={2000} rows={4} className="w-full resize-y rounded-lg border border-violet-400/30 bg-black/25 p-3 text-sm leading-6 text-white/80 outline-none focus:border-violet-400" />{saveError && <p className="mt-2 text-xs text-red-200">{saveError}</p>}<div className="mt-2 flex gap-2"><button disabled={saving || !draft.trim()} onClick={async () => { setSaving(true); setSaveError(""); try { await onSave(event.id, draft); setEditing(false); } catch { setSaveError("Không thể lưu chỉnh sửa lúc này."); } finally { setSaving(false); } }} className="rounded-md bg-violet-500 px-3 py-1.5 text-xs font-medium disabled:opacity-50">{saving ? "Đang lưu…" : "Lưu"}</button><button disabled={saving} onClick={() => { setDraft(event.summary || event.claims.map((claim) => claim.text).join(" ")); setSaveError(""); setEditing(false); }} className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-white/50">Hủy</button></div></div> : <p className="text-sm leading-6 text-white/75">{event.summary || event.claims.map((claim) => claim.text).join(" ")}</p>}<div className="mt-2 flex items-center justify-between gap-3"><span className="text-[11px] text-white/35">{label}</span>{!editing && <button disabled={disabled} onClick={() => { setDraft(event.summary || event.claims.map((claim) => claim.text).join(" ")); setEditing(true); }} className="text-[11px] text-violet-300 hover:text-violet-200 disabled:opacity-30">Chỉnh sửa</button>}</div><div className="mt-3 flex flex-wrap gap-1.5">{sources.map((source) => <button key={`${source.asset_id}-${source.page_order}`} onClick={() => void onInspectSource(source, { eventId: event.id, kind: "event" })} className="rounded border border-white/10 px-2 py-1 text-[11px] text-white/35 hover:border-violet-400/30 hover:text-violet-200">Nguồn · Trang {String(source.page_order).padStart(2, "0")}</button>)}</div><details className="mt-3 text-xs text-white/35"><summary className="cursor-pointer hover:text-white/60">Xem thông tin nguồn</summary><ul className="mt-2 space-y-2 border-l border-white/10 pl-3">{event.claims.map((claim) => <li key={claim.id} className="leading-5">{claim.text}</li>)}</ul></details></div></div></article>;
}

function UnresolvedCard({ item, selected, disabled, onInspect, onResolve }: { item: UnresolvedEvidence; selected: boolean; disabled: boolean; onInspect: (source: Source, selection: { unresolvedKey?: string; kind: "event" | "unresolved" }) => void; onResolve: (item: UnresolvedEvidence, action: "add" | "dismiss", text?: string) => Promise<void> }) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState(item.evidence_text);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const inspect = () => onInspect({ asset_id: item.asset_id, page_order: item.page_order, region_ids: [item.region_id] }, { unresolvedKey: `${item.asset_id}-${item.region_id}`, kind: "unresolved" });
  const dismiss = async () => {
    inspect();
    if (!window.confirm("Xác nhận đoạn này không quan trọng đối với câu chuyện?")) return;
    setSaving(true); setError("");
    try { await onResolve(item, "dismiss"); } catch { setError("Không thể lưu quyết định lúc này."); } finally { setSaving(false); }
  };
  return <div onClick={inspect} className={`rounded-lg border p-3 text-left ${selected ? "border-violet-400/45 bg-violet-500/10" : "border-white/[0.07] bg-black/10 hover:border-violet-400/25 hover:bg-violet-500/[0.04]"}`}><span className="text-[11px] text-violet-300">Trang {item.page_order}</span><p className="mt-1.5 text-sm leading-5 text-white/65">“{item.evidence_text}”</p>{selected && <p className="mt-2 text-[11px] text-amber-200/70">ComicAI chưa sử dụng đoạn này trong câu chuyện.</p>}{adding ? <div className="mt-3" onClick={(event) => event.stopPropagation()}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={2000} rows={3} className="w-full resize-y rounded-lg border border-violet-400/30 bg-black/30 p-2.5 text-sm text-white/75 outline-none focus:border-violet-400" />{error && <p className="mt-2 text-xs text-red-200">{error}</p>}<div className="mt-2 flex gap-2"><button disabled={saving || !draft.trim()} onClick={async () => { setSaving(true); setError(""); try { await onResolve(item, "add", draft); setAdding(false); } catch { setError("Không thể thêm đoạn này lúc này."); } finally { setSaving(false); } }} className="rounded-md bg-violet-500 px-3 py-1.5 text-xs disabled:opacity-50">{saving ? "Đang lưu…" : "Lưu"}</button><button disabled={saving} onClick={() => { setAdding(false); setDraft(item.evidence_text); setError(""); }} className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-white/50">Hủy</button></div></div> : <div className="mt-3 flex flex-wrap gap-2" onClick={(event) => event.stopPropagation()}><button disabled={disabled || saving} onClick={() => { inspect(); setAdding(true); }} className="rounded-md border border-violet-400/25 px-2.5 py-1.5 text-xs text-violet-200 disabled:opacity-30">Thêm vào câu chuyện</button><button disabled={disabled || saving} onClick={() => void dismiss()} className="rounded-md border border-white/10 px-2.5 py-1.5 text-xs text-white/45 disabled:opacity-30">Không quan trọng</button></div>}{error && !adding && <p className="mt-2 text-xs text-red-200">{error}</p>}</div>;
}

function ScriptPanel({ storyUsable, lockReason, style, onStyle, script, record, loading, error, eventPages, onGenerate, onSaveSegment, onApprove, onSelectPage }: { storyUsable: boolean; lockReason: string; style: string; onStyle: (value: string) => void; script: ScriptResult | null; record: ScriptRecord | null; loading: boolean; error: string; eventPages: Map<string, number[]>; onGenerate: () => void; onSaveSegment: (segmentId: string, text: string) => Promise<void>; onApprove: () => Promise<void>; onSelectPage: (page: number) => void }) {
  const labels: Record<string, string> = { hook: "Mở đầu", setup: "Bối cảnh", development: "Diễn biến", payoff: "Cao trào", ending: "Kết" };
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [approvalError, setApprovalError] = useState("");
  const styleLabels: Record<string, string> = { natural: "Tự nhiên", funny: "Hài hước", emotional: "Cảm xúc", dramatic: "Kịch tính" };
  const statusText = record?.status === "approved" ? "✓ Kịch bản đã được duyệt" : record?.status === "edited" ? "✎ Kịch bản đã được chỉnh sửa" : record?.status === "stale" ? "↻ Story đã thay đổi, hãy tạo lại kịch bản" : script ? "✓ Kịch bản đã được tạo" : "Story đã sẵn sàng. Hãy tạo kịch bản.";
  return <div><p className="text-[11px] font-medium uppercase tracking-[0.18em] text-white/30">Kịch bản video</p>{!storyUsable && <div className="mt-5 rounded-xl border border-amber-300/15 bg-amber-300/[0.05] p-4"><p className="text-sm leading-6 text-amber-100">{lockReason}</p><p className="mt-1 text-xs text-white/30">Bạn vẫn có thể xem kịch bản cũ, nhưng không thể duyệt hoặc sử dụng khi Story đang khóa.</p></div>}{storyUsable && <><p className="mt-4 text-xs text-white/35">Phong cách</p><div className="mt-2 flex flex-wrap gap-1.5">{Object.entries(styleLabels).map(([value,label]) => <button key={value} onClick={() => onStyle(value)} className={`rounded-md px-2.5 py-1.5 text-xs ${style === value ? "bg-violet-500/20 text-violet-200 ring-1 ring-violet-400/35" : "border border-white/10 text-white/35 hover:text-white"}`}>{label}</button>)}</div><button onClick={onGenerate} disabled={loading} className="mt-4 w-full rounded-lg bg-violet-500 py-2.5 text-sm font-medium hover:bg-violet-400 disabled:opacity-50">{loading ? "ComicAI đang viết kịch bản..." : script ? "✦ Tạo lại kịch bản" : "✦ Tạo kịch bản"}</button></>}
    {error && <p className="mt-4 text-sm leading-6 text-amber-200">{error}</p>}
    <p className={`mt-4 text-xs ${record?.status === "approved" ? "text-emerald-300" : record?.status === "stale" ? "text-violet-300" : "text-white/40"}`}>{statusText}</p>
    {script && <><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-white/30"><span>{styleLabels[record?.style ?? style] ?? style}</span><span>{script.summary.word_count} từ</span><span>~{Math.max(1, Math.ceil((script.summary.estimated_duration_seconds ?? 0) / 60))} phút ước tính</span></div><div className="mt-2">{script.segments.map((segment) => <ScriptSegmentCard key={segment.id} segment={segment} label={labels[segment.type]} pages={[...new Set(segment.source_event_ids.flatMap((id) => eventPages.get(id) ?? []))]} disabled={Boolean(record?.stale)} onSave={onSaveSegment} onSelectPage={onSelectPage} />)}</div><button onClick={async () => { setApprovalLoading(true); setApprovalError(""); try { await onApprove(); } catch { setApprovalError("Không thể duyệt kịch bản lúc này."); } finally { setApprovalLoading(false); } }} disabled={!storyUsable || Boolean(record?.stale) || record?.script_approved || approvalLoading} className="mt-5 w-full rounded-lg border border-emerald-400/25 py-2.5 text-sm text-emerald-300 disabled:opacity-45">{record?.script_approved ? "✓ Kịch bản đã được duyệt" : approvalLoading ? "Đang duyệt…" : "✓ Duyệt kịch bản"}</button>{approvalError && <p className="mt-2 text-xs text-red-200">{approvalError}</p>}<details className="mt-4 text-[10px] text-white/20"><summary className="cursor-pointer">Chi tiết nguồn</summary><p className="mt-2">Script fingerprint: {record?.script_fingerprint ?? "—"}</p>{script.segments.map((segment) => <p key={segment.id}>{labels[segment.type]} · events: {segment.source_event_ids.join(", ")} · claims: {segment.source_claim_ids.join(", ")}</p>)}</details></>}
  </div>;
}

function ScriptSegmentCard({ segment, label, pages, disabled, onSave, onSelectPage }: { segment: Segment; label: string; pages: number[]; disabled: boolean; onSave: (segmentId: string, text: string) => Promise<void>; onSelectPage: (page: number) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(segment.text);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  return <article className="border-b border-white/[0.08] py-4"><div className="flex items-center justify-between gap-3"><span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-violet-300">{label}</span><div className="flex items-center gap-3"><span className="text-[10px] text-white/25">{segment.provenance === "human_edited" ? "Người dùng sửa" : "AI tạo"}</span>{!editing && <button disabled={disabled} onClick={() => { setDraft(segment.text); setEditing(true); }} className="text-[11px] text-violet-300 disabled:opacity-30">Chỉnh sửa</button>}</div></div>{editing ? <div className="mt-2"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={4000} rows={4} className="w-full resize-y rounded-lg border border-violet-400/30 bg-[#0a0a0c] p-3 text-sm leading-6 text-white/75 outline-none focus:border-violet-400" />{saveError && <p className="mt-2 text-xs text-red-200">{saveError}</p>}<div className="mt-2 flex gap-2"><button disabled={saving || !draft.trim()} onClick={async () => { setSaving(true); setSaveError(""); try { await onSave(segment.id, draft); setEditing(false); } catch { setSaveError("Không thể lưu đoạn kịch bản lúc này."); } finally { setSaving(false); } }} className="rounded-md bg-violet-500 px-3 py-1.5 text-xs disabled:opacity-50">{saving ? "Đang lưu…" : "Lưu"}</button><button disabled={saving} onClick={() => { setDraft(segment.text); setSaveError(""); setEditing(false); }} className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-white/45">Hủy</button></div></div> : <p className="mt-2 text-sm leading-6 text-white/70">{segment.text}</p>}{pages.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{pages.map((page) => <button key={page} onClick={() => onSelectPage(page)} className="text-[11px] text-white/30 hover:text-violet-300">Nguồn · Trang {String(page).padStart(2, "0")}</button>)}</div>}</article>;
}
