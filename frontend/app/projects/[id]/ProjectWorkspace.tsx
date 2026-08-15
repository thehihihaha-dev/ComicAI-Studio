"use client";

import Image from "next/image";
import { useCallback, useMemo, useState } from "react";
import AssetUploader, { type Asset } from "./AssetUploader";

type RightTab = "story" | "script";
type Source = { asset_id: string; page_order: number; region_ids: number[] };
type Claim = { id: string; text: string; sources: Source[] };
type StoryEvent = { id: string; summary?: string; claims: Claim[] };
type Reliability = { coverage: { unresolved_regions: number }; grounded_result: { events: StoryEvent[]; main_progression: string[] } };
type Segment = { id: string; type: string; text: string; source_event_ids: string[]; source_claim_ids: string[] };
type ScriptResult = { segments: Segment[]; summary: { word_count: number } };

export default function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [rightTab, setRightTab] = useState<RightTab>("story");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [story, setStory] = useState<Reliability | null>(null);
  const [storyLoading, setStoryLoading] = useState(false);
  const [storyError, setStoryError] = useState("");
  const [style, setStyle] = useState("funny");
  const [script, setScript] = useState<ScriptResult | null>(null);
  const [generatedText, setGeneratedText] = useState<Record<string, string>>({});
  const [editedText, setEditedText] = useState<Record<string, string>>({});
  const [approved, setApproved] = useState(false);
  const [scriptLoading, setScriptLoading] = useState(false);
  const [scriptError, setScriptError] = useState("");

  const selectedAsset = assets.find((asset) => asset.id === selectedAssetId) ?? null;
  const handleAssets = useCallback((items: Asset[]) => {
    setAssets(items);
    setSelectedAssetId((current) => current && items.some((item) => item.id === current) ? current : items[0]?.id ?? null);
  }, []);
  const selectPage = useCallback((pageOrder: number) => {
    const asset = assets.find((item) => item.page_order === pageOrder);
    if (asset) setSelectedAssetId(asset.id);
  }, [assets]);

  async function loadStory() {
    setStoryLoading(true); setStoryError("");
    try {
      const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/story-analysis`, { method: "POST" });
      if (!response.ok) throw new Error();
      setStory((await response.json()) as Reliability);
    } catch { setStoryError("ComicAI chưa thể phân tích câu chuyện. Hãy kiểm tra các trang truyện."); }
    finally { setStoryLoading(false); }
  }

  async function generateScript() {
    setScriptLoading(true); setScriptError(""); setApproved(false);
    try {
      const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/short-script`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ style }) });
      if (!response.ok) throw new Error();
      const result = (await response.json()) as ScriptResult;
      setScript(result);
      const text = Object.fromEntries(result.segments.map((segment) => [segment.id, segment.text]));
      setGeneratedText(text); setEditedText(text);
    } catch { setScriptError("ComicAI chưa có đủ thông tin chắc chắn để tạo kịch bản. Hãy kiểm tra phần Câu chuyện."); }
    finally { setScriptLoading(false); }
  }

  const eventPages = useMemo(() => {
    const result = new Map<string, number[]>();
    for (const event of story?.grounded_result.events ?? []) {
      result.set(event.id, [...new Set(event.claims.flatMap((claim) => claim.sources.map((source) => source.page_order)))]);
    }
    return result;
  }, [story]);
  const hasEdits = Object.keys(editedText).some((id) => editedText[id] !== generatedText[id]);
  const scriptStatus = approved ? "Đã duyệt" : hasEdits ? "Đã chỉnh sửa" : "AI tạo";

  return <div className="grid border-x border-white/[0.08] lg:h-auto lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(220px,21%)_minmax(0,1fr)_minmax(300px,27%)] lg:grid-rows-2 lg:overflow-hidden">
    <aside className="flex h-full min-h-0 flex-col overflow-hidden border-b border-white/[0.08] bg-[#0f0f12] lg:row-span-2 lg:border-b-0 lg:border-r">
      <AssetUploader projectId={projectId} selectedAssetId={selectedAssetId} onSelectAsset={setSelectedAssetId} onAssetsChange={handleAssets} />
    </aside>

    <section className="flex min-h-[45vh] min-w-0 flex-col overflow-hidden border-b border-white/[0.08] bg-[#08080a] lg:col-start-2 lg:row-start-1 lg:min-h-0">
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden p-4 lg:p-6">
          {selectedAsset ? <div className="relative h-full w-full"><Image src={selectedAsset.url} alt={selectedAsset.filename} fill unoptimized sizes="(max-width: 1024px) 100vw, 55vw" className="object-contain" /></div> : <div className="text-sm text-white/30">Chọn một trang để xem trước</div>}
        </div>
        <div className="flex h-12 shrink-0 items-center gap-4 border-t border-white/[0.08] bg-[#0d0d10] px-5 text-white/25">
          <button disabled className="flex h-7 w-7 items-center justify-center rounded-md border border-white/10 text-xs" aria-label="Phát video — chưa khả dụng">▶</button>
          <div className="h-1 flex-1 rounded-full bg-white/[0.08]" />
          <span className="font-mono text-xs">00:00</span>
        </div>
      </div>
    </section>

    <aside className="flex min-h-[560px] min-w-0 flex-col overflow-hidden border-t border-white/[0.08] bg-[#101013] lg:col-start-3 lg:row-start-1 lg:min-h-0 lg:border-b lg:border-l lg:border-t-0">
      <nav className="flex h-12 border-b border-white/[0.08] px-5" aria-label="Bảng nội dung">
        {([['story', 'Câu chuyện'], ['script', 'Kịch bản']] as const).map(([id, label]) => <button key={id} onClick={() => setRightTab(id)} className={`relative mr-6 text-sm transition ${rightTab === id ? "text-white after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-violet-500" : "text-white/35 hover:text-white/65"}`}>{label}</button>)}
      </nav>
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {rightTab === "story" ? <StoryPanel story={story} loading={storyLoading} error={storyError} onAnalyze={() => void loadStory()} onSelectPage={selectPage} /> : <ScriptPanel style={style} onStyle={setStyle} script={script} editedText={editedText} onEdit={(id, value) => { setEditedText((current) => ({ ...current, [id]: value })); setApproved(false); }} status={scriptStatus} approved={approved} loading={scriptLoading} error={scriptError} eventPages={eventPages} onGenerate={() => void generateScript()} onApprove={() => setApproved(true)} onSelectPage={selectPage} />}
      </div>
    </aside>
    <section className="flex min-h-[40vh] min-w-0 flex-col bg-[#0c0c0f] lg:col-span-2 lg:col-start-2 lg:row-start-2 lg:min-h-0">
      <div className="flex h-10 items-center border-b border-white/[0.06] px-4">
        <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-white/20">Công cụ chỉnh sửa</span>
      </div>
    </section>
  </div>;
}

