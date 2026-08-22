#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys,time,unicodedata
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"backend"),str(ROOT/"scripts")]
from app.services.ocr_acceptance_router_experiment import HARD,SAFE,STRUCTURAL,metrics,route,short_bucket,signal_features
from app.services.resource_safety import ResourceThresholds,sample_resources
DAY=ROOT/"benchmarks/day11";HUMAN=DAY/"reader-correctness-human-verified-11.11.json";LOGICAL=DAY/"reader-logical-region-sample-11.11.json";RAW=DAY/"reader-v2-correctness-review-sample-11.11.json";OCR=DAY/"reader-ocr-correctness-11.11.json"
def load_rows():
 human=json.loads(HUMAN.read_text());logical=json.loads(LOGICAL.read_text());raw=json.loads(RAW.read_text());ocr=json.loads(OCR.read_text());human_pages={p["asset_id"]:p for p in human["pages"]};raw_pages={p["asset_id"]:p for p in raw["pages"]};ocr_labels={(r["page_order"],r["logical_region_id"]):r for r in ocr["regions"]};rows=[]
 for page in logical["pages"]:
  hp=human_pages[page["asset_id"]];frags={r["region_id"]:r for r in raw_pages[page["asset_id"]]["regions"]}
  for lr in page["logical_regions"]:
   lid=lr["logical_region_id"]
   if lid not in hp["human_transcriptions"]:continue
   source=[frags[x] for x in lr["source_fragment_ids"]];features=signal_features(lr,source);features["baseline_accepted"]=all(x["routing_state"]=="ACCEPT_CANDIDATE" for x in source);label=ocr_labels[(page["page_order"],lid)]
   rows.append({"sample_id":f"p{page['page_order']}:{lid}","asset_id":page["asset_id"],"page_order":page["page_order"],"logical_region_id":lid,"source_hash":page["source_hash"],"bbox":lr["bbox"],"source_fragment_ids":lr["source_fragment_ids"],"crop_metadata":{"bbox_width":features["bbox_width"],"bbox_height":features["bbox_height"]},"ocr_output":label["prediction"],"human_gt":hp["human_transcriptions"][lid],"correct":label["exact"],"features":features,"error_types":[]})
 return rows
def choose(results):
 eligible=[x for x in results if x["candidate"]!="R1"]
 zero=[x for x in eligible if x["false_safe"]==0 and x["safe_count"]>0]
 return max(zero,key=lambda x:x["safe_count"],default=min(eligible,key=lambda x:(x["false_safe_rate"],-x["safe_count"]))) ["candidate"]
def text_error_types(pred,human):
 p=" ".join(pred.upper().split());h=" ".join(human.upper().split());types=[];plain=lambda x:"".join(c for c in unicodedata.normalize("NFD",x) if unicodedata.category(c)!="Mn")
 if plain(p)==plain(h) and p!=h:types.append("diacritic error")
 if "".join(c for c in p if c.isalnum() or c.isspace())=="".join(c for c in h if c.isalnum() or c.isspace()) and p!=h:types.append("punctuation error")
 if len(p)<len(h):types.append("missing character/text")
 elif len(p)>len(h):types.append("extra character/text")
 elif p!=h:types.append("wrong character")
 return types or ["other"]
