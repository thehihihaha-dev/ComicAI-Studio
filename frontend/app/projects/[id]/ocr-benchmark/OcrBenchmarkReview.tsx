"use client";

import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type State = "PENDING" | "VERIFIED" | "SKIPPED" | "UNREADABLE" | "SOURCE_UNAVAILABLE";
type Item = { sample_id: string; asset_id: string; page_order: number; region_id: number | null; text_role: string; state: State; source_compatible: boolean; revision: number; verified_text?: string | null; crop_url?: string | null };
type Queue = { total: number; verified: number; pending: number; items: Item[] };
const API = "http://127.0.0.1:8000";

export default function OcrBenchmarkReview({ projectId }: { projectId: string }) {
  const [queue, setQueue] = useState<Queue | null>(null); const [index, setIndex] = useState(0);
  const [text, setText] = useState(""); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const editor = useRef<HTMLTextAreaElement>(null);
  const load = useCallback(async () => { const response = await fetch(`${API}/projects/${projectId}/ocr-benchmark-review`, { cache: "no-store" }); if (!response.ok) throw new Error("Không thể tải hàng đợi."); const data = await response.json() as Queue; setQueue(data); setIndex((current) => Math.min(current, Math.max(0, data.items.length - 1))); }, [projectId]);
  useEffect(() => {
    // Queue loading is the external synchronization performed by this effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load().catch((caught) => setError(caught instanceof Error ? caught.message : "Đã có lỗi."));
  }, [load]);
  const item = queue?.items[index] ?? null;
  useEffect(() => {
    // Reset the editor only when navigation selects a different persisted sample.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setText(item?.state === "VERIFIED" ? item.verified_text ?? "" : ""); setError(""); if (item?.state !== "SOURCE_UNAVAILABLE") editor.current?.focus();
  }, [item?.sample_id, item?.revision, item?.state, item?.verified_text]);
  const completed = useMemo(() => queue?.items.filter((entry) => entry.state !== "PENDING").length ?? 0, [queue]);
  async function save(state: "VERIFIED" | "SKIPPED" | "UNREADABLE") {
    if (!item || saving) return; if (state === "VERIFIED" && !text.trim()) { setError("Bản chép chính xác không được để trống."); return; }
    setSaving(true); setError(""); try { const response = await fetch(`${API}/projects/${projectId}/ocr-benchmark-review/${item.sample_id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ state, transcription: state === "VERIFIED" ? text : null }) }); if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || "Không thể lưu."); } await load(); setIndex((current) => Math.min(current + 1, Math.max(0, (queue?.items.length ?? 1) - 1))); } catch (caught) { setError(caught instanceof Error ? caught.message : "Không thể lưu."); } finally { setSaving(false); }
  }
  if (!queue) return <div className="mx-auto max-w-5xl p-8 text-sm text-white/45">Đang tải hàng đợi…{error && ` ${error}`}</div>;
  if (!item) return <div className="mx-auto max-w-5xl p-8 text-sm text-white/45">Không có vùng OCR cần chép.</div>;
  return <section className="mx-auto max-w-5xl px-5 py-8">
    <div className="mb-5 flex items-end justify-between"><div><p className="text-xs uppercase tracking-[0.18em] text-violet-300">Human-only review</p><h2 className="mt-1 text-xl font-semibold">{queue.verified} / {queue.total} verified</h2><p className="mt-1 text-xs text-white/35">{completed} đã xử lý · mẫu {index + 1} / {queue.total}</p></div><span className="rounded-full border border-white/10 px-3 py-1 text-xs text-white/45">{item.state}</span></div>
    <div className="grid gap-6 rounded-2xl border border-white/10 bg-[#111114] p-5 md:grid-cols-[minmax(0,1.15fr)_minmax(300px,.85fr)]">
      <div><div className="relative h-[420px] overflow-hidden rounded-xl border border-white/10 bg-black/50">{item.crop_url ? <Image src={item.crop_url} alt={`Source crop trang ${item.page_order}`} fill unoptimized sizes="600px" className="object-contain" /> : <div className="flex h-full items-center justify-center text-sm text-amber-200/70">SOURCE_UNAVAILABLE</div>}</div><p className="mt-3 text-xs text-white/35">Trang {item.page_order} · {item.text_role} · vùng {item.region_id ?? "N/A"}</p></div>
      <div className="flex flex-col"><label htmlFor="human-transcription" className="text-xs font-medium text-white/60">Exact transcription</label><p className="mt-1 text-xs leading-5 text-white/30">Chỉ chép những gì bạn nhìn thấy. OCR và AI được ẩn để tránh bias.</p><textarea ref={editor} id="human-transcription" value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") void save("VERIFIED"); }} disabled={!item.source_compatible || saving} rows={8} className="mt-4 resize-none rounded-xl border border-white/10 bg-black/30 p-4 text-base leading-7 outline-none focus:border-violet-400/50 disabled:opacity-40" />
        {error && <p className="mt-3 text-sm text-red-300">{error}</p>}<div className="mt-4 grid grid-cols-2 gap-2"><button disabled={saving || !item.source_compatible} onClick={() => void save("UNREADABLE")} className="rounded-lg border border-white/10 py-2.5 text-sm text-white/55 disabled:opacity-40">Unreadable</button><button disabled={saving || !item.source_compatible} onClick={() => void save("SKIPPED")} className="rounded-lg border border-white/10 py-2.5 text-sm text-white/55 disabled:opacity-40">Skip</button><button disabled={saving || !item.source_compatible || !text.trim()} onClick={() => void save("VERIFIED")} className="col-span-2 rounded-lg bg-violet-500 py-3 text-sm font-semibold hover:bg-violet-400 disabled:opacity-40">{saving ? "Đang lưu…" : "Save & Next"}</button></div>
        <div className="mt-auto flex justify-between pt-6"><button disabled={index === 0} onClick={() => setIndex((value) => Math.max(0, value - 1))} className="text-sm text-white/45 disabled:opacity-25">← Previous</button><button disabled={index >= queue.items.length - 1} onClick={() => setIndex((value) => Math.min(queue.items.length - 1, value + 1))} className="text-sm text-white/45 disabled:opacity-25">Next →</button></div>
      </div>
    </div>
  </section>;
}