function StoryPanel({ story, loading, error, onAnalyze, onSelectPage }: { story: Reliability | null; loading: boolean; error: string; onAnalyze: () => void; onSelectPage: (page: number) => void }) {
  const events = story?.grounded_result.events.filter((event) => story.grounded_result.main_progression.includes(event.id)) ?? [];
  return <div><div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-medium uppercase tracking-[0.18em] text-white/30">Câu chuyện AI hiểu</p>{story && <p className={`mt-2 text-xs ${story.coverage.unresolved_regions ? "text-amber-300" : "text-emerald-400"}`}>{story.coverage.unresolved_regions ? "⚠ Có nội dung cần kiểm tra" : "✓ Đã phân tích câu chuyện"}</p>}</div><button onClick={onAnalyze} disabled={loading} className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-white/55 hover:bg-white/5 hover:text-white disabled:opacity-50">{loading ? "Đang đọc..." : story ? "Làm lại" : "Phân tích"}</button></div>
    {error && <p className="mt-4 text-sm leading-6 text-amber-200">{error}</p>}
    {!story && !loading && !error && <p className="mt-10 text-center text-sm leading-6 text-white/30">Phân tích truyện để xem các diễn biến chính.</p>}
    <div className="mt-5">{events.map((event, index) => { const pages = [...new Set(event.claims.flatMap((claim) => claim.sources.map((source) => source.page_order)))]; return <button key={event.id} onClick={() => pages[0] && onSelectPage(pages[0])} className="block w-full border-b border-white/[0.08] py-5 text-left transition first:pt-2 hover:bg-white/[0.02]"><span className="text-xs font-semibold text-violet-300">{String(index + 1).padStart(2, "0")}</span><p className="mt-2 text-sm leading-6 text-white/75">{event.summary || event.claims.map((claim) => claim.text).join(" ")}</p><div className="mt-3 flex flex-wrap gap-1.5">{pages.map((page) => <span key={page} className="rounded border border-white/10 px-2 py-1 text-[11px] text-white/35">Nguồn · Trang {String(page).padStart(2, "0")}</span>)}</div></button>; })}</div>
  </div>;
}

