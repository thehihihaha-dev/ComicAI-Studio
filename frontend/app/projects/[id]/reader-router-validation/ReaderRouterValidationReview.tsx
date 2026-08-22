"use client";

import Image from "next/image";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";

type ReviewState = "PENDING" | "VERIFIED" | "UNREADABLE" | "SOURCE_UNAVAILABLE";
type Item = {sample_id:string;page_order:number;state:ReviewState;source_compatible:boolean;revision:number;human_transcription:string|null;crop_url:string|null};
type Queue = {checkpoint:string;total:number;verified:number;unreadable:number;pending:number;source_unavailable:number;items:Item[];model_calls:{ocr:number;vlm:number;ollama:number}};
const API = "http://127.0.0.1:8000";

export default function ReaderRouterValidationReview({projectId}:{projectId:string}) {
 const [queue,setQueue]=useState<Queue|null>(null),[index,setIndex]=useState(0),[text,setText]=useState(""),[saving,setSaving]=useState(false),[error,setError]=useState("");
 const editor=useRef<HTMLTextAreaElement>(null);
 const load=useCallback(async()=>{const response=await fetch(`${API}/projects/${projectId}/reader-router-validation-review`,{cache:"no-store"});if(!response.ok)throw new Error("Không thể tải queue 11.13.");const data=await response.json() as Queue;setQueue(data);setIndex(current=>Math.min(current,Math.max(0,data.items.length-1)))},[projectId]);
 useEffect(()=>{
  // Queue loading is the only external synchronization performed here.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  void load().catch(caught=>setError(caught instanceof Error?caught.message:"Đã có lỗi."))
 },[load]);
 const item=queue?.items[index]??null;
 useEffect(()=>{
  // Restore only already-saved Human input; model output is never present in this payload.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  setText(item?.state==="VERIFIED"?item.human_transcription??"":"");setError("");editor.current?.focus()
 },[item?.sample_id,item?.revision,item?.state,item?.human_transcription]);
 const completed=useMemo(()=>queue?queue.total-queue.pending-queue.source_unavailable:0,[queue]);
 async function save(state:"VERIFIED"|"UNREADABLE") {if(!item||saving)return;if(state==="VERIFIED"&&!text.trim()){setError("Vui lòng nhập chính xác chữ nhìn thấy.");return}setSaving(true);setError("");try{const response=await fetch(`${API}/projects/${projectId}/reader-router-validation-review/${item.sample_id}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({state,transcription:state==="VERIFIED"?text:null})});if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.detail||"Không thể lưu.")}await load();setIndex(value=>Math.min(value+1,Math.max(0,(queue?.items.length??1)-1)))}catch(caught){setError(caught instanceof Error?caught.message:"Không thể lưu.")}finally{setSaving(false)}}
 if(!queue)return <div className="mx-auto max-w-5xl p-8 text-sm text-white/45">Đang tải… {error}</div>;
 if(!item)return <div className="mx-auto max-w-5xl p-8 text-sm text-white/45">Không có crop cần chép.</div>;
 return <section className="mx-auto max-w-6xl px-5 py-8"><div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs uppercase tracking-[.18em] text-violet-300">HUMAN TESTING REQUIRED — CHECKPOINT 11.13</p><h2 className="mt-1 text-xl font-semibold">{completed} / {queue.total} đã xử lý</h2><p className="mt-1 text-xs text-white/35">Crop {index+1}/{queue.total} · trang nguồn {item.page_order}</p></div><div className="text-right text-xs text-white/40"><p>{queue.verified} verified · {queue.unreadable} không đọc được</p><p>OCR, confidence và R2 đang được ẩn</p></div></div>
 <div className="grid gap-6 rounded-2xl border border-white/10 bg-[#111114] p-5 md:grid-cols-[minmax(0,1.35fr)_minmax(320px,.65fr)]"><div className="relative h-[520px] overflow-hidden rounded-xl border border-white/10 bg-black/50">{item.crop_url?<Image src={item.crop_url} alt={`Crop trang ${item.page_order}`} fill unoptimized sizes="720px" className="object-contain"/>:<div className="grid h-full place-items-center text-amber-200/70">SOURCE_UNAVAILABLE</div>}</div><div className="flex flex-col"><label htmlFor="validation-transcription" className="text-sm font-medium">Chữ nhìn thấy trong crop</label><p className="mt-1 text-xs leading-5 text-white/35">Chép nguyên văn. Không dịch, không sửa theo suy đoán.</p><textarea ref={editor} id="validation-transcription" value={text} onChange={event=>setText(event.target.value)} disabled={!item.source_compatible||saving} rows={10} className="mt-4 resize-none rounded-xl border border-white/10 bg-black/30 p-4 text-base leading-7 outline-none focus:border-violet-400/50 disabled:opacity-40"/>{error&&<p className="mt-3 text-sm text-red-300">{error}</p>}<div className="mt-4 grid gap-2"><button disabled={saving||!item.source_compatible||!text.trim()} onClick={()=>void save("VERIFIED")} className="rounded-lg bg-violet-500 py-3 font-semibold disabled:opacity-35">{saving?"Đang lưu…":"Lưu & Tiếp theo"}</button><button disabled={saving||!item.source_compatible} onClick={()=>void save("UNREADABLE")} className="rounded-lg border border-white/10 py-2.5 text-sm text-white/60 disabled:opacity-35">Không đọc được</button></div><div className="mt-auto flex justify-between pt-6"><button disabled={index===0} onClick={()=>setIndex(value=>value-1)} className="text-sm text-white/45 disabled:opacity-25">← Crop trước</button><button disabled={index===queue.items.length-1} onClick={()=>setIndex(value=>value+1)} className="text-sm text-white/45 disabled:opacity-25">Crop tiếp →</button></div></div></div></section>
}
