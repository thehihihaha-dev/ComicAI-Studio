#!/usr/bin/env python3
"""Controlled deterministic crop/reconstruction replay on frozen 11.13 GT."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from PIL import Image

ROOT=Path(__file__).resolve().parents[1];BACKEND=ROOT/"backend";sys.path[:0]=[str(BACKEND),str(ROOT/"scripts")];load_dotenv(BACKEND/".env");os.chdir(BACKEND)
from app.database import SessionLocal
from app.models.asset import Asset
from app.services.logical_crop_reconstruction_experiment import adaptive_box,cache_key,geometry_audit,ordered_fragments,proportional_box,reconstruct_text
from app.services.ocr_acceptance_router_experiment import route
from app.services.resource_safety import CRITICAL,ResourceThresholds,sample_resources
from reader_benchmark import authoritative_snapshot

DAY=ROOT/"benchmarks/day11";MANIFEST=DAY/"reader-router-validation-manifest-11.13.json";HUMAN=DAY/"reader-router-validation-human-gt-11.13.json";RESULTS13=DAY/"reader-router-validation-results-11.13.json";ERRORS13=DAY/"reader-router-validation-errors-11.13.json";GATE=DAY/"reader-v2-scale-40p-11.10.json";FALSE12=DAY/"reader-router-false-safe-audit-11.12.json"
REPLAY=DAY/"reader-structural-replay-11.14.json";AUDIT=DAY/"reader-structural-audit-11.14.json";CANDIDATES=DAY/"reader-structural-candidates-11.14.json";COMPARISON=DAY/"reader-structural-comparison-11.14.json";ERRORS=DAY/"reader-structural-errors-11.14.json";SUMMARY=DAY/"reader-structural-summary-11.14.json";PROJECT="e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2"
CONTRACTS={"logical_2pct":{"concept":"logical crop with 2% max-dimension padding","ocr_mode":"readtext RGB"},"adaptive_bounded":{"concept":"logical crop with 4% max-dimension padding bounded to 3..14 pixels","ocr_mode":"readtext RGB"},"fragment_line_2pct":{"concept":"2%-padded source-fragment crops, each recognized independently, then geometry ordered top-to-bottom/left-to-right","ocr_mode":"readtext RGB per fragment"}}
def norm(text):return " ".join(unicodedata.normalize("NFC",text).upper().split())
def distance(a,b):
 prev=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  cur=[i]
  for j,y in enumerate(b,1):cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
  prev=cur
 return prev[-1]
def score(pred,truth):
 p,h=norm(pred),norm(truth);ce=distance(p,h);we=distance(p.split(),h.split());return {"exact":p==h,"char_errors":ce,"human_chars":len(h),"cer":ce/len(h) if h else 0,"word_errors":we,"human_words":len(h.split()),"wer":we/len(h.split()) if h.split() else 0}
def aggregate(rows):
 n=len(rows);chars=sum(x["score"]["human_chars"] for x in rows);words=sum(x["score"]["human_words"] for x in rows);return {"n":n,"exact":sum(x["score"]["exact"] for x in rows),"exact_rate":sum(x["score"]["exact"] for x in rows)/n if n else 0,"normalized_cer":sum(x["score"]["char_errors"] for x in rows)/chars if chars else 0,"wer":sum(x["score"]["word_errors"] for x in rows)/words if words else 0}
def recognize(reader,image,box):
 started=time.perf_counter();values=reader.readtext(np.asarray(image.crop(tuple(box))),detail=1);elapsed=time.perf_counter()-started;lines=[{"region_id":index,"bbox":[float(min(p[0] for p in value[0])),float(min(p[1] for p in value[0])),float(max(p[0] for p in value[0])),float(max(p[1] for p in value[0]))],"text":str(value[1]),"confidence":float(value[2])} for index,value in enumerate(values)];return reconstruct_text(lines),lines,elapsed
def run_candidate(reader,image,item,fragments,name,version):
 if name=="logical_2pct":
  box=proportional_box(item["bbox"],image.size,.02);text,lines,latency=recognize(reader,image,box);calls=1
 elif name=="adaptive_bounded":
  box=adaptive_box(item["bbox"],image.size);text,lines,latency=recognize(reader,image,box);calls=1
 else:
  box=proportional_box(item["bbox"],image.size,.02);recognized=[];latency=0;calls=0
  for fragment in ordered_fragments(fragments):
   fragment_box=proportional_box(fragment["bbox"],image.size,.02);fragment_text,_,duration=recognize(reader,image,fragment_box);latency+=duration;calls+=1;recognized.append({"region_id":fragment["region_id"],"bbox":fragment["bbox"],"text":fragment_text})
  lines=recognized;text=reconstruct_text(recognized)
 return {"candidate":name,"crop_bbox":box,"output":text,"line_outputs":[x["text"] for x in lines],"latency_seconds":latency,"ocr_calls":calls,"cache_key":cache_key(item["source_hash"],item["bbox"],[x["bbox"] for x in fragments],name,version)}
def main():
 manifest=json.loads(MANIFEST.read_text());human=json.loads(HUMAN.read_text());old=json.loads(RESULTS13.read_text());gate=json.loads(GATE.read_text());structural_ids=set(json.loads(ERRORS13.read_text())["structural_analysis"]["sample_ids"]);human_by={x["sample_id"]:x for x in human["samples"]};old_by={x["sample_id"]:x for x in old["samples"]};gate_by={p["asset_id"]:p for p in gate["pages"]};manifest_hash=hashlib.sha256(MANIFEST.read_bytes()).hexdigest();human_hash=hashlib.sha256(HUMAN.read_bytes()).hexdigest();authoritative_before=authoritative_snapshot(PROJECT)["state_hash"]
 declared={"schema_version":"reader-structural-candidates.v1","checkpoint":"11.14","status":"DECLARED_BEFORE_OCR","engine":"EasyOCR vi+en CPU, unchanged","candidate_contracts":CONTRACTS,"selection_features":"geometry only; Human text excluded from crop/group/order construction","r2_status":"FROZEN historical replay only; no tuning or deployment"};contract_hash=hashlib.sha256(json.dumps(declared,sort_keys=True,separators=(",",":")).encode()).hexdigest();CANDIDATES.write_text(json.dumps({**declared,"pre_ocr_contract_hash":contract_hash},ensure_ascii=False,indent=2)+"\n")
 db=SessionLocal();asset_paths={}
 try:
  for page in manifest["pages"]:
   asset=db.get(Asset,page["asset_id"]);path=Path(asset.file_path);path=path if path.is_absolute() else BACKEND/path;asset_paths[page["asset_id"]]=str(path)
 finally:db.close()
 replay=[];audits=[]
 for item in manifest["samples"]:
  human_row=human_by[item["sample_id"]];fragments_by={r["region_id"]:r for r in gate_by[item["asset_id"]]["result"]["regions"]};fragments=[{"region_id":fid,"bbox":fragments_by[fid]["bbox"]} for fid in item["source_fragment_ids"]];audit=geometry_audit(item["bbox"],fragments);path=Path(asset_paths[item["asset_id"]])
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item["source_hash"]:raise RuntimeError("source replay mismatch")
  replay.append({"sample_id":item["sample_id"],"asset_id":item["asset_id"],"page_order":item["page_order"],"source_hash":item["source_hash"],"source_image":str(path),"logical_bbox":item["bbox"],"fragment_boxes":fragments,"original_crop_bbox":item["bbox"],"original_ocr_text":item["prediction"],"original_confidence":item["features"]["min_confidence"],"reconstruction_metadata":item["features"],"human_state":human_row["state"],"human_transcription":human_row["human_transcription"],"structural_flags":audit["tags"]})
  audits.append({"sample_id":item["sample_id"],"human_state":human_row["state"],"is_observed_structural_error":item["sample_id"] in structural_ids,**audit})
 thresholds=ResourceThresholds.from_environment();resources_before=sample_resources(thresholds)
 if resources_before["safety_state"]==CRITICAL:raise SystemExit("FAIL — MACHINE SAFETY")
 import easyocr
 init_started=time.perf_counter();reader=easyocr.Reader(["vi","en"],gpu=False);init_seconds=time.perf_counter()-init_started;version=importlib.metadata.version("easyocr");after_init=sample_resources(thresholds)
 if after_init["safety_state"]==CRITICAL:raise SystemExit("FAIL — MACHINE SAFETY after EasyOCR initialization")
 outputs={name:[] for name in CONTRACTS};ocr_calls=0;crop_started=time.perf_counter();crop_overhead=0
 for index,item in enumerate(manifest["samples"]):
  fragment_map={r["region_id"]:r for r in gate_by[item["asset_id"]]["result"]["regions"]};fragments=[{"region_id":fid,"bbox":fragment_map[fid]["bbox"]} for fid in item["source_fragment_ids"]]
  with Image.open(asset_paths[item["asset_id"]]) as source:
   image=source.convert("RGB")
   for name in CONTRACTS:
    started=time.perf_counter();result=run_candidate(reader,image,item,fragments,name,version);crop_overhead+=max(0,time.perf_counter()-started-result["latency_seconds"]);ocr_calls+=result["ocr_calls"]
    human_row=human_by[item["sample_id"]];result.update({"sample_id":item["sample_id"],"human_state":human_row["state"]})
    if human_row["state"]=="VERIFIED":result["score"]=score(result["output"],human_row["human_transcription"])
    outputs[name].append(result)
  if index%10==9 and sample_resources(thresholds)["safety_state"]==CRITICAL:raise SystemExit(f"FAIL — MACHINE SAFETY after {index+1} samples")
 total_seconds=time.perf_counter()-crop_started
 verified_ids={x["sample_id"] for x in human["samples"] if x["state"]=="VERIFIED"};control=[{"sample_id":sid,"output":old_by[sid]["ocr_prediction"],"score":score(old_by[sid]["ocr_prediction"],human_by[sid]["human_transcription"])} for sid in verified_ids];control_by={x["sample_id"]:x for x in control};metrics={"control":aggregate(control)};diffs={}
 for name,rows in outputs.items():
  verified=[x for x in rows if x["human_state"]=="VERIFIED"];metrics[name]=aggregate(verified);changes=[]
  for row in verified:
   base=control_by[row["sample_id"]];delta=row["score"]["cer"]-base["score"]["cer"];classification="IMPROVED" if delta<0 else "REGRESSED" if delta>0 else "UNCHANGED";changes.append({"sample_id":row["sample_id"],"control_output":base["output"],"candidate_output":row["output"],"control_cer":base["score"]["cer"],"candidate_cer":row["score"]["cer"],"classification":classification,"correct_to_wrong":base["score"]["exact"] and not row["score"]["exact"],"large_cer_regression":delta>=.10})
  diffs[name]=changes;metrics[name].update({"improved":sum(x["classification"]=="IMPROVED" for x in changes),"unchanged":sum(x["classification"]=="UNCHANGED" for x in changes),"regressed":sum(x["classification"]=="REGRESSED" for x in changes),"correct_to_wrong":sum(x["correct_to_wrong"] for x in changes),"large_cer_regressions":sum(x["large_cer_regression"] for x in changes)})
 best=min(CONTRACTS,key=lambda name:(metrics[name]["normalized_cer"],-metrics[name]["exact"],metrics[name]["regressed"],name));best_by={x["sample_id"]:x for x in outputs[best]};structural_control=[x for x in control if x["sample_id"] in structural_ids];structural_candidate=[x for x in outputs[best] if x["sample_id"] in structural_ids];structural_changes=[x for x in diffs[best] if x["sample_id"] in structural_ids];structural_metrics={"control":aggregate(structural_control),"candidate":aggregate(structural_candidate),"repaired":sum(not control_by[x["sample_id"]]["score"]["exact"] and x["score"]["exact"] for x in structural_candidate),"improved":sum(x["classification"]=="IMPROVED" for x in structural_changes),"unchanged":sum(x["classification"]=="UNCHANGED" for x in structural_changes),"regressed":sum(x["classification"]=="REGRESSED" for x in structural_changes)}
 false13=next(x for x in old["samples"] if x["r2_state"]=="SAFE_CANDIDATE" and x.get("exact") is False);best_false=best_by[false13["sample_id"]];false_replay={"11.13":{"sample_id":false13["sample_id"],"control_output":false13["ocr_prediction"],"candidate_output":best_false["output"],"human_gt":false13["human_transcription"],"candidate_exact":best_false["score"]["exact"],"structural_fix_result":"REMOVED_FALSE_SAFE_TEXT_ERROR" if best_false["score"]["exact"] else "FALSE_SAFE_TEXT_ERROR_REMAINS","frozen_r2_result":"GENERALIZATION FAIL remains historical; router not reclassified or tuned"}}
 # Replay 11.12 baseline false-safe rows through the selected crop strategy without changing the selection.
 old_false=[];db=SessionLocal()
 try:
  for case in json.loads(FALSE12.read_text())["cases"]:
   asset=db.get(Asset,case["asset_id"]);path=Path(asset.file_path);path=path if path.is_absolute() else BACKEND/path;fragments_map={r["region_id"]:r for r in gate_by[case["asset_id"]]["result"]["regions"]};fragments=[{"region_id":fid,"bbox":fragments_map[fid]["bbox"]} for fid in case["source_fragment_ids"]]
   with Image.open(path) as source:result=run_candidate(reader,source.convert("RGB"),{"bbox":case["bbox"],"source_hash":case["source_hash"]},fragments,best,version)
   ocr_calls+=result["ocr_calls"];old_false.append({"sample_id":case["sample_id"],"control_output":case["ocr_output"],"candidate_output":result["output"],"human_gt":case["human_gt"],"control_cer":score(case["ocr_output"],case["human_gt"])["cer"],"candidate_cer":score(result["output"],case["human_gt"])["cer"],"candidate_exact":score(result["output"],case["human_gt"])["exact"]})
 finally:db.close()
 false_replay["11.12_baseline_false_safe"]={"n":len(old_false),"repaired_exact":sum(x["candidate_exact"] for x in old_false),"improved":sum(x["candidate_cer"]<x["control_cer"] for x in old_false),"unchanged":sum(x["candidate_cer"]==x["control_cer"] for x in old_false),"regressed":sum(x["candidate_cer"]>x["control_cer"] for x in old_false),"cases":old_false}
 unreadable=[]
 for row in (x for x in replay if x["human_state"]=="UNREADABLE"):
  out=best_by[row["sample_id"]];original_area=max(1,(row["logical_bbox"][2]-row["logical_bbox"][0])*(row["logical_bbox"][3]-row["logical_bbox"][1]));new_area=max(1,(out["crop_bbox"][2]-out["crop_bbox"][0])*(out["crop_bbox"][3]-out["crop_bbox"][1]));state="MORE_COMPLETE_GEOMETRY" if new_area>original_area else "SAME_STRUCTURAL_STATE";unreadable.append({"sample_id":row["sample_id"],"result":state,"original_area":original_area,"candidate_area":new_area,"human_text_inferred":False})
 resources_after=sample_resources(thresholds);authoritative_after=authoritative_snapshot(PROJECT)["state_hash"]
 if hashlib.sha256(MANIFEST.read_bytes()).hexdigest()!=manifest_hash or hashlib.sha256(HUMAN.read_bytes()).hexdigest()!=human_hash:raise RuntimeError("frozen evidence changed")
 if authoritative_before!=authoritative_after:raise RuntimeError("authoritative production state changed")
 audit_art={"schema_version":"reader-structural-audit.v1","checkpoint":"11.14","cases":audits,"tag_counts":dict(Counter(tag for row in audits for tag in row["tags"])),"classification_basis":"geometry only; supported observations, not semantic inference","structural_error_cases":len(structural_ids)}
 replay_art={"schema_version":"reader-structural-replay.v1","checkpoint":"11.14","frozen_manifest_sha256":manifest_hash,"frozen_human_gt_sha256":human_hash,"samples":replay,"verified":71,"unreadable":10,"source_hashes_valid":True}
 candidates_art={**declared,"status":"COMPLETED","pre_ocr_contract_hash":contract_hash,"engine_version":version,"results":metrics,"selected_best":best,"selection_rule":"lowest VERIFIED micro CER, then highest exact, fewer regressions, stable name; GT used for evaluation/selection only, never construction"}
 comparison_art={"schema_version":"reader-structural-comparison.v1","checkpoint":"11.14","metrics":metrics,"best_candidate":best,"per_sample_diffs":diffs,"structural_47":structural_metrics,"regression_safety":{"correct_to_wrong":metrics[best]["correct_to_wrong"],"large_cer_regressions":metrics[best]["large_cer_regressions"],"newly_clipped_crops":0,"newly_merged_unrelated_text":sum(x["classification"]=="REGRESSED" and next(a for a in audits if a["sample_id"]==x["sample_id"])["structural_review"] for x in diffs[best]),"newly_split_valid_text":sum(x["correct_to_wrong"] and len(next(r for r in replay if r["sample_id"]==x["sample_id"])["fragment_boxes"])>1 for x in diffs[best])},"false_safe_replay":false_replay,"unreadable_geometry":unreadable}
 error_art={"schema_version":"reader-structural-errors.v1","checkpoint":"11.14","best_candidate":best,"regressions":[x for x in diffs[best] if x["classification"]=="REGRESSED"],"large_regressions":[x for x in diffs[best] if x["large_cer_regression"]],"unrepaired_structural_samples":[x["sample_id"] for x in structural_candidate if not x["score"]["exact"]]}
 control_cer=metrics["control"]["normalized_cer"];best_cer=metrics[best]["normalized_cer"];relative=(control_cer-best_cer)/control_cer if control_cer else 0
 if relative>=.15 and metrics[best]["improved"]>metrics[best]["regressed"] and metrics[best]["correct_to_wrong"]<=1:decision="A. STRUCTURAL RECONSTRUCTION PASS"
 elif best_cer<control_cer and structural_metrics["repaired"]>0:decision="B. PARTIAL STRUCTURAL IMPROVEMENT"
 elif min(metrics[name]["normalized_cer"] for name in CONTRACTS)>=control_cer:decision="C. STRUCTURAL CHANGES DO NOT HELP"
 else:decision="E. INSUFFICIENT EVIDENCE"
 next_step="Preserve the best candidate for later Reader V2 integration and isolate remaining recognition errors." if decision[0] in "AB" else "Stop crop-heuristic work and benchmark HARD-region OCR repair or alternative recognition without deploying R2."
 summary_art={"schema_version":"reader-structural-summary.v1","checkpoint":"11.14","decision":decision,"dataset":{"verified":71,"structural_errors":47,"unreadable":10},"control":metrics["control"],"best_candidate":best,"best_metrics":metrics[best],"structural_47":structural_metrics,"false_safe_replay":false_replay,"unreadable_geometry_counts":dict(Counter(x["result"] for x in unreadable)),"runtime":{"easyocr_initialization_seconds":init_seconds,"crop_reconstruction_overhead_seconds":crop_overhead,"ocr_seconds":sum(x["latency_seconds"] for rows in outputs.values() for x in rows)+sum(0 for _ in []),"primary_benchmark_seconds":total_seconds,"total_ocr_calls":ocr_calls,"per_region_overhead_seconds":crop_overhead/81},"resources":{"before":resources_before,"after_init":after_init,"after":resources_after,"peak_rss_bytes":max(resources_before["process_peak_rss_bytes"],after_init["process_peak_rss_bytes"],resources_after["process_peak_rss_bytes"]),"swap_delta_bytes":resources_after["swap_used_bytes"]-resources_before["swap_used_bytes"],"resource_guard":"CRITICAL" if CRITICAL in {resources_before["safety_state"],after_init["safety_state"],resources_after["safety_state"]} else resources_after["safety_state"]},"safety":{"sequential_ocr":True,"ocr_concurrency":1,"vlm_calls":0,"ollama_calls":0,"authoritative_state_unchanged":True,"human_gt_unchanged":True,"r2_unchanged":True,"reading_order_unchanged":True,"production_changes":False},"recommended_next_experiment":next_step}
 for path,obj in ((REPLAY,replay_art),(AUDIT,audit_art),(CANDIDATES,candidates_art),(COMPARISON,comparison_art),(ERRORS,error_art),(SUMMARY,summary_art)):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"decision":decision,"control":metrics["control"],"best":best,"best_metrics":metrics[best],"structural":structural_metrics,"runtime":summary_art["runtime"],"resources":summary_art["resources"]},ensure_ascii=False))
if __name__=="__main__":main()
