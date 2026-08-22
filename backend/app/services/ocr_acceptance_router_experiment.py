from __future__ import annotations
import math,re,statistics,time
from typing import Any
SAFE="SAFE_CANDIDATE";HARD="HARD";STRUCTURAL="STRUCTURAL_REVIEW"
def signal_features(logical:dict[str,Any],fragments:list[dict[str,Any]])->dict[str,Any]:
 texts=[str(x.get("predicted_text", "")) for x in fragments];text=" ".join(x.strip() for x in texts if x.strip());compact="".join(text.split());conf=[float(x["ocr_confidence"]) for x in fragments if x.get("ocr_confidence") is not None];symbols=sum(not c.isalnum() and not c.isspace() for c in text);digits=sum(c.isdigit() for c in compact);runs=[len(x.group()) for x in re.finditer(r"(.)\1+",compact)];x1,y1,x2,y2=logical["bbox"];area=max(1.0,(x2-x1)*(y2-y1));fragment_count=len(fragments);boundary=min((min(x.get("crop_bbox",[1,1])[:2]) for x in fragments),default=1)<=0
 return {"text":text,"min_confidence":min(conf,default=0.0),"mean_confidence":statistics.mean(conf) if conf else 0.0,"confidence_spread":max(conf,default=0)-min(conf,default=0),"character_count":len(compact),"word_count":len(text.split()),"symbol_ratio":symbols/max(1,len(text)),"digit_ratio":digits/max(1,len(compact)),"max_repeated_run":max(runs,default=1),"suspicious_whitespace":bool(re.search(r"\s{2,}|^\s|\s$",text)),"fragment_count":fragment_count,"reconstruction_mode":"single_block" if fragment_count==1 else "multi_fragment_merge","merge_split_warning":fragment_count>1,"bbox_width":x2-x1,"bbox_height":y2-y1,"text_to_crop_density":len(compact)/area,"boundary_clipping_warning":boundary,"region_type":logical.get("region_type","unknown"),"aggregation_confidence":float(logical.get("aggregation_confidence",0)),"geometry_stable":logical.get("region_type")!="logical_text_region" or fragment_count==1}
def route(features:dict[str,Any],candidate:str)->str:
 structural=features["merge_split_warning"] or features["boundary_clipping_warning"]
 if candidate=="BASELINE":return SAFE if features["baseline_accepted"] else HARD
 if candidate=="R1":return SAFE if features["min_confidence"]>=.98 else HARD
 if candidate=="R2":return STRUCTURAL if structural else (SAFE if features["min_confidence"]>=.98 else HARD)
 sane=features["character_count"]>=4 and features["symbol_ratio"]<=.15 and features["max_repeated_run"]<=2 and not features["suspicious_whitespace"]
 if candidate=="R3":return STRUCTURAL if structural else (SAFE if features["min_confidence"]>=.98 and sane else HARD)
 if candidate=="R4":return STRUCTURAL if structural or not features["geometry_stable"] else (SAFE if features["min_confidence"]>=.995 and sane and features["confidence_spread"]<=.01 and 0<features["text_to_crop_density"]<=.02 else HARD)
 raise ValueError("unknown router candidate")
def metrics(rows:list[dict[str,Any]],candidate:str)->dict[str,Any]:
 started=time.perf_counter_ns();states=[route(x["features"],candidate) for x in rows];elapsed=time.perf_counter_ns()-started;safe=[x for x,s in zip(rows,states) if s==SAFE];correct=sum(x["correct"] for x in safe);false=len(safe)-correct;hard=sum(s==HARD for s in states);structural=sum(s==STRUCTURAL for s in states)
 return {"candidate":candidate,"safe_count":len(safe),"safe_coverage":len(safe)/len(rows),"safe_correct":correct,"false_safe":false,"false_safe_rate":false/len(safe) if safe else 0.0,"safe_precision":correct/len(safe) if safe else None,"hard_count":hard,"hard_rate":hard/len(rows),"structural_review_count":structural,"structural_review_rate":structural/len(rows),"correct_ocr_routed_hard":sum(x["correct"] and s!=SAFE for x,s in zip(rows,states)),"routing_nanoseconds":elapsed,"nanoseconds_per_region":elapsed/len(rows),"states":states}
def short_bucket(n:int)->str:return "1-3" if n<=3 else "4-8" if n<=8 else "9+"