def run():
 before=sample_resources(ResourceThresholds.from_environment());rows=load_rows();baseline=metrics(rows,"BASELINE");candidates=[metrics(rows,x) for x in ("R1","R2","R3","R4")];selected=choose(candidates);false_rows=[r for r,s in zip(rows,baseline["states"]) if s==SAFE and not r["correct"]];taxonomy=Counter();high_wrong=[];short=Counter()
 for r in false_rows:
  f=r["features"];short[short_bucket(f["character_count"])]+=1
  r["error_types"]=text_error_types(r["ocr_output"],r["human_gt"])
  for kind in r["error_types"]:taxonomy[kind]+=1
  if f["merge_split_warning"]:taxonomy["merged/split reconstruction"]+=1;r["error_types"].append("merged/split reconstruction")
  if f["min_confidence"]>=.95:taxonomy["high-confidence wrong OCR"]+=1;high_wrong.append(r["sample_id"])
  if f["character_count"]<=8:taxonomy["short-text ambiguity"]+=1
  if f["symbol_ratio"]>.15:taxonomy["symbol/background contamination"]+=1
  if f["boundary_clipping_warning"]:taxonomy["truncated/boundary crop"]+=1
  if not any((f["merge_split_warning"],f["min_confidence"]>=.95,f["character_count"]<=8,f["symbol_ratio"]>.15,f["boundary_clipping_warning"])):taxonomy["plausible single-block text"]+=1
 audit_rows=[]
 for r in false_rows:audit_rows.append({k:r[k] for k in ("sample_id","asset_id","page_order","logical_region_id","source_hash","bbox","source_fragment_ids","ocr_output","human_gt","features","error_types")})
 baseline_art={"schema_version":"reader-router-baseline.v1","checkpoint":"11.12","dataset_size":len(rows),"gt_source":"Human VERIFIED 11.11","historical_expected":{"accepted":44,"false_accepts":36},"reproduced":{k:v for k,v in baseline.items() if k!="states"},"hard_count":baseline["hard_count"],"hard_rate":baseline["hard_rate"],"human_gt_hash":hashlib.sha256(HUMAN.read_bytes()).hexdigest(),"ocr_inference_calls":0,"vlm_calls":0,"ollama_calls":0}
 audit={"schema_version":"reader-router-false-safe-audit.v1","checkpoint":"11.12","false_safe_count":len(false_rows),"taxonomy":dict(taxonomy),"short_text_buckets":dict(short),"high_confidence_wrong_count":len(high_wrong),"high_confidence_wrong_samples":high_wrong,"runtime_signal_rule":"Human GT labels correctness only; no GT-derived feature is exposed to routers.","cases":audit_rows}
 candidate_art={"schema_version":"reader-router-candidates.v1","checkpoint":"11.12","benchmark_fitted":True,"contracts":{"SAFE_CANDIDATE":"multiple cheap signals agree; benchmark evidence only","HARD":"weak evidence defaults to escalation","STRUCTURAL_REVIEW":"merge/split, crop boundary, or geometry structure is questionable"},"definitions":{"R1":"min confidence >= 0.98","R2":"R1 + single fragment + no boundary warning","R3":"R2 + >=4 chars + sane symbols/repeats/whitespace","R4":"R3 at confidence >=0.995 + <=0.01 confidence spread + stable geometry + conservative density"},"results":[{k:v for k,v in x.items() if k!="states"} for x in candidates],"selected_for_analysis":selected,"deployment":"NONE"}
 # Stability asks whether the benchmark-selected rule changes when one sample/page is removed.
 loo=Counter();lop=Counter();ranges={x:{"coverage":[],"false_safe":[]} for x in ("R1","R2","R3","R4")}
 for i in range(len(rows)):
  subset=rows[:i]+rows[i+1:];res=[metrics(subset,x) for x in ranges];loo[choose(res)]+=1
  for x,m in zip(ranges,res):ranges[x]["coverage"].append(m["safe_coverage"]);ranges[x]["false_safe"].append(m["false_safe"])
 for page in sorted({r["page_order"] for r in rows}):lop[choose([metrics([r for r in rows if r["page_order"]!=page],x) for x in ranges])]+=1
 sensitivity=[]
 for threshold in (.97,.98,.99,.995):
  states=[STRUCTURAL if r["features"]["merge_split_warning"] or r["features"]["boundary_clipping_warning"] else SAFE if r["features"]["min_confidence"]>=threshold and r["features"]["character_count"]>=4 and r["features"]["symbol_ratio"]<=.15 else HARD for r in rows];safe=[r for r,s in zip(rows,states) if s==SAFE];sensitivity.append({"threshold":threshold,"safe":len(safe),"false_safe":sum(not r["correct"] for r in safe),"precision":sum(r["correct"] for r in safe)/len(safe) if safe else None})
 stability={"schema_version":"reader-router-stability.v1","checkpoint":"11.12","small_data_warning":"N=50 across 10 pages; candidates are BENCHMARK-FITTED, not production-calibrated.","leave_one_out_selected_rule_counts":dict(loo),"leave_one_page_out_selected_rule_counts":dict(lop),"candidate_ranges":{x:{"coverage_min":min(v["coverage"]),"coverage_max":max(v["coverage"]),"false_safe_min":min(v["false_safe"]),"false_safe_max":max(v["false_safe"])} for x,v in ranges.items()},"R3_confidence_sensitivity":sensitivity}
 merged=[r for r in rows if r["features"]["merge_split_warning"]];selected_metric=next(x for x in candidates if x["candidate"]==selected);states=selected_metric["states"];merged_selected=[(r,s) for r,s in zip(rows,states) if r["features"]["merge_split_warning"]];short_analysis={b:{"count":sum(short_bucket(r["features"]["character_count"])==b for r in rows),"wrong":sum(short_bucket(r["features"]["character_count"])==b and not r["correct"] for r in rows)} for b in ("1-3","4-8","9+")}
 old=json.loads((DAY/"reader-v2-fast-pass-11.8.json").read_text());old_accept=[r for r in old["results"] if r["routing_state"]=="ACCEPT_CANDIDATE"]
 old_r1=[r for r in old_accept if (r.get("ocr",{}).get("confidence") or 0)>=.98];old_r2=[r for r in old_r1 if len(r.get("ocr",{}).get("lines",[]))==1]
 after=sample_resources(ResourceThresholds.from_environment());swap_delta=(after["swap_used_bytes"]-before["swap_used_bytes"] if after["swap_used_bytes"] is not None and before["swap_used_bytes"] is not None else None);summary={"schema_version":"reader-router-summary.v1","checkpoint":"11.12","decision":"B. ROUTER PROMISING BUT MORE GT REQUIRED","decision_basis":"R2 combines confidence with structural agreement and has 1/50 SAFE with 0 observed false-safe, but its 2% coverage and single-page dependence are not production evidence.","selected_candidate":selected,"selected_metrics":{k:v for k,v in selected_metric.items() if k!="states"},"merged_split_analysis":{"cases":len(merged),"caught_structural":sum(s==STRUCTURAL for _,s in merged_selected),"missed_non_structural":sum(s!=STRUCTURAL for _,s in merged_selected),"false_safe_merged_split":sum(s==SAFE and not r["correct"] for r,s in merged_selected)},"short_text_analysis":short_analysis,"high_confidence_wrong":{"count":len(high_wrong),"threshold":"min fragment confidence >= 0.95","additional_signals_that_catch":"No wrong sample crosses the descriptive high-confidence threshold; merge/split structural warning still catches multi-fragment cases below it."},"regression_11_8":{"historical_accepts":19,"historical_false_accepts":16,"R1_would_safe":len(old_r1),"R2_single_line_would_safe":len(old_r2),"note":"11.8 lacks the new logical aggregation features; comparison is limited to confidence and OCR-line structure."},"regression_11_11":{"baseline_false_accepts":baseline["false_safe"],"selected_false_safe":selected_metric["false_safe"],"selected_safe_count":selected_metric["safe_count"]},"runtime":{"routing_nanoseconds":selected_metric["routing_nanoseconds"],"nanoseconds_per_region":selected_metric["nanoseconds_per_region"]},"resource_safety":{"before":before,"after":after,"swap_delta_bytes":swap_delta,"ocr_inference_calls":0,"vlm_calls":0,"ollama_calls":0},"reading_order_deferred":"shared tier/row grouping geometry; intentionally unchanged","production_changes":False,"single_next_action":"Validate the benchmark-fitted R2 contract on a new page-grouped Human GT set; do not deploy or relax it."}
 for name,obj in (("reader-router-baseline-11.12.json",baseline_art),("reader-router-false-safe-audit-11.12.json",audit),("reader-router-candidates-11.12.json",candidate_art),("reader-router-stability-11.12.json",stability),("reader-router-summary-11.12.json",summary)):(DAY/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
 return baseline_art,audit,candidate_art,stability,summary
if __name__=="__main__":
 b,a,c,s,m=run();print(json.dumps({"baseline":b["reproduced"],"candidates":c["results"],"stability":{"loo":s["leave_one_out_selected_rule_counts"],"lop":s["leave_one_page_out_selected_rule_counts"]},"summary":m},ensure_ascii=False))
