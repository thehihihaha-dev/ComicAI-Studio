#!/usr/bin/env python3
from __future__ import annotations
import hashlib,importlib.metadata,json,os,sys,time,unicodedata
from collections import Counter
from pathlib import Path
import numpy as np
from dotenv import load_dotenv
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];BACKEND=ROOT/"backend";sys.path[:0]=[str(BACKEND),str(ROOT/"scripts")];load_dotenv(BACKEND/".env");os.chdir(BACKEND)
from app.services.logical_crop_reconstruction_experiment import adaptive_box
from app.services.resource_safety import CRITICAL,ResourceThresholds,sample_resources
from reader_benchmark import authoritative_snapshot,result_json
from reader_router_experiment_11_12 import text_error_types
DAY=ROOT/"benchmarks/day11";REPLAY=DAY/"reader-structural-replay-11.14.json";HUMAN=DAY/"reader-router-validation-human-gt-11.13.json";CONTROL13=DAY/"reader-router-validation-results-11.13.json";COMP14=DAY/"reader-structural-comparison-11.14.json";MODEL=Path.home()/".paddlex/official_models/PP-OCRv6_medium_rec";PROJECT="e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2"
MANIFEST=DAY/"reader-residual-recognition-manifest-11.15.json";CONTROL=DAY/"reader-residual-recognition-control-11.15.json";CANDIDATE=DAY/"reader-residual-recognition-candidate-11.15.json";ERRORS=DAY/"reader-residual-recognition-errors-11.15.json";PERFORMANCE=DAY/"reader-residual-recognition-performance-11.15.json";SUMMARY=DAY/"reader-residual-recognition-summary-11.15.json"
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
def compare(control,candidate):
 changes=[]
 for sid,base in control.items():
  row=candidate[sid];delta=row["score"]["cer"]-base["score"]["cer"];changes.append({"sample_id":sid,"classification":"IMPROVED" if delta<0 else "REGRESSED" if delta>0 else "UNCHANGED","wrong_to_correct":not base["score"]["exact"] and row["score"]["exact"],"correct_to_wrong":base["score"]["exact"] and not row["score"]["exact"],"control_output":base["output"],"candidate_output":row["output"],"control_cer":base["score"]["cer"],"candidate_cer":row["score"]["cer"]})
 return changes
def predict(model,crop):
 started=time.perf_counter();values=list(model.predict(np.asarray(crop)));elapsed=time.perf_counter()-started;data=result_json(values[0]) if values else {};text=str(data.get("rec_text",data.get("text","")));value=data.get("rec_score",data.get("score"));return text,(float(value) if value is not None else None),elapsed
