# Checkpoint 11.10 Report — Controlled Reader V2 Scale Benchmark

## A. Dataset inventory
Six unique real source pages now exist in the target project. Gate A used pages 1–5. Pages 1–3 reused persisted logical regions (22 total); pages 4–5 had no persisted geometry and used isolated EasyOCR transient detection, producing 40 line-level regions. Page 6 was not needed for Gate A. No page was duplicated or synthesized.

## B. Gate progression
Gate A (5 pages) completed cold and cached with safe results. Gate B requires 10 pages but only 6 exist, so Gates B/C/D were not run. Four additional unique real pages are required.

## C. Cache behavior
Exact identity includes source hash, geometry, crop/Reader/order revisions, OCR version/config and policy. Cold: 0 hits/5 misses/64 OCR calls. Cached: 5 hits/0 misses/0 OCR calls. Cached wall time was 0.0303 s versus 8.0998 s cold.

## D. 5-page performance
Cold: 5 pages, 62 regions, 8.0998 s, 1.6200 s/page, 0.617 pages/s, 7.654 regions/s, 1.4536 s region-OCR time. Cached: 0.0303 s, 0.00605 s/page. These are observed CPU/macOS measurements, not targets.

## E. 10-page performance
Not run: only 6 unique real pages exist; Gate B needs 4 more.

## F. 20-page performance
Not reached.

## G. 40-page performance
Not reached.

## H. OCR workload
Cold used 64 EasyOCR calls: 2 full-page transient detections and 62 logical/line-region crop recognitions. Cached used 0. OCR output remains predicted/non-authoritative; no GT or production OCR field was written.

## I. Reading-order diagnostics
Every page records panel count, region count, predicted sequence, fallback PAGE group, orphan/ambiguity/overlap signals and geometry provenance. Panel count is zero and fallback is explicit because no panel detector was introduced. Transient line detections are not claimed as logical bubbles or correct order.

## J. 11.9 regression result
No geometry code change was introduced. Frozen 11.9 evidence remains 2/3 exact pages, 76/79 pairwise, 3/3 fallback group structures and three Page 3 inversions. GT and Page 3 remain immutable.

## K. Ambiguity distribution
Explicit geometry ambiguity flags: 0/5 pages. This does not imply correctness because page fallback lacks verified panels and transient pages are unverified.

## L. Human-review candidate count
Two Gate A pages contain non-ACCEPT regions and transient line-level geometry. Low-confidence OCR signals also select all five Gate A pages; Page 3 additionally carries the known-regression category and Page 1 the deterministic-easy category. Categories are merged per page, so the review sample contains 5 unique pages. The artifact is selection metadata only; no human GT was created.

## M. Memory
Cold RSS 91,537,408→6,730,973,184 bytes; peak 6,730,973,184; available memory after 5,637,898,240. Cached peak RSS 92,930,048; available memory after 10,453,663,744.

## N. Swap
Cold swap delta 0; cached swap delta 0.

## O. Resource Guard
NORMAL before/after both runs and between cold pages. No CRITICAL state, crash, source mutation or unsafe swap growth occurred. Concurrency was one.

## P. VLM/Ollama call count
VLM 0; Ollama 0. No dialogue correction, recovery, Story or Script generation.

## Q. Source integrity
All six eligible sources exist and have distinct SHA-256 hashes. Exact identities are stored in cache/results. Three older unrelated asset records remain ineligible because their files are missing.

## R. Authoritative-state integrity
Project snapshot hashes matched before/after cold and cached runs. No OCR/Vision/Dialogue/Story/Review/GT field was overwritten.

## S. Tests
Focused Fast Pass/cache/GT tests initially pass 18/18. Full backend passes 276/276 in 2.461 s. Python compilation, three-artifact JSON validation, workflow validation and `git diff --check` pass. Tests make no real VLM/Ollama calls.

## T. Files changed
Added the isolated staged scale/cache runner, focused cache tests and Gate A/cache/summary/review-sample artifacts; updated active workflow documents. Production Reader code is unchanged.

## U. Limitations
Only Gate A ran. Two pages use EasyOCR line boxes rather than validated logical bubbles; none of the new pages has reading-order GT. Zero ambiguity flags are not calibrated. Cold RSS is substantial despite NORMAL guard state. Execution scalability and correctness remain separate.

## V. Final verdict
**F. HUMAN INPUT REQUIRED.** Gate A is execution/cache safe, but evidence cannot progress to Gate B without four additional real pages.

## W. Recommendation for 11.11
Do not begin 11.11. Upload four additional unique real manga pages to reach ten, then resume 11.10 Gate B using the exact cache. Preserve OCR distrust: 11.8 false ACCEPT remains 16/19.
