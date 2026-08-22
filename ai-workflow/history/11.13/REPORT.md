# Checkpoint 11.13 — Post-Human Out-of-Sample Validation

## Human completeness and separation

Human explicitly confirmed the completed queue split: 81/81 processed, comprising 71 VERIFIED transcriptions and 10 intentional UNREADABLE labels; PENDING and SOURCE_UNAVAILABLE are both zero. All ten source hashes remain valid. Ten validation pages are unique and have an empty source-hash intersection with the ten 11.11/11.12 calibration pages.

Leakage checks all PASS: calibration samples excluded, validation pages unseen, source hashes unique/separated, Human GT absent from runtime features, and prediction/confidence/R2 state hidden during annotation. The manifest hash remains `480d02ca3ac77f54bc3bb557d78dea87cc4e6fbe4ecbdbcb0671c11d39b9c635`.

## Frozen R2 result — 71 VERIFIED only

R2 was evaluated unchanged: SAFE iff minimum persisted OCR confidence is at least 0.98, fragment count is one, and crop-boundary warning is false.

- SAFE: 1/71 (1.41% coverage)
- SAFE correct: 0
- FALSE SAFE: 1 (100% of SAFE)
- observed SAFE precision: 0%
- HARD: 21/71 (29.58%)
- STRUCTURAL_REVIEW: 49/71 (69.01%)

The unseen false-safe is page 13 sample `11.13:725a6a01324b:LR_fc624020f5d6`: persisted OCR `\"STAR` versus Human GT `STAR`. It is a single fragment, confidence >= 0.98, has no boundary warning, and therefore satisfies every frozen SAFE condition. Error classification: punctuation plus extra character/text. R2 did not prevent SAFE.

## Intentional UNREADABLE safety analysis

The 10 UNREADABLE labels were not treated as correct or incorrect and were not modified:

- SAFE_CANDIDATE: 2
- HARD: 8
- STRUCTURAL_REVIEW: 0
- UNREADABLE_SAFE_RISK: 2

The two risks are `11.13:774a019f7f27:LR_218e1d60e667` and `11.13:774a019f7f27:LR_691c6e0ae1b4`. They are serious independent warnings but are not counted as false-safe without authoritative text.

## OCR quality and structural analysis

On 71 VERIFIED transcriptions: exact match 8/71 (11.27%), normalized CER 14.85%, WER 38.88%.

There are 49 multi-fragment/structural-signal samples among VERIFIED. Forty-seven are transcription errors, and all 47 were routed to STRUCTURAL_REVIEW; structural false-safe is zero. Structural-error frequency is 47/71 (66.20%). Persisted features identify multi-fragment merge/reconstruction warnings but do not contain an independent split label, so no split count was inferred. Error taxonomy observations include 24 missing-text, 29 wrong-character, 10 extra-text, 7 punctuation, and 4 diacritic classifications; categories may overlap.

## Calibration vs independent validation

- 11.12 calibration: N=50, SAFE=1 (2%), false-safe=0, observed precision=100%.
- 11.13 VERIFIED validation: N=71, SAFE=1 (1.41%), false-safe=1, observed precision=0%.
- Non-independent descriptive only: N=121 transcription samples (excludes 10 UNREADABLE), SAFE=2, false-safe=1. The first 50 selected R2 and are not independent evidence.

## Verdict and next experiment

**C. R2 GENERALIZATION FAIL.** R2 is not production-safe and was not deployed or retuned. The highest-value 11.14 experiment is one frozen-case-driven logical crop/merge/split reconstruction improvement benchmark, covering the observed false-safe and structural-review cases. Do not continue threshold tuning. Reading Order shared tier/row geometry remains deferred and unchanged.

## Resource, preservation and tests

Resource Guard stayed NORMAL. Process RSS was approximately 88.8 MB before and 94.6 MB after; available memory approximately 6.82 GB; swap delta zero. OCR inference calls 0, VLM calls 0, Ollama calls 0. The authoritative production-state hash and frozen manifest are unchanged; Human GT was read only, and production routing was not changed.

Focused tests pass 7/7 and the full backend suite passes 306/306. Python compile, artifact JSON validation, workflow validation and `git diff --check` are part of final handoff validation. No commit or push was performed.
