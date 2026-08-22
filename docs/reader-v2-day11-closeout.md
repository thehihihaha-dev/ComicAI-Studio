# Reader V2 Day 11 closeout

## Final boundary

The offline Reader V2 contract emits ordered logical regions with raw OCR observations, conservative reliability states, `requires_repair`, provenance, and explicit non-authoritative state. Human Ground Truth is evaluation-only and is never included in predictions or cache fingerprints.

For manga only, the frozen Reading Order experiment uses top-to-bottom tiers, right-to-left peers, and normalized vertical overlap `>= 0.50`. The threshold is **BENCHMARK_FITTED**, not production-calibrated. Webtoon remains a separate source policy.

OCR states are `OBSERVED`, `HARD`, `STRUCTURAL_REVIEW`, and `UNREADABLE_OR_UNKNOWN`. Every Day 11 OCR observation remains `authoritative = false` and `requires_repair = true`; high confidence cannot bypass that boundary. R2, the 11.14 padding candidate, and the 11.15 PP-OCR candidate are not integrated.

## Evidence

- Scale input: 40 unique Gate D pages and 858 frozen EasyOCR observations.
- Integration pass: 40 new-contract cache misses, 858 sequential EasyOCR region calls, 13.33 s. This genuine replay uses the frozen Gate D engine/config and region geometry; it introduces no OCR experiment or tuning and does not materially regress the 62.49 s Gate D incremental baseline.
- Exact replay through the same cache API: 40/40 cache hits, 68.5 μs, identical output hashes, zero additional OCR inference.
- Reading Order Human subset: 7/10 exact pages, 43/50 positions, 120/124 pairs, four inversions—an exact reproduction of 11.16.
- OCR Human subset: 8/71 exact, 14.85% CER, 38.88% WER; zero unsafe authoritative promotions.
- Scale reliability: 763 OBSERVED, 59 HARD, 36 UNREADABLE_OR_UNKNOWN; 858/858 require repair.
- Known R2 failures: the `"STAR` false-safe and both UNREADABLE-safe-risk samples are blocked from authoritative state.
- Machine: Resource Guard NORMAL, peak RSS 1.21 GB, approximately 6.55 GB available after replay, swap delta zero.
- VLM/Ollama calls: zero.

## Verdict and handoff

**B. READER V2 FOUNDATION PASS WITH KNOWN OCR LIMITATION.** Day 11 can close because the offline boundary is deterministic, cacheable, provenance-preserving, source-aware, and false-safe by construction. OCR correctness is not solved.

Carry forward: **HARD/STRUCTURAL OCR repair remains an open Reader V2 module.**

Proposed Day 12 focus, without implementation: Reader V2 → Repair Boundary → Page Understanding → Scene/Chunk construction → Carry-over state → grounded Story events. Unsafe observed OCR must not enter authoritative Story facts.

## Solved / acceptable foundation

- Scalable offline processing on 40 real manga pages and 858 regions.
- Exact-input cache and deterministic replay with output-hash equality.
- Source, crop, OCR engine/config and algorithm provenance.
- Explicit reliability and repair-required states instead of fabricated success.
- A failure-safe Reader contract that never promotes Day 11 OCR automatically.
- Improved manga Reading Order geometry, retained as benchmark-fitted evidence.
- Resource Guard NORMAL with controlled RSS and zero swap delta.

## Not solved

- Trusted OCR and a validated OCR repair layer.
- Production-calibrated Reading Order, including non-manga policies.
- Semantic page understanding and supported speaker/text-role relationships.
- Scene/chunk construction and evidence-grounded cross-page carry-over.
- Safe integration from Reader evidence into Story facts.

## Architectural lesson

**OCR confidence is not correctness.** Reader output must preserve the distinction between an **observation** and an **authoritative fact**. Raw OCR remains immutable evidence; a future repair/validation boundary may produce validated text or an unresolved marker, but must never overwrite the observation. Downstream Story components must consume grounded, qualified evidence rather than treating raw OCR as fact.
