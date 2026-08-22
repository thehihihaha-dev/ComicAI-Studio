# Checkpoint 11.8 Report — Reader V2 Fast Pass Prototype

## A. Existing Reader architecture inspected
Production `ocr_service.py` runs EasyOCR on whole pages; persisted `vision_regions` reference OCR block IDs and existing reading order may come from Vision/VLM. The three-page benchmark has logical regions but no trustworthy panel hierarchy.

## B. Reader V2 Fast Pass architecture
Added an isolated `ReaderV2FastPass`: source image/hash + compatible logical regions/panels -> bounded crops -> injected local OCR adapter -> deterministic geometry order -> quality signals/routing -> structured result. It is not wired into production.

## C. Logical crop implementation
Promoted the 11.7 algorithm as reusable `logical_crop_box()`: default 2% of maximum bbox dimension, maximum allowed 10%, clipped to image bounds, stable native integer output and original bbox preservation.

## D. OCR engine/config
Benchmark adapter: EasyOCR, Vietnamese+English, CPU, `detail=1`, version/config recorded. One reader instance processed 20 regions sequentially. No correction/recovery model.

## E. Structured output contract
Each page records reader/source/fingerprint, regions with bbox/type/crop dimensions, OCR engine/version/config/text/confidence/raw lines, quality signals, ambiguity reasons and routing state, plus reading order and timings/counts.

## F. Reading-order policy
Policy enum supports `MANGA_RTL`, `WEBTOON_VERTICAL` and `WESTERN_LTR`; only MANGA_RTL is validated here. It orders tiers top-to-bottom and peers right-to-left.

## G. Geometry algorithm
Ordering is hierarchical panel/group then region, using bbox containment, tier clustering, overlap/cross-panel checks and stable IDs. With no panel metadata, the benchmark explicitly uses one page fallback group; no detector is claimed or added.

## H. Ambiguity behavior
Regions crossing overlapping panels, contained by multiple panels or orphaned when panels exist receive explicit ambiguity reasons and `AMBIGUOUS`; they are still deterministically positioned for reproducibility, not semantic certainty.

## I. Confidence/quality signals
Signals include confidence (explicitly not truth), empty output, suspiciously short output and unusual-symbol ratio. Confidence is never an acceptance threshold. `ACCEPT_CANDIDATE` only means no implemented escalation signal fired.

## J. Cache/fingerprint contract
SHA-256 fingerprint covers source hash, reader/crop/order revisions, 2% padding, OCR engine/version/config, policy, stable region identity/geometry/type and supplied panel identity/geometry. No persistence/distributed cache was added.

## K. Human GT dataset
Exactly the frozen 20 VERIFIED samples from one project/three pages were used. GT and image/crop identity hashes were revalidated; authoritative database snapshot matched before/after.

## L. OCR exact/CER/WER
Normalized exact 4/20; micro raw CER 0.22714; mean normalized CER 0.11038; mean WER 0.40558; missing 0. Edits: 6 insertions, 14 deletions, 134 substitutions.

## M. False ACCEPT analysis
Routing produced 19 `ACCEPT_CANDIDATE`, 1 `HARD`, 0 `AMBIGUOUS` on panel-less benchmark inputs. Of 19 accepts, 16 were wrong: false ACCEPT rate 84.21%. This proves the current cheap signals are not a safe trust router; no threshold was fitted or promoted.

## N. Reading-order test results
Tests cover A→C→B manga panels, same-tier right-before-left bubbles, uneven layouts, overlapping/cross-panel ambiguity, partial-boundary/orphan handling, page fallback, panel-sensitive fingerprints and structured end-to-end zero-model behavior. All 9 Reader V2 focused tests pass.

## O. Latency
EasyOCR initialization 2.36020 s; 20-region benchmark wall 0.92342 s. Aggregated page work: crop 0.00081 s, OCR 0.84985 s, reading order 0.00028 s, service wall 0.85777 s.

## P. Memory/RSS
Process RSS 79,265,792→1,124,515,840 bytes; peak observed RSS 1,124,515,840. Available memory 7,787,986,944→7,005,716,480 bytes.

## Q. Swap
Swap before/after 1,540,232,314 bytes; delta 0.

## R. Safety state
Resource Guard was NORMAL before and after, checked between pages; concurrency was one. No GPU-memory or temperature claim.

## S. Model-call count
VLM calls 0; Ollama calls 0. No model download or resident Ollama requirement.

## T. Regression analysis
Fast Pass exactly reproduced 11.7 Mode B aggregate metrics and all per-sample CER values: 0/20 regressions. Production OCR behavior was not changed.

## U. Tests
Focused Reader/OCR/geometry/resource set: 32/32 pass. Full backend: 267/267 pass in 2.221 s. Python compile, four-artifact JSON validation and `git diff --check` pass. Post-review fingerprint artifacts were refreshed purely from saved inputs; OCR was not rerun.

## V. Files changed
Added `backend/app/services/reader_v2_fast_pass.py`, `backend/tests/test_reader_v2_fast_pass.py`, `scripts/reader_v2_fast_pass_benchmark.py`, four 11.8 artifacts and active workflow documents.

## W. Production isolation
No router, asset processor, production OCR, DB schema or persisted output path imports/calls the prototype. Benchmark execution was read-only and additive.

## X. Limitations
N=20 from three pages; no real panel annotations/detection validation; page fallback cannot prove manga panel order. OCR remains wrong on 16/20 and quality signals have dangerously high false acceptance. WEBTOON/WESTERN policies are interface placeholders, not validated behavior.

## Y. Human testing requirement
The next meaningful validation requires a human to inspect real manga page reading order and/or supply panel/group truth on more pages. Do not infer that judgment from current persisted order or simulate it with AI.

## Z. Recommendation for 11.9
Do not promote Fast Pass routing to production. If human-approved, 11.9 should collect/verify page-level panel and region reading-order GT plus broader OCR GT, then evaluate ambiguity/false-accept rules independently. Do not tune trust thresholds on these same 20 samples.
