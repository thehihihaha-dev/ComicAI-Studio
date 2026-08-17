"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";

export interface ReviewItem {
  asset_id: string; filename: string; page_order: number; region_id: number;
  raw_text: string; clean_text: string; recovered_text?: string | null;
  verified_text?: string | null; correction_score?: number | null;
  confidence?: number | null; reason?: string; reason_code?: string;
  bbox?: number[] | null; image_url: string; crop_url?: string | null;
}

export default function ReviewQueue({ projectId, onSelectItem, onVerified }: { projectId: string; onSelectItem: (item: ReviewItem) => void; onVerified: () => void }) {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [open, setOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [storyReady, setStoryReady] = useState(false);

  const loadReviewQueue = useCallback(async () => {
    const response = await fetch(`http://127.0.0.1:8000/assets/project/${projectId}/review-queue`, { cache: "no-store" });
    if (!response.ok) throw new Error("Không thể tải danh sách cần kiểm tra.");
    const data = await response.json();
    const nextItems = (data.items ?? []) as ReviewItem[];
    setItems(nextItems);
    setSelectedKey((current) => current && nextItems.some((item) => itemKey(item) === current) ? current : nextItems[0] ? itemKey(nextItems[0]) : null);
    return nextItems;
  }, [projectId]);

  const loadReadiness = useCallback(async () => {
    const response = await fetch(`http://127.0.0.1:8000/projects/${projectId}/story-input`, { cache: "no-store" });
    if (response.ok) setStoryReady((await response.json()).status === "ready");
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        await Promise.all([loadReviewQueue(), loadReadiness()]);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Đã có lỗi xảy ra.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [loadReadiness, loadReviewQueue]);

  const selected = items.find((item) => itemKey(item) === selectedKey) ?? items[0] ?? null;
  function chooseItem(item: ReviewItem) { setSelectedKey(itemKey(item)); onSelectItem(item); }

  async function verifyDialogue(item: ReviewItem, verifiedText: string) {
    const text = verifiedText.trim();
    if (!text) { setError("Văn bản đúng không được để trống."); return; }
    const key = itemKey(item); setSavingKey(key); setError("");
    try {
      const response = await fetch(`http://127.0.0.1:8000/assets/${item.asset_id}/dialogues/${item.region_id}/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ verified_text: text }) });
      if (!response.ok) throw new Error("Không thể lưu xác nhận. Vui lòng thử lại.");
      await Promise.all([loadReviewQueue(), loadReadiness()]);
      onVerified();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể lưu xác nhận.");
    } finally { setSavingKey(null); }
  }

  return <>
    <button type="button" onClick={() => { setOpen(true); if (selected) onSelectItem(selected); }} className={`ml-auto rounded-lg border px-2.5 py-1.5 text-xs transition ${items.length ? "border-amber-400/30 bg-amber-400/10 text-amber-200 hover:bg-amber-400/15" : "border-emerald-400/20 text-emerald-300"}`}>
      {loading ? "Đang kiểm tra…" : items.length ? `⚠ ${items.length} đoạn cần kiểm tra` : "✓ Nội dung đã kiểm tra"}
    </button>
    {open && <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm" onMouseDown={() => setOpen(false)}>
      <section className="ml-auto flex h-full w-full max-w-2xl flex-col border-l border-white/10 bg-[#101013] shadow-2xl" onMouseDown={(event) => event.stopPropagation()} aria-label="Danh sách nội dung cần kiểm tra">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-white/10 px-5"><div><h2 className="text-sm font-semibold">Kiểm tra nội dung</h2><p className="mt-1 text-xs text-white/35">{items.length ? `${items.length} đoạn đang chờ xác nhận` : "Không còn đoạn cần kiểm tra"}</p></div><button onClick={() => setOpen(false)} className="h-9 w-9 rounded-lg border border-white/10 text-white/50 hover:bg-white/5 hover:text-white" aria-label="Đóng">×</button></header>
        {error && <p className="mx-5 mt-4 rounded-lg border border-red-400/20 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {storyReady && <p className="mx-5 mt-4 rounded-lg border border-emerald-400/20 bg-emerald-500/10 p-3 text-sm text-emerald-200">✓ Nội dung đã sẵn sàng để phân tích câu chuyện</p>}
        {items.length === 0 ? <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-white/35">Tất cả hội thoại đã được kiểm tra.</div> : <div className="grid min-h-0 flex-1 md:grid-cols-[190px_minmax(0,1fr)]">
          <nav className="overflow-y-auto border-r border-white/10 p-3" aria-label="Các đoạn cần kiểm tra">{items.map((item) => <button key={itemKey(item)} onClick={() => chooseItem(item)} className={`mb-2 w-full rounded-lg border p-3 text-left ${selected && itemKey(item) === itemKey(selected) ? "border-violet-400/35 bg-violet-500/10" : "border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.04]"}`}><span className="text-xs font-medium text-white/75">Trang {item.page_order}</span><p className="mt-1 truncate text-xs text-white/35">{suggestedText(item)}</p></button>)}</nav>
          {selected && <ReviewEditor key={itemKey(selected)} item={selected} saving={savingKey === itemKey(selected)} onSave={(text) => void verifyDialogue(selected, text)} />}
        </div>}
      </section>
    </div>}
  </>;
}

function ReviewEditor({ item, saving, onSave }: { item: ReviewItem; saving: boolean; onSave: (text: string) => void }) {
  const proposal = suggestedText(item); const [text, setText] = useState(proposal);
  return <div className="overflow-y-auto p-5"><div className="flex items-center justify-between"><div><p className="text-xs text-violet-300">Trang {item.page_order}</p><h3 className="mt-1 text-base font-medium">Đoạn cần kiểm tra</h3></div>{item.confidence != null && <span className="text-xs text-white/30">Độ tin cậy {Math.round(item.confidence * 100)}%</span>}</div>
    <div className="relative mt-4 h-52 overflow-hidden rounded-xl border border-white/10 bg-black/40"><Image src={item.crop_url || item.image_url} alt={`Vùng cần kiểm tra trên trang ${item.page_order}`} fill unoptimized sizes="460px" className="object-contain" /></div>
    <div className="mt-5 space-y-4"><div><p className="text-[11px] uppercase tracking-wider text-white/30">OCR gốc</p><p className="mt-1.5 text-sm leading-6 text-white/55">{item.raw_text || "Không đọc được"}</p></div><div><p className="text-[11px] uppercase tracking-wider text-white/30">AI đọc</p><p className="mt-1.5 text-sm leading-6 text-white/80">{proposal}</p></div>
      <div><label htmlFor={`verified-${itemKey(item)}`} className="text-[11px] uppercase tracking-wider text-white/30">Văn bản đúng</label><textarea id={`verified-${itemKey(item)}`} value={text} onChange={(event) => setText(event.target.value)} rows={3} className="mt-2 w-full resize-y rounded-xl border border-white/10 bg-[#09090b] p-3 text-sm leading-6 text-white outline-none focus:border-violet-400/50" /></div>
      <div className="rounded-lg bg-white/[0.03] p-3"><p className="text-[11px] text-white/30">Lý do cần kiểm tra</p><p className="mt-1 text-sm text-white/55">{friendlyReason(item.reason_code, item.reason)}</p></div>
      <button onClick={() => onSave(text)} disabled={saving || !text.trim()} className="w-full rounded-lg bg-violet-500 py-2.5 text-sm font-medium text-white hover:bg-violet-400 disabled:opacity-50">{saving ? "Đang lưu…" : "Xác nhận"}</button>
    </div></div>;
}

function itemKey(item: ReviewItem) { return `${item.asset_id}-${item.region_id}`; }
function suggestedText(item: ReviewItem) { return item.verified_text || item.recovered_text || item.clean_text || item.raw_text || ""; }
function friendlyReason(code?: string, fallback?: string) {
  const labels: Record<string, string> = { ambiguous_visual: "Chữ trong ảnh khó đọc rõ.", fragmented_ocr: "Văn bản được nhận diện thành nhiều phần rời.", low_confidence: "AI chưa đủ chắc chắn về nội dung.", proper_name_uncertain: "Tên riêng cần được người dùng xác nhận.", recovered_visual_text_requires_review: "Đây là chữ viết tay được khôi phục từ hình ảnh.", needs_review: "AI cần bạn kiểm tra lại nội dung này." };
  return labels[code || ""] || fallback || labels.needs_review;
}
