# Checkpoint 11.17 — Final Reader V2 Offline Integration

## Result

The offline-only final Reader V2 contract is implemented without changing production Reader, OCR, Story, Human GT, or persisted benchmark state. It separates observed OCR from authoritative text, preserves source/crop/engine/config/algorithm provenance, exposes conservative reliability states and marks every Day 11 OCR region `requires_repair = true`. R2, the 11.14 structural candidate, and PP-OCRv6 are not integrated.

The frozen manga Reading Order rule remains normalized vertical overlap `>= 0.50`, top-to-bottom tiers and right-to-left peers, explicitly `BENCHMARK_FITTED`. Webtoon is a separate, unbenchmarked source policy.

## Scale and cache

The genuine Gate D input remains 40 unique real manga pages and 858 regions. The corrected 11.17 integration pass ran 858 sequential EasyOCR region calls with the frozen engine/config and frozen Gate D geometry through the final contract in 13.33 s, producing 40 new-contract cache misses. Source bytes are required to match every historical Gate D source hash before inference. This is a genuine replay, not a new OCR experiment or tuning exercise, and does not materially regress the measured 62.49 s Gate D incremental baseline.

Immediate exact replay through the same cache API produced 40/40 hits in 0.0000685 s, made zero additional OCR calls, retained identical source/config fingerprints and identical structured output hashes. Fingerprints include source hash/type, region geometry and geometry version, OCR engine/config, and Reading Order algorithm/config; Human GT is excluded. The scale artifact retains all 858 structured outputs for audit.

## Correctness and safety

Correctness is reported only on existing Human GT subsets, never on all 40 scale pages.

- Reading Order: 7/10 exact pages, 43/50 exact positions, 120/124 correct pairs, four inversions. This reproduces 11.16 exactly with no integration regression.
- OCR VERIFIED set: 8/71 exact (11.27%), CER 14.85%, WER 38.88%.
- VERIFIED reliability: 22 HARD and 49 STRUCTURAL_REVIEW; 71/71 require repair.
- Scale reliability: 763 OBSERVED, 59 HARD and 36 UNREADABLE_OR_UNKNOWN; 858/858 require repair.
- Unsafe OCR promoted authoritative: zero.
- Known `"STAR` false-safe: blocked.
- Ten Human UNREADABLE samples remain untranscribed; both known R2 UNREADABLE-safe-risk samples are blocked; authoritative unreadable promotions: zero.
- Human GT involvement in normal Reader output: false.
- VLM/Ollama calls: 0/0.

Resource Guard remained NORMAL. Peak RSS was 1.21 GB, available memory after replay approximately 6.55 GB and swap delta zero.

## Verification

Focused tests: 16 passed. Full backend suite: 332 passed plus 11 subtests. Python compile, JSON artifact validation, workflow validation and `git diff --check` are part of the final gate. Historical input hashes were checked after artifact generation. No commit or push was performed.

## Verdict

**B. READER V2 FOUNDATION PASS WITH KNOWN OCR LIMITATION.** Day 11 should close after independent Reviewer PASS. This does not claim OCR correctness is solved.

Carry forward: **HARD/STRUCTURAL OCR repair remains an open Reader V2 module.**

Proposed Day 12 focus only: Reader V2 → Repair Boundary → Page Understanding → Scene/Chunk construction → Carry-over state → grounded Story events.
