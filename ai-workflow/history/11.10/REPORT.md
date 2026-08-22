# Checkpoint 11.10 Report — Controlled Reader V2 Scale

## A. Dataset and Gate D rebaseline
The user explicitly requested Gate D be redone after re-uploading the pages. Preflight found 40/40 unique real source hashes and stable authoritative snapshots. The current set preserves all three 11.9 Human GT sources but contains 19/20 Gate C sources; one source was replaced. Gate C artifacts remain immutable. Gate D therefore reused 19 exact cache entries and processed 21 unmatched current sources without claiming source equivalence.

## B. Gate progression
Gates A/B/C/D completed at 5/10/20/40 pages, each followed by an exact cached repeat. No synthetic or duplicated page was used.

## C. Cache behavior
Gate D incremental: 19 hits/21 misses. Exact repeat: 40 hits/0 misses/0 OCR calls. Cache identity includes source hash, region geometry, crop policy, OCR engine/version/config, Reader version and reading-order policy.

## D. 5-page performance
Cold 8.0998 s/62 regions/64 OCR calls; cached 0.0303 s/0 OCR calls. NORMAL, swap delta 0.

## E. 10-page performance
Incremental 13.9611 s/159 regions/102 OCR calls/5 hits; cached 0.0603 s/10 hits/0 OCR. NORMAL; no swap growth.

## F. 20-page performance
Incremental 44.7077 s/386 regions/237 OCR calls/10 hits; cached 0.1486 s/20 hits/0 OCR. NORMAL, swap delta 0.

## G. 40-page performance
Incremental rebaseline: 858 regions, 62.4856 s, 1.5621 s/page, 0.6401 pages/s, 13.7312 regions/s, 528 OCR calls, 10.4459 s measured new region-crop OCR subtotal, peak RSS 6.626 GB, available memory after 5.167 GB, swap delta 0, NORMAL. Cached: 0.2506 s, 159.617 pages/s, 40 hits, 0 OCR calls, peak RSS 102.3 MB, swap delta 0, NORMAL.

## H. OCR workload
The 21 misses used isolated transient EasyOCR detection plus region recognition. All OCR is predicted and non-authoritative; `ACCEPT_CANDIDATE` remains untrusted because 11.8 recorded 16/19 false accepts.

## I. Reading-order diagnostics
All 40 pages record provenance, region count, predicted sequence, group assignment, orphan/ambiguity/overlap flags and fallback status. Transient line geometry is not claimed to be logical bubbles or correct panel hierarchy.

## J. 11.9 regression result
Frozen result remains 2/3 exact pages, 76/79 pairwise, 3/3 group accuracy, and three Page 3 inversions. All three Human GT sources remain present and no Human GT was created or modified.

## K. Ambiguity and review sample
Explicit geometry ambiguity is 0/40, but this is uncalibrated and not correctness evidence. Twenty-eight pages contain non-ACCEPT regions. The generated review sample is predicted-difficulty metadata only, not Human GT.

## L. Resource and safety
Gate D remained NORMAL before, between and after pages. Incremental process RSS rose from 96.0 MB to 6.621 GB (peak 6.626 GB); available memory ended at 5.167 GB. Swap delta was zero. Concurrency was one and no CRITICAL guard state occurred.

## M. Model calls and production integrity
VLM calls 0; Ollama calls 0. No correction, recovery, Story or Script call occurred. Authoritative snapshot hashes matched before/after both Gate D runs; there was no production OCR/Vision/Dialogue/Story/Review/GT write.

## N. Tests and validation
Full backend suite passes 276/276. The Gate D cold and cached artifacts report 40 pages/858 regions, 19/21 then 40/0 cache split, zero cached OCR, NORMAL safety, zero swap delta and unchanged authoritative state. Python/JSON/workflow/diff checks are performed before handoff.

## O. Limitations
Only three pages have Reading Order Human GT. Most pages use transient OCR line boxes without verified panels. The OCR inference subtotal excludes detector overhead, which remains included in wall time. Peak cold RSS is substantial. Execution scale safety does not establish reading-order or OCR correctness.

## P. Final verdict
**B. SCALE SAFE — CORRECTNESS VALIDATION STILL REQUIRED.** All four controlled gates executed safely and cache determinism passed. Accuracy cannot be promoted beyond the existing three-page Human GT evidence.

## Q. Recommendation
Stop at Checkpoint 11.10 human approval. Do not begin 11.11 automatically. A future correctness checkpoint should collect reproducible Human GT for the prepared review sample before any production routing promotion.
