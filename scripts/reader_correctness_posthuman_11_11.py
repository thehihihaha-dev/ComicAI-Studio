#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys,unicodedata
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"backend"),str(ROOT/"scripts")]
from dotenv import load_dotenv
load_dotenv(ROOT/"backend/.env")
from app.database import SessionLocal
from app.models.asset import Asset
from app.models.reader_correctness_review import ReaderCorrectnessReview
from app.models.reader_logical_review import ReaderLogicalReview
from app.services.resource_safety import ResourceThresholds,sample_resources
from reader_benchmark import authoritative_snapshot
PROJECT="e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2";DAY=ROOT/"benchmarks/day11";MANIFEST=DAY/"reader-logical-region-sample-11.11.json";RAW=DAY/"reader-v2-correctness-review-sample-11.11.json"
def stable(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def norm(text):return " ".join(unicodedata.normalize("NFC",text).upper().split())
def distance(a,b):
 prev=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  cur=[i]
  for j,y in enumerate(b,1):cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
  prev=cur
 return prev[-1]
def pair_metrics(pred,human):
 pos={x:i for i,x in enumerate(human)};total=inv=0
 for i,a in enumerate(pred):
  for b in pred[i+1:]:total+=1;inv+=pos[a]>pos[b]
 return total,inv
def mismatch_cause(a,b,regions):
 aa,bb=regions[a]["bbox"],regions[b]["bbox"];acy=(aa[1]+aa[3])/2;bcy=(bb[1]+bb[3])/2;ah=aa[3]-aa[1];bh=bb[3]-bb[1]
 if abs(acy-bcy)<=max(4,min(ah,bh)*.6):return "B. right-to-left ordering error"
 if acy>bcy:return "C. top-to-bottom ordering error"
 return "A. row grouping error"
def build():
 before_res=sample_resources(ResourceThresholds.from_environment());before_state=authoritative_snapshot(PROJECT)["state_hash"];manifest=json.loads(MANIFEST.read_text());raw=json.loads(RAW.read_text());raw_by_asset={p["asset_id"]:p for p in raw["pages"]};db=SessionLocal();verified=[];pages=[];error_rows=[];ocr_rows=[];aggregate=Counter();ocr_types=Counter();prediction_hash_before=hashlib.sha256(MANIFEST.read_bytes()).hexdigest();old11_hash=hashlib.sha256((DAY/"reader-reading-order-comparison-11.9.json").read_bytes()).hexdigest()
 try:
  for page in manifest["pages"]:
   row=db.query(ReaderLogicalReview).filter_by(asset_id=page["asset_id"],representation_hash=page["representation_hash"]).one();asset=db.get(Asset,row.asset_id);ordered=row.human_ordered_region_ids or [];excluded=row.human_excluded_region_ids or [];expected={r["logical_region_id"] for r in row.logical_regions}
   if row.state!="VERIFIED" or set(ordered)|set(excluded)!=expected or set(ordered)&set(excluded):raise RuntimeError(f"Human GT incomplete: page {row.page_order}")
   human={"asset_id":row.asset_id,"page_order":row.page_order,"source_hash":row.source_image_hash,"representation_hash":row.representation_hash,"representation_version":row.human_representation_version,"ordered_region_ids":ordered,"excluded_region_ids":excluded,"human_transcriptions":row.human_transcriptions or {},"verified":True,"revision":row.revision};verified.append(human)
   predicted_original=list(page["predicted_sequence"]);pred=[x for x in predicted_original if x in set(ordered)];missing=[x for x in ordered if x not in predicted_original];extra=[x for x in predicted_original if x not in expected];excluded_predicted=[x for x in predicted_original if x in set(excluded)];total,inv=pair_metrics(pred,ordered) if set(pred)==set(ordered) else (0,0);position_correct=sum(i<len(pred) and pred[i]==x for i,x in enumerate(ordered));moved=sum(i>=len(pred) or pred[i]!=x for i,x in enumerate(ordered));exact=pred==ordered and not missing
   region_map={r["logical_region_id"]:r for r in page["logical_regions"]};causes=Counter()
   pos={x:i for i,x in enumerate(ordered)}
   for i,a in enumerate(pred):
    for b in pred[i+1:]:
     if pos[a]>pos[b]:causes[mismatch_cause(a,b,region_map)]+=1
   if excluded_predicted:causes["H. region should have been excluded"]+=len(excluded_predicted)
   for k,v in causes.items():aggregate[k]+=v
   error_rows.append({"page_order":row.page_order,"exact":exact,"inversions":inv,"moved_regions":moved,"excluded_predicted":len(excluded_predicted),"causes":dict(causes),"same_rule_cluster":"tiered_order geometry" if inv else None})
   pages.append({"page_order":row.page_order,"predicted_original":predicted_original,"predicted_scored_after_human_exclusion":pred,"human_order":ordered,"human_excluded":excluded,"exact":exact,"position_correct":position_correct,"position_total":len(ordered),"pairwise_correct":total-inv,"pairwise_total":total,"inversions":inv,"moved_regions":moved,"missing_predicted_regions":missing,"extra_predicted_regions":extra,"excluded_regions_predicted_as_readable":excluded_predicted,"ambiguous_unresolved":0})
   raw_page=raw_by_asset[row.asset_id];fragment_by_id={r["region_id"]:r for r in raw_page["regions"]}
   for lrid,human_text in (row.human_transcriptions or {}).items():
    lr=region_map[lrid];frags=[fragment_by_id[x] for x in lr["source_fragment_ids"]];frags.sort(key=lambda r:(r["bbox"][1],r["bbox"][0],r["region_id"]));pred_text=" ".join(r["predicted_text"].strip() for r in frags if r["predicted_text"].strip());pn,hn=norm(pred_text),norm(human_text);char_err=distance(pn,hn);word_err=distance(pn.split(),hn.split());accepted=all(r["routing_state"]=="ACCEPT_CANDIDATE" for r in frags);exact_text=pn==hn
    if char_err:
     if pn.replace(" ","")==hn.replace(" ",""):ocr_types["spacing"]+=1
     elif "".join(c for c in pn if c.isalnum() or c.isspace())=="".join(c for c in hn if c.isalnum() or c.isspace()):ocr_types["punctuation"]+=1
     elif len(pn)<len(hn):ocr_types["missing character/text"]+=1
     elif len(pn)>len(hn):ocr_types["extra character/text"]+=1
     else:ocr_types["wrong character"]+=1
     if len(frags)>1:ocr_types["merged/split fragment reconstruction"]+=1
    ocr_rows.append({"page_order":row.page_order,"logical_region_id":lrid,"source_fragment_ids":lr["source_fragment_ids"],"prediction":pred_text,"human_gt":human_text,"exact":exact_text,"char_errors":char_err,"human_chars":len(hn),"word_errors":word_err,"human_words":len(hn.split()),"routing_state":"ACCEPT_CANDIDATE" if accepted else "HARD_REVIEW","false_accept":accepted and not exact_text})
 finally:db.close()
 exact_pages=sum(p["exact"] for p in pages);pos_correct=sum(p["position_correct"] for p in pages);pos_total=sum(p["position_total"] for p in pages);pair_correct=sum(p["pairwise_correct"] for p in pages);pair_total=sum(p["pairwise_total"] for p in pages);inversions=sum(p["inversions"] for p in pages);exact_ocr=sum(r["exact"] for r in ocr_rows);char_errors=sum(r["char_errors"] for r in ocr_rows);chars=sum(r["human_chars"] for r in ocr_rows);word_errors=sum(r["word_errors"] for r in ocr_rows);words=sum(r["human_words"] for r in ocr_rows);false_accept=sum(r["false_accept"] for r in ocr_rows);accepted=sum(r["routing_state"]=="ACCEPT_CANDIDATE" for r in ocr_rows);hard=len(ocr_rows)-accepted
 human_art={"schema_version":"reader-human-verified.v2","checkpoint":"11.11","status":"VERIFIED","total_pages":len(verified),"ordered_regions":sum(len(x["ordered_region_ids"]) for x in verified),"excluded_regions":sum(len(x["excluded_region_ids"]) for x in verified),"human_transcriptions":sum(len(x["human_transcriptions"]) for x in verified),"unreadable_regions":0,"pages":verified}
 comparison={"schema_version":"reader-order-comparison.v2","checkpoint":"11.11","prediction_source":MANIFEST.name,"scoring_note":"Original prediction is immutable; Human-excluded regions are reported separately and removed only from pair/order scoring.","metrics":{"exact_page_order":{"correct":exact_pages,"total":len(pages),"accuracy":exact_pages/len(pages)},"exact_region_position":{"correct":pos_correct,"total":pos_total,"accuracy":pos_correct/pos_total if pos_total else 1},"pairwise":{"correct":pair_correct,"total":pair_total,"accuracy":pair_correct/pair_total if pair_total else 1},"total_inversions":inversions,"pages_requiring_correction":len(pages)-exact_pages,"moved_regions":sum(p["moved_regions"] for p in pages),"excluded_regions":sum(len(p["human_excluded"]) for p in pages),"missing_predicted_regions":sum(len(p["missing_predicted_regions"]) for p in pages),"extra_predicted_regions":sum(len(p["extra_predicted_regions"]) for p in pages),"ambiguous_unresolved":sum(p["ambiguous_unresolved"] for p in pages)},"pages":pages}
 errors={"schema_version":"reader-order-errors.v1","checkpoint":"11.11","aggregate_causes":dict(aggregate),"dominant_rule_cluster":"tiered_order row/tier geometry" if aggregate else None,"pages":error_rows}
 ocr={"schema_version":"reader-ocr-correctness.v2","checkpoint":"11.11","gt_source":"human logical-region transcription only","normalization":"Unicode NFC + uppercase + collapsed whitespace","metrics":{"samples":len(ocr_rows),"exact_match":{"correct":exact_ocr,"accuracy":exact_ocr/len(ocr_rows)},"normalized_cer":char_errors/chars if chars else 0,"wer":word_errors/words if words else 0,"false_accept_count":false_accept,"false_accept_rate":false_accept/accepted if accepted else 0,"true_accepted_count":accepted-false_accept,"accepted_count":accepted,"hard_review_count":hard,"unreadable_count":0},"error_types":dict(ocr_types),"regions":ocr_rows}
 after_state=authoritative_snapshot(PROJECT)["state_hash"];after_res=sample_resources(ResourceThresholds.from_environment());value_differences=sum(x["ordered_region_ids"]!=[rid for rid in next(p["predicted_sequence"] for p in manifest["pages"] if p["asset_id"]==x["asset_id"]) if rid not in set(x["excluded_region_ids"])] for x in verified);preservation={"human_gt_storage_separate_from_prediction":True,"pages_where_human_order_differs_from_scored_prediction":value_differences,"prediction_artifact_unchanged":prediction_hash_before==hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),"ground_truth_11_9_artifact_unchanged":old11_hash==hashlib.sha256((DAY/"reader-reading-order-comparison-11.9.json").read_bytes()).hexdigest(),"authoritative_state_unchanged":before_state==after_state}
 order_verdict="A. PASS — geometry sufficiently reliable for current benchmark" if exact_pages==len(pages) else ("B. PASS WITH DETERMINISTIC FIXES" if pair_total and pair_correct/pair_total>=.90 else "C. FAIL — geometry requires redesign")
 ocr_verdict="A. FAST PASS OCR ACCEPTABLE" if accepted and false_accept/accepted<=.02 else ("B. ROUTER/CORRECTNESS FIX REQUIRED" if accepted else "D. INSUFFICIENT HUMAN GT")
 next_action="Redesign the OCR ACCEPT_CANDIDATE rule using observed false-safe logical-region errors before changing the OCR engine." if false_accept else "Implement one deterministic tiered-order geometry fix targeting the dominant inversion cluster."
 summary={"schema_version":"reader-correctness-summary.v2","checkpoint":"11.11","human_gt_complete":True,"reading_order_verdict":order_verdict,"ocr_verdict":ocr_verdict,"single_next_action":next_action,"preservation":preservation,"resource_safety":{"before":before_res,"after":after_res,"swap_delta_bytes":after_res["swap_used_bytes"]-before_res["swap_used_bytes"],"new_ocr_inference_calls":0,"vlm_calls":0,"ollama_calls":0},"artifact_hashes":{"prediction_manifest":prediction_hash_before,"11_9_gt":old11_hash}}
 for path,obj in ((DAY/"reader-correctness-human-verified-11.11.json",human_art),(DAY/"reader-reading-order-comparison-11.11.json",comparison),(DAY/"reader-reading-order-errors-11.11.json",errors),(DAY/"reader-ocr-correctness-11.11.json",ocr),(DAY/"reader-correctness-summary-11.11.json",summary)):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
 return summary,comparison,ocr,errors
if __name__=="__main__":
 s,c,o,e=build();print(json.dumps({"reading":c["metrics"],"ocr":o["metrics"],"errors":e["aggregate_causes"],"summary":s},ensure_ascii=False))