def main():
 if not MODEL.is_dir():raise SystemExit("cached PP-OCRv6_medium_rec missing; no download attempted")
 replay=json.loads(REPLAY.read_text());human=json.loads(HUMAN.read_text());control13=json.loads(CONTROL13.read_text());comparison14=json.loads(COMP14.read_text());human_by={x["sample_id"]:x for x in human["samples"]};old_by={x["sample_id"]:x for x in control13["samples"]};adaptive_by={x["sample_id"]:x for x in comparison14["per_sample_diffs"]["adaptive_bounded"]};manifest_hash=hashlib.sha256(REPLAY.read_bytes()).hexdigest();human_hash=hashlib.sha256(HUMAN.read_bytes()).hexdigest();before_state=authoritative_snapshot(PROJECT)["state_hash"]
 protocol={"schema_version":"reader-residual-recognition-manifest.v1","checkpoint":"11.15","status":"FROZEN_BEFORE_CANDIDATE_INFERENCE","candidate":{"engine":"PaddleX create_model recognizer API","model":"PP-OCRv6_medium_rec","model_cache_bytes":sum(p.stat().st_size for p in MODEL.rglob("*") if p.is_file()),"framework_versions":{"paddlex":importlib.metadata.version("paddlex"),"paddleocr":importlib.metadata.version("paddleocr"),"paddlepaddle":importlib.metadata.version("paddlepaddle")},"model_file_sha256":{"inference.json":hashlib.sha256((MODEL/"inference.json").read_bytes()).hexdigest(),"inference.pdiparams":hashlib.sha256((MODEL/"inference.pdiparams").read_bytes()).hexdigest(),"inference.yml":hashlib.sha256((MODEL/"inference.yml").read_bytes()).hexdigest()},"recognizer_only":True,"detector_used":False,"device":"cpu","downloads":[]},"modes":{"A":"persisted EasyOCR 11.13 logical result","B":"frozen 11.14 adaptive 4%, 3–14px","C":"PP-OCRv6 medium recognizer on exact logical bbox","D":"PP-OCRv6 medium recognizer on frozen adaptive bbox"},"dataset":{"verified":71,"unreadable":10},"oracle":"Human GT used only after inference for scoring","frozen_replay_sha256":manifest_hash,"frozen_human_sha256":human_hash};protocol_hash=hashlib.sha256(json.dumps(protocol,sort_keys=True,separators=(",",":")).encode()).hexdigest();MANIFEST.write_text(json.dumps({**protocol,"protocol_hash":protocol_hash},ensure_ascii=False,indent=2)+"\n")
 control_a=[];control_b=[]
 for sample in replay["samples"]:
  if sample["human_state"]!="VERIFIED":continue
  truth=human_by[sample["sample_id"]]["human_transcription"];control_a.append({"sample_id":sample["sample_id"],"r2_state":old_by[sample["sample_id"]]["r2_state"],"output":sample["original_ocr_text"],"score":score(sample["original_ocr_text"],truth)});control_b.append({"sample_id":sample["sample_id"],"output":adaptive_by[sample["sample_id"]]["candidate_output"],"score":score(adaptive_by[sample["sample_id"]]["candidate_output"],truth)})
 thresholds=ResourceThresholds.from_environment();before_res=sample_resources(thresholds)
 if before_res["safety_state"]==CRITICAL:raise SystemExit("FAIL — MACHINE SAFETY")
 from paddlex import create_model
 init=time.perf_counter();model=create_model(MODEL.name,model_dir=str(MODEL),device="cpu");init_seconds=time.perf_counter()-init;after_init=sample_resources(thresholds)
 if after_init["safety_state"]==CRITICAL:raise SystemExit("FAIL — MACHINE SAFETY after init")
 modes={"C":[],"D":[]};unreadable=[];calls=0;started_all=time.perf_counter()
 for index,sample in enumerate(replay["samples"]):
  with Image.open(sample["source_image"]) as source:
   image=source.convert("RGB");boxes={"C":[round(x) for x in sample["logical_bbox"]],"D":adaptive_box(sample["logical_bbox"],image.size)};diagnostic={"sample_id":sample["sample_id"],"human_state":sample["human_state"],"structural_flags":sample["structural_flags"],"modes":{}}
   for mode,box in boxes.items():
    output,confidence,latency=predict(model,image.crop(tuple(box)));calls+=1;row={"sample_id":sample["sample_id"],"crop_bbox":box,"output":output,"confidence":confidence,"latency_seconds":latency,"cache_status":"MEASURED_THIS_RUN","recognizer_only":True};modes[mode].append(row)
    if sample["human_state"]=="VERIFIED":row["score"]=score(output,human_by[sample["sample_id"]]["human_transcription"]);row["r2_state"]=old_by[sample["sample_id"]]["r2_state"]
    else:diagnostic["modes"][mode]={"produced_output":bool(norm(output)),"output":output,"confidence":confidence,"disagrees_with_easyocr":norm(output)!=norm(sample["original_ocr_text"])}
   if sample["human_state"]=="UNREADABLE":unreadable.append(diagnostic)
  if index%10==9 and sample_resources(thresholds)["safety_state"]==CRITICAL:raise SystemExit("FAIL — MACHINE SAFETY during candidate")
 warm_total=time.perf_counter()-started_all;after_res=sample_resources(thresholds);after_state=authoritative_snapshot(PROJECT)["state_hash"]
 if before_state!=after_state:raise RuntimeError("authoritative state changed")
 if hashlib.sha256(REPLAY.read_bytes()).hexdigest()!=manifest_hash or hashlib.sha256(HUMAN.read_bytes()).hexdigest()!=human_hash:raise RuntimeError("frozen evidence changed")
 control_a_by={x["sample_id"]:x for x in control_a};control_b_by={x["sample_id"]:x for x in control_b};mode_by={name:{x["sample_id"]:x for x in rows if "score" in x} for name,rows in modes.items()};metrics={"A":aggregate(control_a),"B":aggregate(control_b),"C":aggregate(list(mode_by["C"].values())),"D":aggregate(list(mode_by["D"].values()))};changes={name:compare(control_a_by,mode_by[name]) for name in ("C","D")}
 for name in changes:metrics[name].update({"improved":sum(x["classification"]=="IMPROVED" for x in changes[name]),"unchanged":sum(x["classification"]=="UNCHANGED" for x in changes[name]),"regressed":sum(x["classification"]=="REGRESSED" for x in changes[name]),"wrong_to_correct":sum(x["wrong_to_correct"] for x in changes[name]),"correct_to_wrong":sum(x["correct_to_wrong"] for x in changes[name])})
 best=min(("C","D"),key=lambda name:(-metrics[name]["exact"],metrics[name]["normalized_cer"],metrics[name]["correct_to_wrong"],name));best_by=mode_by[best];best_changes=changes[best];wrong_ids={sid for sid,row in control_a_by.items() if not row["score"]["exact"]};residual=[x for x in best_changes if x["sample_id"] in wrong_ids];residual_chars=sum(control_a_by[sid]["score"]["human_chars"] for sid in wrong_ids);residual_control_errors=sum(control_a_by[sid]["score"]["char_errors"] for sid in wrong_ids);residual_candidate_errors=sum(best_by[sid]["score"]["char_errors"] for sid in wrong_ids);residual_metrics={"n":len(wrong_ids),"repaired_exact":sum(x["wrong_to_correct"] for x in residual),"repair_rate":sum(x["wrong_to_correct"] for x in residual)/len(wrong_ids),"improved":sum(x["classification"]=="IMPROVED" for x in residual),"unchanged":sum(x["classification"]=="UNCHANGED" for x in residual),"regressed":sum(x["classification"]=="REGRESSED" for x in residual),"control_cer":residual_control_errors/residual_chars,"candidate_cer":residual_candidate_errors/residual_chars,"cer_reduction":(residual_control_errors-residual_candidate_errors)/residual_chars}
 breakdown={}
 for state in ("HARD","STRUCTURAL_REVIEW"):
  ids={sid for sid,row in control_a_by.items() if row["r2_state"]==state};base=[control_a_by[sid] for sid in ids];candidate=[best_by[sid] for sid in ids];diff=[x for x in best_changes if x["sample_id"] in ids];breakdown[state]={"control":aggregate(base),"candidate":aggregate(candidate),"improved":sum(x["classification"]=="IMPROVED" for x in diff),"unchanged":sum(x["classification"]=="UNCHANGED" for x in diff),"regressed":sum(x["classification"]=="REGRESSED" for x in diff),"repairs":sum(x["wrong_to_correct"] for x in diff)}
 disagreements=Counter()
 for sid,base in control_a_by.items():
  candidate=best_by[sid];same=norm(base["output"])==norm(candidate["output"]);disagreements["equal" if same else "different"]+=1
  if not same:disagreements["easy_correct_candidate_wrong" if base["score"]["exact"] and not candidate["score"]["exact"] else "easy_wrong_candidate_correct" if not base["score"]["exact"] and candidate["score"]["exact"] else "both_wrong"]+=1
 oracle=sum(control_a_by[sid]["score"]["exact"] or best_by[sid]["score"]["exact"] for sid in control_a_by);false_id=next(sid for sid,row in control_a_by.items() if row["r2_state"]=="SAFE_CANDIDATE" and not row["score"]["exact"]);false_replay={"sample_id":false_id,"easyocr":control_a_by[false_id]["output"],"candidate":best_by[false_id]["output"],"human_gt":human_by[false_id]["human_transcription"],"repaired":best_by[false_id]["score"]["exact"]}
 taxonomy=Counter();error_cases=[]
 for sid,row in best_by.items():
  if row["score"]["exact"]:continue
  truth=human_by[sid]["human_transcription"];types=text_error_types(row["output"],truth)
  if ('"' in row["output"] or '"' in truth) and norm(row["output"])!=norm(truth):types.append("quote character")
  if norm(row["output"]).replace(" ","")==norm(truth).replace(" ","") and norm(row["output"])!=norm(truth):types.append("spacing")
  if len(next(x for x in replay["samples"] if x["sample_id"]==sid)["fragment_boxes"])>1:types.append("reconstruction/multi-fragment")
  for kind in set(types):taxonomy[kind]+=1
  error_cases.append({"sample_id":sid,"output":row["output"],"human_gt":truth,"types":sorted(set(types))})
 latencies=[x["latency_seconds"] for x in modes[best]];warm_verified=[x["latency_seconds"] for x in modes[best] if "score" in x];mean=sum(warm_verified)/len(warm_verified);cost={str(rate):{"estimated_calls_per_100_regions":round(100*rate),"estimated_seconds_per_100_regions":100*rate*mean} for rate in (.10,.25,.50,1.0)};swap_delta=after_res["swap_used_bytes"]-before_res["swap_used_bytes"]
 if residual_metrics["repair_rate"]>=.20 and metrics[best]["correct_to_wrong"]<=1:decision="A. RESIDUAL RECOGNIZER STRONGLY HELPS"
 elif residual_metrics["repaired_exact"]>0 and residual_metrics["improved"]>residual_metrics["regressed"]:decision="B. RESIDUAL RECOGNIZER PARTIALLY HELPS"
 elif metrics[best]["exact"]<=metrics["A"]["exact"] and metrics[best]["normalized_cer"]>=metrics["A"]["normalized_cer"]:decision="C. CANDIDATE DOES NOT JUSTIFY COST"
 else:decision="D. RECOGNITION ENGINE IS NOT THE MAIN LIMIT"
 next_action="Preserve PP-OCRv6 medium as a residual-recognition candidate and isolate the remaining dominant failure before integration." if decision.startswith(("A.","B.")) else "Do not add PP-OCRv6 medium to Reader V2; run the isolated shared tier/row Reading Order geometry experiment next."
 control_art={"schema_version":"reader-residual-recognition-control.v1","checkpoint":"11.15","metrics":{"A":metrics["A"],"B":metrics["B"]},"mode_a":control_a,"mode_b":control_b}
 candidate_art={"schema_version":"reader-residual-recognition-candidate.v1","checkpoint":"11.15","candidate":protocol["candidate"],"protocol_hash":protocol_hash,"metrics":{"C":metrics["C"],"D":metrics["D"]},"selected_mode":best,"selection_rule":"highest exact, then lowest micro CER, fewer correct-to-wrong, stable mode","mode_c":modes["C"],"mode_d":modes["D"],"unreadable_diagnostic":unreadable}
 errors_art={"schema_version":"reader-residual-recognition-errors.v1","checkpoint":"11.15","selected_mode":best,"taxonomy":dict(taxonomy),"cases":error_cases,"high_confidence_false_safe_replay":false_replay,"disagreement":dict(disagreements),"per_sample_changes":best_changes}
 performance_art={"schema_version":"reader-residual-recognition-performance.v1","checkpoint":"11.15","cold_initialization_seconds":init_seconds,"warm_total_seconds_all_162_calls":warm_total,"selected_mode_total_seconds_81_regions":sum(latencies),"selected_mode_verified_total_seconds":sum(warm_verified),"mean_warm_region_seconds":mean,"ocr_calls":calls,"estimated_cost_per_100_regions":cost,"estimate_note":"Linear warm-latency estimate; excludes cold initialization and concurrency effects.","resources":{"before":before_res,"after_init":after_init,"after":after_res,"peak_rss_bytes":max(before_res["process_peak_rss_bytes"],after_init["process_peak_rss_bytes"],after_res["process_peak_rss_bytes"]),"available_memory_after_bytes":after_res["system_available_memory_bytes"],"swap_delta_bytes":swap_delta,"resource_guard":"CRITICAL" if CRITICAL in {before_res["safety_state"],after_init["safety_state"],after_res["safety_state"]} else after_res["safety_state"]},"concurrency":1,"vlm_calls":0,"ollama_calls":0}
 summary_art={"schema_version":"reader-residual-recognition-summary.v1","checkpoint":"11.15","decision":decision,"candidate":"PP-OCRv6_medium_rec","selected_mode":best,"dataset":{"verified":71,"unreadable":10,"residual_wrong":len(wrong_ids)},"metrics":metrics,"residual":residual_metrics,"breakdown":breakdown,"false_safe_replay":false_replay,"disagreement":dict(disagreements),"oracle_upper_bound_not_production_achievable":{"exact":oracle,"n":71,"accuracy":oracle/71},"performance":performance_art,"safety":{"human_gt_unchanged":True,"r2_unchanged":True,"reading_order_unchanged":True,"production_ocr_unchanged":True,"authoritative_state_unchanged":True,"vlm_calls":0,"ollama_calls":0},"recommended_11_16_action":next_action}
 for path,obj in ((CONTROL,control_art),(CANDIDATE,candidate_art),(ERRORS,errors_art),(PERFORMANCE,performance_art),(SUMMARY,summary_art)):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"decision":decision,"best_mode":best,"metrics":metrics,"residual":residual_metrics,"breakdown":breakdown,"disagreement":dict(disagreements),"oracle":summary_art["oracle_upper_bound_not_production_achievable"],"false_safe":false_replay,"performance":performance_art},ensure_ascii=False))
if __name__=="__main__":main()
