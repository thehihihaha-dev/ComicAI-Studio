"use client";
/* eslint-disable react-hooks/refs -- gesture refs are read only inside pointer-event handlers. */

import Image from "next/image";
import { PointerEvent, useCallback, useEffect, useRef, useState } from "react";
import { deletedBox, drawnBox, movedBox, pointerToSource, resizedBox, sourceBoxToDisplay,
  toggledAmbiguity, type PanelBox, type Size } from "./panelState";

type Box = PanelBox;
type Item = { review_id: string; page_order: number; source_hash: string; state: string; revision: number;
  image_dimensions: { width: number; height: number }; human_panels: Box[]; image_url: string | null };
type Queue = { total: number; verified: number; pending: number; predictions_hidden: boolean; items: Item[] };
type Gesture = { kind: "draw" | "move" | "resize"; id: string; start: [number, number]; original: Box["bbox"]; corner?: string };
type LoadState = "LOADING" | "READY" | "ERROR";
const API = "/api/panel-ground-truth";

export default function PanelGroundTruth() {
  const [queue, setQueue] = useState<Queue | null>(null), [index, setIndex] = useState(0);
  const [boxes, setBoxes] = useState<Box[]>([]), [selected, setSelected] = useState<string | null>(null);
  const [saving, setSaving] = useState(false), [error, setError] = useState(""), [nextId, setNextId] = useState(1);
  const [loadState, setLoadState] = useState<LoadState>("LOADING");
  const [surfaceSize, setSurfaceSize] = useState<Size>({ width: 0, height: 0 });
  const gesture = useRef<Gesture | null>(null);
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const load = useCallback(async () => { setLoadState("LOADING"); setError(""); try {
    const response = await fetch(API, { cache: "no-store", signal: AbortSignal.timeout(12_000) });
    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new Error(payload?.detail || `Không thể tải hàng đợi (HTTP ${response.status})`);
    if (!payload || payload.total !== 6 || !Array.isArray(payload.items)) throw new Error("Queue Panel GT trả dữ liệu không hợp lệ");
    setQueue(payload); setLoadState("READY");
  } catch (value) { setQueue(null); setError(value instanceof Error ? value.message : String(value)); setLoadState("ERROR"); } }, []);
  useEffect(() => {
    // Queue loading is the external synchronization performed by this effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);
  const item = queue?.items[index];
  useEffect(() => { if (!item) return;
    // Restore only persisted Human boxes for the selected frozen source.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBoxes(item.human_panels); setSelected(null); setNextId(item.human_panels.reduce((maximum, panel) => {
      const suffix=Number(panel.panel_id.split("-").at(-1)); return Number.isFinite(suffix)?Math.max(maximum,suffix+1):maximum;
    }, 1));
  }, [item]);

  useEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;
    const update = () => setSurfaceSize({ width: element.clientWidth, height: element.clientHeight });
    update();
    const observer = new ResizeObserver(update); observer.observe(element);
    return () => observer.disconnect();
  }, [item]);

  function point(event: PointerEvent): [number, number] | null {
    const element = (event.currentTarget as HTMLElement).closest("[data-panel-surface]") as HTMLElement;
    const rect = element.getBoundingClientRect(), dims = item!.image_dimensions;
    return pointerToSource([event.clientX - rect.left,event.clientY - rect.top],{width:rect.width,height:rect.height},dims);
  }
  function startDraw(event: PointerEvent<HTMLDivElement>) {
    if (event.target !== event.currentTarget || !item) return;
    const start = point(event); if (!start) return; event.currentTarget.setPointerCapture(event.pointerId);
    const id = `human-${item.page_order}-${nextId}`; setNextId(value => value + 1);
    gesture.current = { kind: "draw", id, start, original: [start[0], start[1], start[0], start[1]] };
    setBoxes(current => [...current, { panel_id: id, bbox: [start[0], start[1], start[0], start[1]], ambiguous: false }]); setSelected(id);
  }
  function startExisting(event: PointerEvent, box: Box, kind: "move" | "resize", corner?: string) {
    event.stopPropagation(); const element=(event.currentTarget as HTMLElement).closest("[data-panel-surface]") as HTMLElement; element.setPointerCapture(event.pointerId);
    const start=point(event); if(!start)return;
    gesture.current = { kind, id: box.panel_id, start, original: [...box.bbox], corner }; setSelected(box.panel_id);
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    const active = gesture.current; if (!active || !item) return; const now = point(event), dims = item.image_dimensions;
    if(!now)return;
    setBoxes(current => current.map(box => { if (box.panel_id !== active.id) return box;
      let next: Box["bbox"];
      if (active.kind === "draw") next = drawnBox(active.start,now);
      else if (active.kind === "move") next=movedBox(active.original,now[0]-active.start[0],now[1]-active.start[1],dims.width,dims.height);
      else next=resizedBox(active.original,active.corner!,now);
      return { ...box, bbox: next }; }));
  }
  function end() { const active=gesture.current; gesture.current=null; if(!active)return;
    setBoxes(current=>current.filter(box=>box.panel_id!==active.id || (box.bbox[2]-box.bbox[0])*(box.bbox[3]-box.bbox[1])>=16)); }
  function remove() { if (!selected) return; setBoxes(current => deletedBox(current,selected)); setSelected(null); }
  function toggleAmbiguous() { if (!selected) return; setBoxes(current => toggledAmbiguity(current,selected)); }
  async function save() { if (!item) return; setSaving(true); setError(""); try { const response=await fetch(`${API}/${encodeURIComponent(item.review_id)}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({panels:boxes})});
    if(!response.ok)throw new Error((await response.json()).detail||"Không thể lưu");await load(); } catch(value){setError(String(value));} finally{setSaving(false);} }
  if (loadState === "LOADING") return <div className="grid min-h-[70vh] place-items-center p-8 text-white/60"><div className="text-center"><p className="text-lg">Đang tải dữ liệu Panel GT…</p><p className="mt-2 text-sm text-white/35">Đang kết nối queue gồm 6 trang.</p></div></div>;
  if (loadState === "ERROR" || !queue || !item) return <div className="grid min-h-[70vh] place-items-center p-8"><div className="max-w-xl rounded-xl border border-red-400/25 bg-red-500/10 p-6 text-center"><h2 className="text-lg font-semibold text-red-200">Không tải được Human Panel GT</h2><p className="mt-3 text-sm text-red-100/75">{error || "Queue không có trang hợp lệ."}</p><button onClick={()=>void load()} className="mt-5 rounded bg-white px-5 py-2 font-semibold text-black">Thử lại</button></div></div>;
  const dims=item.image_dimensions, current=boxes.find(box=>box.panel_id===selected);
  return <section className="mx-auto max-w-[1700px] p-5">
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-semibold uppercase text-violet-300">HUMAN TESTING REQUIRED</p><h2 className="text-xl">Trang {index+1}/{queue.total} · Page {item.page_order}</h2><p className="text-sm text-white/55">Vẽ một khung quanh từng ô truyện thật. Nếu ranh giới panel thực sự không rõ, đánh dấu Mơ hồ.</p></div><div className="text-right text-sm"><p><b className="text-emerald-300">{queue.verified} VERIFIED</b> · {queue.pending} PENDING</p><p className="text-xs text-white/40">Dữ liệu dự đoán được ẩn hoàn toàn</p></div></div>
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,3fr)_340px]">
      <div className="rounded-xl border border-white/10 bg-black/50 p-3"><div ref={surfaceRef} data-panel-surface onPointerDown={startDraw} onPointerMove={move} onPointerUp={end} onPointerCancel={end} className="relative mx-auto w-full touch-none select-none" style={{aspectRatio:`${dims.width}/${dims.height}`,maxHeight:"calc(100vh - 150px)"}}>
        <Image src={item.image_url!} alt={`Trang truyện ${item.page_order}`} fill unoptimized draggable={false} className="pointer-events-none object-contain" />
        {boxes.map((box,position)=>{const [x1,y1,x2,y2]=sourceBoxToDisplay(box.bbox,surfaceSize,dims),isSelected=box.panel_id===selected;return <div key={box.panel_id} onPointerDown={event=>startExisting(event,box,"move")} className={`absolute cursor-move border-2 ${box.ambiguous?"border-amber-400 bg-amber-400/10":"border-emerald-400 bg-emerald-400/10"} ${isSelected?"z-20 ring-2 ring-white":"z-10"}`} style={{left:x1,top:y1,width:x2-x1,height:y2-y1}}><span className="absolute left-0 top-0 bg-black/75 px-1 text-xs">{position+1}{box.ambiguous?" · Mơ hồ":""}</span>{isSelected&&(["lt","rt","lb","rb"] as const).map(corner=><button key={corner} aria-label={`Điều chỉnh góc ${corner}`} onPointerDown={event=>startExisting(event,box,"resize",corner)} className={`absolute h-4 w-4 rounded-full bg-white ${corner.includes("l")?"-left-2":"-right-2"} ${corner.includes("t")?"-top-2":"-bottom-2"}`} />)}</div>})}
      </div></div>
      <aside className="space-y-4 lg:sticky lg:top-5"><div className="rounded-xl border border-white/10 bg-[#111114] p-4"><h3 className="font-semibold">Cách làm</h3><ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-white/65"><li>Vẽ khung quanh toàn bộ ô truyện, không vẽ bong bóng thoại, vùng chữ hoặc riêng nhân vật.</li><li>Nếu ranh giới của một panel thực sự không rõ, đánh dấu Mơ hồ.</li><li>Kéo khung để di chuyển; kéo chấm tròn để chỉnh kích thước.</li><li>Làm hết cả 6 trang và lưu từng trang. Thứ tự vẽ không phải thứ tự đọc.</li></ol></div>
        <div className="rounded-xl border border-white/10 bg-[#111114] p-4"><h3 className="font-semibold">Khung đang chọn</h3>{current?<><p className="mt-2 text-sm text-white/55">Khung số {boxes.indexOf(current)+1}</p><button onClick={toggleAmbiguous} className={`mt-3 w-full rounded py-2 ${current.ambiguous?"bg-amber-500 text-black":"border border-white/15"}`}>{current.ambiguous?"✓ Đã đánh dấu Mơ hồ":"Đánh dấu Mơ hồ"}</button><button onClick={remove} className="mt-2 w-full rounded border border-red-400/40 py-2 text-red-300">Xóa khung</button></>:<p className="mt-2 text-sm text-white/40">Chọn một khung để chỉnh sửa.</p>}</div>
        {error&&<p className="rounded bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
        <button disabled={saving||boxes.length===0} onClick={()=>void save()} className="w-full rounded bg-violet-500 py-3 font-semibold disabled:opacity-30">{saving?"Đang lưu…":item.state==="VERIFIED"?"Lưu thay đổi":"Lưu và xác nhận trang"}</button>
        <div className="flex justify-between"><button disabled={index===0} onClick={()=>setIndex(value=>value-1)}>← Trang trước</button><button disabled={index===queue.items.length-1} onClick={()=>setIndex(value=>value+1)}>Trang tiếp →</button></div>
      </aside>
    </div>
  </section>;
}
