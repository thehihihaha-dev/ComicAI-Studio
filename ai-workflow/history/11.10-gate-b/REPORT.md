# Checkpoint 11.10 Report — Gates A–B Controlled Scale

## A. Dataset inventory
Ten unique real source pages exist. Pages 1–3 use 22 persisted logical regions; pages 4–10 use isolated transient EasyOCR line-region detection because production Vision remains pending. Gate B contains 159 regions total. Nothing was duplicated or synthesized.

## B. Gate progression
Gate A and Gate B completed safely. Gate C requires 20 pages; only 10 exist, so Gates C/D were not run. Ten additional unique real pages are required.

## C. Cache behavior
Gate A cold/cached: 0/5 then 5/5 hits; cached OCR calls 0. Gate B incremental: first five pages hit cache and five new pages missed; exact repeat produced 10/10 hits, 0 misses and 0 OCR calls. Identity includes source, geometry, OCR/config, Reader/crop/order revisions and policy.

## D. 5-page performance
Cold: 62 regions, 8.0998 s, 1.6200 s/page, 64 OCR calls, peak RSS 6.731 GB, swap delta 0, NORMAL. Cached: 0.0303 s, 5 hits, 0 OCR calls, NORMAL.

## E. 10-page performance
Incremental: 159 regions, 13.9611 s, 1.3961 s/page, 0.716 pages/s, 11.389 regions/s, 5 hits/5 misses, 102 OCR calls, 1.5303 s measured region-crop OCR time, peak RSS 6.613 GB, available memory after 5.153 GB, swap delta −8 MiB, NORMAL. Cached: 0.0603 s, 10 hits, 0 OCR calls, peak RSS 94.1 MB, swap delta 0, NORMAL.

## F. 20-page performance
Not run: Gate C needs ten additional pages.

## G. 40-page performance
Not reached.

## H. OCR workload
Gate B incremental performed 5 full-page transient detections plus 97 new region recognitions = 102 EasyOCR calls. The 62 Gate A regions were reused. Cached Gate B performed zero OCR. OCR remains predicted/non-authoritative.

## I. Reading-order diagnostics
Every page records source/geometry provenance, panel/region counts, PAGE fallback groups, predicted sequence, orphans, ambiguity and overlap. Panel count remains zero; no panel detector/VLM was added. Line regions on pending pages are explicitly transient and unverified.

## J. 11.9 regression result
No geometry change. Frozen result remains 2/3 exact, 76/79 pairwise, 3/3 fallback groups and three Page 3 inversions; Human GT and Page 3 are unchanged.

## K. Ambiguity distribution
Explicit geometry ambiguity is 0/10, but is not a correctness claim because panel hierarchy is unavailable and seven pages use transient geometry.

## L. Human-review candidate count
Five Gate B pages contain non-ACCEPT regions. The selection artifact contains ten unique pages after category merging because low OCR confidence occurs across the gate; Page 3 is tagged known regression and Page 1 deterministic easy sample. No GT was created.

## M. Memory
Incremental Gate B RSS 92.8 MB→6.540 GB; peak 6.613 GB; available memory 7.240→5.153 GB. Cached peak RSS 94.1 MB. Gate A measurements remain preserved in summary.

## N. Swap
Gate B incremental swap decreased 8 MiB; cached delta 0. No unsafe growth.

## O. Resource Guard
NORMAL before/after and between pages for reached gates. No CRITICAL state, crash or source mutation. Concurrency one.

## P. VLM/Ollama call count
VLM 0; Ollama 0. No dialogue correction/recovery, Story or Script call.

## Q. Source integrity
All ten sources exist with distinct SHA-256 hashes. Exact input identities are cached. No source changed during either run.

## R. Authoritative-state integrity
Snapshot hashes matched before/after incremental and cached Gate B. Production OCR/Vision/Dialogue/Story/Review/GT fields were not written.

## S. Tests
Focused Fast Pass/cache/GT tests pass. Full backend passes 276/276. Python compilation, Gate A/B/summary/review JSON validation, workflow validation and `git diff --check` pass. Unit tests make no model calls.

## T. Files changed
Extended the staged scale runner summary to retain multiple completed gates and select the next gate dynamically; added Gate B artifact and refreshed summary/review sample. Production Reader is unchanged.

## U. Limitations
Gate B has no new Human GT, seven pages use line boxes rather than validated logical bubbles, ambiguity is uncalibrated, and full detection latency is included in wall time but not the reported region-crop OCR subtotal. Cold RSS is substantial despite NORMAL safety. Scale execution is not accuracy.

## V. Final verdict
**F. HUMAN INPUT REQUIRED.** Gates A/B are execution/cache safe, but Gate C cannot begin without ten more pages.

## W. Recommendation for 11.11
Do not start 11.11. Upload ten additional unique real manga pages to reach 20, then resume Gate C from the exact ten-page cache. Keep OCR `ACCEPT_CANDIDATE` untrusted (11.8 false accepts 16/19).