function ScriptPanel({ style, onStyle, script, editedText, onEdit, status, approved, loading, error, eventPages, onGenerate, onApprove, onSelectPage }: { style: string; onStyle: (value: string) => void; script: ScriptResult | null; editedText: Record<string, string>; onEdit: (id: string, value: string) => void; status: string; approved: boolean; loading: boolean; error: string; eventPages: Map<string, number[]>; onGenerate: () => void; onApprove: () => void; onSelectPage: (page: number) => void }) {
  const labels: Record<string, string> = { hook: "Mở đầu", setup: "Bối cảnh", development: "Diễn biến", payoff: "Cao trào", ending: "Kết" };
  return <div><p className="text-[11px] font-medium uppercase tracking-[0.18em] text-white/30">Kịch bản video</p><div className="mt-4 flex flex-wrap gap-1.5">{[["funny","Hài hước"],["emotional","Cảm xúc"],["dramatic","Kịch tính"]].map(([value,label]) => <button key={value} onClick={() => onStyle(value)} className={`rounded-md px-2.5 py-1.5 text-xs ${style === value ? "bg-violet-500/20 text-violet-200 ring-1 ring-violet-400/35" : "border border-white/10 text-white/35 hover:text-white"}`}>{label}</button>)}</div><button onClick={onGenerate} disabled={loading} className="mt-4 w-full rounded-lg bg-violet-500 py-2.5 text-sm font-medium hover:bg-violet-400 disabled:opacity-50">{loading ? "✦ ComicAI đang viết..." : "✦ Tạo kịch bản"}</button>
    {error && <p className="mt-4 text-sm leading-6 text-amber-200">{error}</p>}
    {script && <><div className="mt-4 flex items-center justify-between text-xs text-white/30"><span>{status}</span><span>{script.segments.length} đoạn</span></div><div className="mt-2">{script.segments.map((segment) => { const pages = [...new Set(segment.source_event_ids.flatMap((id) => eventPages.get(id) ?? []))]; return <div key={segment.id} className="border-b border-white/[0.08] py-4"><div className="flex items-center justify-between"><label htmlFor={segment.id} className="text-[11px] font-semibold uppercase tracking-[0.14em] text-violet-300">{labels[segment.type]}</label><span className="text-[10px] text-white/25">{editedText[segment.id] !== segment.text ? "Đã sửa" : "AI tạo"}</span></div><textarea id={segment.id} value={editedText[segment.id] ?? segment.text} onChange={(event) => onEdit(segment.id, event.target.value)} rows={4} className="mt-2 w-full resize-y rounded-lg border border-white/[0.09] bg-[#0a0a0c] p-3 text-sm leading-6 text-white/75 outline-none focus:border-violet-400/45" />{pages.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{pages.map((page) => <button key={page} onClick={() => onSelectPage(page)} className="text-[11px] text-white/30 hover:text-violet-300">Nguồn · Trang {String(page).padStart(2, "0")}</button>)}</div>}</div>; })}</div><button onClick={onApprove} disabled={approved} className="mt-5 w-full rounded-lg border border-emerald-400/25 py-2.5 text-sm text-emerald-300 disabled:opacity-55">{approved ? "✓ Đã duyệt" : "✓ Duyệt kịch bản"}</button><p className="mt-2 text-center text-[10px] text-white/20">Chỉnh sửa hiện được giữ trong phiên này.</p></>}
  </div>;
}
