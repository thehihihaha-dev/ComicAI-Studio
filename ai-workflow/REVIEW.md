# Checkpoint 11.17 Independent Re-review

## Verdict

**PASS**

## Independent evidence

- The current database inventory contains exactly the 40 Gate D asset identities,
  and independent hashing confirmed all 40 current source files match their
  historical Gate D source hashes. The runner now enforces this equality before
  inference, preventing current bytes from being processed under stale identity.
- The corrected cold replay used the frozen 11.10 EasyOCR 1.7.2 CPU config and
  frozen region geometry sequentially on all 40 pages: 858 regions, 858 recorded
  OCR calls, 40 cache misses, 13.3348 s, and no reused OCR observations. This is
  a genuine repeat of the approved engine/config, not OCR tuning or a new model
  experiment. It materially improves rather than regresses the historical
  62.4856 s Gate D incremental measurement.
- Immediate replay exercised `OfflineReaderCache.get_or_build` for the same 40
  fingerprints. It produced 40 hits, zero misses, zero additional OCR calls,
  identical output hashes, and 68.5 us measured wall time. The miss builder is
  deliberately fail-fast during replay, so an unexpected miss could not be
  silently counted as a hit.
- Cache fingerprints include actual source hash, source type, region IDs and
  geometry, geometry version, OCR engine/version/config, contract version, and
  frozen Reading Order algorithm/version/threshold. Focused tests independently
  cover invalidation for source, source type, geometry, OCR config, geometry
  version, and order version, as well as deterministic output and hit-path call
  avoidance. Human GT is absent from the fingerprint.
- The scale artifact retains 40 complete structured outputs containing all 858
  regions. Independent checks recomputed every stored page output hash and
  confirmed the page/cache fingerprints and hashes agree. Every region has the
  required schema, provenance, source/crop/engine/config/version identity,
  explicit reliability state, `requires_repair = true`, `authoritative = false`,
  and `human_gt_involved = false`.
- Scale reliability is consistently reported from emitted outputs as 763
  OBSERVED, 59 HARD, and 36 UNREADABLE_OR_UNKNOWN; 858/858 require repair. High
  confidence cannot promote authority. No production code imports the offline
  contract or cache.
- Correctness remains restricted to Human GT subsets. Reading Order exactly
  reproduces 11.16: 7/10 pages, 43/50 positions, 120/124 pairs, four inversions.
  OCR descriptive metrics remain 8/71 exact, CER 14.85%, and WER 38.88%.
- Validation safety mapping consumes only prediction-side structural features;
  Human state is attached afterward for evaluation. All 71 VERIFIED samples and
  all 10 UNREADABLE samples have auditable replay rows, remain non-authoritative,
  and require repair. The `\"STAR` false-safe and both R2 unreadable-safe-risk
  cases are blocked. Unsafe authoritative promotions and authoritative unreadable
  promotions are both zero.
- R2, 11.14 adaptive padding, and 11.15 PP-OCR are explicitly absent from the
  integrated path. VLM and Ollama calls are zero. The frozen manga rule remains
  normalized vertical overlap `>= 0.50`, top-to-bottom tiers/right-to-left peers,
  explicitly `BENCHMARK_FITTED`; webtoon uses a separate unbenchmarked policy.
- Resource measurements are coherent: Resource Guard NORMAL, peak RSS about
  1.21 GB, approximately 6.55 GB available after replay, and zero swap delta.
- All five historical input hashes recorded by the manifest still match. No
  Human GT, authoritative persisted data, historical artifact, production Reader,
  production OCR, or Story behavior was changed. No commit or push was made.

## Validation rerun

- Focused final-contract plus fast-pass tests: 15/15 PASS.
- Canonical backend unittest discovery: 327/327 PASS.
- Python compilation: PASS.
- Six 11.17 JSON artifacts and cross-artifact invariants: PASS.
- Workflow validation and `git diff --check`: PASS.

The evidence supports final verdict **B. READER V2 FOUNDATION PASS WITH KNOWN
OCR LIMITATION**. Day 11 may close after Human approval, carrying forward:
**HARD/STRUCTURAL OCR repair remains an open Reader V2 module.** No Day 12 work
is authorized by this review.
