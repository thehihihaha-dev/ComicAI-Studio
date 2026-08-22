from __future__ import annotations
import hashlib,json,statistics
from typing import Any

REVISION="fragment-logical-geometry.v1"
def _box(r):return [float(x) for x in r["bbox"]]
def _union(rs):
 boxes=[_box(r) for r in rs];return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
def _join(a,b,median_h):
 xover=max(0,min(a[2],b[2])-max(a[0],b[0]));minw=max(1,min(a[2]-a[0],b[2]-b[0]));vgap=max(0,max(a[1],b[1])-min(a[3],b[3]));cx=abs((a[0]+a[2]-b[0]-b[2])/2)
 return vgap<=max(10,median_h*.8) and xover/minw>=.30 and cx<=max(a[2]-a[0],b[2]-b[0])*.65
def aggregate_fragments(regions:list[dict[str,Any]],panel_id:str="PAGE_FALLBACK")->dict[str,Any]:
 if not regions:return {"revision":REVISION,"logical_regions":[],"fragment_count":0,"representation_hash":_hash([],[])}
 detected=[r for r in regions if r.get("region_type")=="detected_text"];logical=[r for r in regions if r.get("region_type")!="detected_text"]
 heights=[_box(r)[3]-_box(r)[1] for r in detected];median_h=statistics.median(heights) if heights else 1;parent={r["region_id"]:r["region_id"] for r in detected}
 def find(x):
  while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
  return x
 def union(a,b):
  ra,rb=find(a),find(b)
  if ra!=rb:parent[max(ra,rb)]=min(ra,rb)
 for i,a in enumerate(detected):
  for b in detected[i+1:]:
   if _join(_box(a),_box(b),median_h):union(a["region_id"],b["region_id"])
 clusters={}
 for r in detected:clusters.setdefault(find(r["region_id"]),[]).append(r)
 items=[]
 for rs in list(clusters.values())+[[r] for r in logical]:
  ids=sorted(r["region_id"] for r in rs);bbox=_union(rs);kind=rs[0].get("region_type","other") if len(rs)==1 and rs[0].get("region_type")!="detected_text" else "logical_text_region"
  stable=hashlib.sha256(json.dumps({"revision":REVISION,"panel":panel_id,"fragments":ids,"bbox":bbox},sort_keys=True,separators=(",",":")).encode()).hexdigest()[:12]
  items.append({"logical_region_id":f"LR_{stable}","source_fragment_ids":ids,"bbox":bbox,"panel_id":panel_id,"region_type":kind,"aggregation_confidence":1.0 if len(rs)==1 and kind!="logical_text_region" else round(.72+.06*min(len(rs),3),2)})
 items.sort(key=lambda r:(r["bbox"][1],-r["bbox"][0],r["logical_region_id"]));source_geometry=sorted(({"fragment_id":r["region_id"],"bbox":_box(r),"region_type":r.get("region_type","other")} for r in regions),key=lambda x:str(x["fragment_id"]));return {"revision":REVISION,"logical_regions":items,"fragment_count":len(regions),"representation_hash":_hash(items,source_geometry)}
def _hash(items,source_geometry):return hashlib.sha256(json.dumps({"revision":REVISION,"regions":items,"source_geometry":source_geometry},sort_keys=True,separators=(",",":")).encode()).hexdigest()
def flatten(panel_order:list[str],region_orders:dict[str,list[str]])->list[str]:return [rid for panel in panel_order for rid in region_orders.get(panel,[])]
