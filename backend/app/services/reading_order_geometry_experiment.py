from __future__ import annotations
import statistics
from typing import Any

MANGA="MANGA";WEBTOON="WEBTOON"
def box(item):return [float(x) for x in item["bbox"]]
def height(item):b=box(item);return b[3]-b[1]
def vertical_overlap(a,b):
 aa,bb=box(a),box(b);return max(0,min(aa[3],bb[3])-max(aa[1],bb[1]))/max(1,min(height(a),height(b)))
def center_distance(a,b):
 aa,bb=box(a),box(b);return abs((aa[1]+aa[3]-bb[1]-bb[3])/2)/max(1,min(height(a),height(b)))
def contains(a,b,tolerance=2):
 aa,bb=box(a),box(b);return bb[0]>=aa[0]-tolerance and bb[1]>=aa[1]-tolerance and bb[2]<=aa[2]+tolerance and bb[3]<=aa[3]+tolerance
def same_tier(a,b,rule,median_height):
 overlap,center=vertical_overlap(a,b),center_distance(a,b);tall=max(height(a),height(b))>median_height*1.8
 if rule=="A_VERTICAL_OVERLAP":return overlap>=.50
 if rule=="B_NORMALIZED_CENTER":return center<=.50
 if rule=="C_HYBRID_TALL_PROTECTION":return center<=.35 if tall else (overlap>=.30 and center<=.75) or center<=.35
 raise ValueError("unknown benchmark-fitted rule")
def tier_order(items:list[dict[str,Any]],rule:str,source_type:str=MANGA)->dict[str,Any]:
 if source_type not in {MANGA,WEBTOON}:raise ValueError("unsupported source type")
 if not items:return {"order":[],"tiers":[],"ambiguous":[]}
 median=statistics.median(height(item) for item in items);tiers=[];ambiguous=[]
 for item in sorted(items,key=lambda x:(box(x)[1],box(x)[0],str(x["id"]))):
  matches=[tier for tier in tiers if any(same_tier(item,peer,rule,median) for peer in tier)]
  if len(matches)>1:ambiguous.append(item["id"])
  if matches:matches[0].append(item)
  else:tiers.append([item])
 tiers.sort(key=lambda tier:(min(box(x)[1] for x in tier),min(str(x["id"]) for x in tier)))
 ordered=[]
 for tier in tiers:
  if source_type==MANGA:tier.sort(key=lambda x:(-box(x)[0],box(x)[1],str(x["id"])))
  else:tier.sort(key=lambda x:(box(x)[1],box(x)[0],str(x["id"])))
  ordered.extend(x["id"] for x in tier)
 return {"order":ordered,"tiers":[[x["id"] for x in tier] for tier in tiers],"ambiguous":ambiguous}
