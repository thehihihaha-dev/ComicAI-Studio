# Checkpoint 11.10 Report — Gates A–C Controlled Scale

## A. Dataset inventory
Twenty-one unique real source pages exist. Gate C used pages 1–20: three pages/22 persisted logical regions and seventeen pages with isolated transient EasyOCR line-region detection. Page 21 stayed outside the gate. No duplication or synthesis.

## B. Gate progression
Gates A (5), B (10) and C (20) completed safely with exact cached repeats. Gate D targets approximately 40 pages; only 21 exist, so 19 additional pages are required and Gate D was not run.

## C. Cache behavior
Gate C incremental reused all ten Gate B pages and processed ten new pages: 10 hits/10 misses. Exact repeat: 20 hits/0 misses/0 OCR calls. Prior Gate A/B cold/cached evidence remains in summary.

## D. 5-page performance
Cold 8.0998 s/62 regions/64 OCR calls; cached 0.0303 s/0 OCR calls. NORMAL, swap delta 0.

## E. 10-page performance
Incremental 13.9611 s/159 regions/102 OCR calls/5 hits; cached 0.0603 s/10 hits/0 OCR. NORMAL; no swap growth.

## F. 20-page performance
Incremental: 386 regions, 44.7077 s, 2.2354 s/page, 0.447 pages/s, 8.634 regions/s, 10 hits/10 misses, 237 OCR calls, 5.9351 s measured new region-crop OCR subtotal, peak RSS 6.607 GB, available memory after 5.094 GB, swap delta 0, NORMAL. Cached: 0.1486 s, 20 hits, 0 OCR calls, peak RSS 96.2 MB, swap delta 0, NORMAL.

## G. 40-page performance
Not run; 21/40 real pages available.

## H. OCR workload
Gate C incremental performed 10 new transient detections plus 227 new line-region recognitions = 237 calls. Existing 159 regions were reused. All OCR remains predicted and non-authoritative.

## I. Reading-order diagnostics
All pages record provenance, region/panel counts, PAGE fallback, sequence, orphan/ambiguity/overlap and fallback status. Panel count is zero and transient line geometry is not claimed to be logical bubbles or correct ordering.

## J. 11.9 regression result
No geometry change: frozen 2/3 exact, 76/79 pairwise, 3/3 fallback groups and three Page 3 inversions remain unchanged. Human GT is immutable.

## K. Ambiguity distribution
Explicit geometry ambiguity 0/20. This is uncalibrated and not accuracy evidence because verified panel hierarchy is absent.

## L. Human-review candidate count
Twelve Gate C pages contain non-ACCEPT regions. Low-confidence selection expands the review artifact to 20 unique pages, with known-regression/easy categories merged. This is predicted difficulty metadata, not GT.

## M. Memory
Incremental Gate C RSS 93.8 MB→6.320 GB; peak 6.607 GB; available memory 8.411→5.094 GB. Cached peak 96.2 MB.

## N. Swap
Gate C incremental/cached swap delta 0.

## O. Resource Guard
NORMAL before/after and between pages. No CRITICAL, crash or unsafe swap growth; concurrency one.

## P. VLM/Ollama call count
VLM 0; Ollama 0. No correction, recovery, Story or Script calls.

## Q. Source integrity
21 eligible sources have distinct SHA-256 hashes. Gate C used exactly 20 unchanged sources.

## R. Authoritative-state integrity
Snapshot hashes matched before/after incremental and cached Gate C. No production OCR/Vision/Dialogue/Story/Review/GT write.

## S. Tests
Full backend passes 276/276. Focused cache/Fast Pass/GT tests, Python compile, Gate A–C/summary/review JSON validation, workflow validation and `git diff --check` pass.

## T. Files changed
Added Gate C artifact and refreshed dynamic multi-gate summary/review sample; production Reader remains unchanged.

## U. Limitations
Seventeen pages use line boxes, only three have Reading Order GT, panel/ambiguity detection is not validated, and full detection time is contained in wall time rather than the region-OCR subtotal. Cold RSS remains substantial. Execution scale is not correctness.

## V. Final verdict
**F. HUMAN INPUT REQUIRED.** Gates A–C are execution/cache safe; Gate D needs 19 additional unique pages.

## W. Recommendation for 11.11
Do not begin 11.11. Upload 19 additional unique real manga pages to reach 40, then resume Gate D from the exact 20-page cache. OCR `ACCEPT_CANDIDATE` remains untrusted (16/19 false accepts in 11.8).
