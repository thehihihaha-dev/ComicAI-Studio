# Checkpoint 11.12 — OCR Acceptance Router Redesign

## A. Dataset
Frozen 11.11 set: 50 Human VERIFIED logical-region transcriptions across 10 pages. Each experimental row preserves sample/source identity, bbox, source fragments, persisted OCR output/confidence/crop and quality metadata, and Human GT. GT labels correctness only and is never a runtime feature.

## B. Baseline ACCEPT behavior
Historical behavior reproduces exactly: SAFE/ACCEPT 44/50 (88% coverage), correct 8, false-safe 36, precision 18.18%, false-safe rate 81.82%; HARD 6/50 (12%), including two correct OCR results.

## C. 36 false-safe audit
All 36 cases are recorded with pre-GT deterministic features. Runtime signals include min/mean/spread confidence, length, symbols/digits/repeats/whitespace, crop geometry/density/boundary, fragment count/reconstruction mode, type and aggregation/geometry stability.

## D. Error taxonomy
Overlapping supported labels: merged/split reconstruction 24, wrong character 17, missing character/text 13, extra character/text 6, diacritic 5, short-text ambiguity 4, symbol contamination 2 and punctuation 1. Eight errors are plausible single-block text not caught by an obvious structural warning.

## E–F. Confidence and high-confidence wrong cases
Confidence alone R1 at min confidence 0.98 leaves 2 SAFE, both correct. No wrong sample has minimum fragment confidence ≥0.95 in this set; this descriptive result must not be generalized. The 11.8 historical set would have zero SAFE at 0.98. Confidence is useful only as a conservative filter, not sufficient production evidence.

## G. Merge/split analysis
Thirty-two of 50 logical samples are multi-fragment. R2–R4 send all 32 to STRUCTURAL_REVIEW: caught 32, missed 0, false-safe structural cases 0. Among baseline false-safes, 24 carry the merge/split warning.

## H. Short-text analysis
1–3 chars: 5 samples/1 wrong; 4–8: 6/4 wrong; 9+: 39/35 wrong. Short text is risky, but long reconstructed text dominates the current error volume.

## I–M. Candidate signals and routers
R1: min confidence ≥0.98 only; comparator, not eligible as the proposed multi-signal contract. Result 2 SAFE/0 false-safe.

R2: R1 plus single-fragment and no crop-boundary warning. Result 1 SAFE (2%), 1 correct, 0 false-safe, precision 100%; 17 HARD (34%), 32 STRUCTURAL_REVIEW (64%), nine correct OCR results escalated.

R3: R2 plus ≥4 chars and sane symbol/repeat/whitespace distribution. SAFE 0; HARD 18; structural 32.

R4: R3 with confidence ≥0.995, low confidence spread, stable geometry and conservative density. SAFE 0; HARD 18; structural 32.

## N–R. Coverage, precision and routing-state tradeoff
Baseline 88% SAFE/18.18% precision/81.82% false-safe is unsafe. R1 has 4% coverage/100% observed precision but only one signal. R2 has 2%/100% observed precision/zero false-safe; HARD+STRUCTURAL rate is 98%. R3/R4 have zero coverage. Correctness wins, and none is deployable.

## S–T. Stability
Leave-one-out and leave-one-page-out still select R2 among eligible multi-signal rules, but R2 coverage ranges from 0% to 2.04%: removing its sole SAFE sample or page eliminates SAFE coverage entirely. False-safe remains zero. R3 threshold sensitivity from 0.97–0.995 remains zero SAFE. Evidence is page-dependent and BENCHMARK-FITTED.

## U–W. Runtime, resources and model calls
R2 routes 50 rows in approximately 4.8 µs total (~97 ns/region in the measured in-process loop). Process RSS 26.7→27.9 MB; available memory ~6.66 GB; swap delta 0; Resource Guard NORMAL. OCR inference 0, VLM 0, Ollama 0.

## X. Reading Order deferred
Known shared tier/row grouping geometry remains unchanged and outside scope.

## Y–Z. Tests and files
Added an experiment-only signal/router module, deterministic benchmark runner, tests and five new 11.12 JSON artifacts. Production OCR/router/Reader code is unchanged. Focused and full validation results are recorded before review.

## AA. Final router verdict
**B. ROUTER PROMISING BUT MORE GT REQUIRED.** R2 demonstrates a zero-observed-false-safe multi-signal subset, but only 1/50 SAFE and it disappears when its page is held out. This is insufficient for production calibration or deployment.

## AB. Recommendation for 11.13
Single next experiment: validate the frozen R2 contract unchanged on a new page-grouped Human GT set. Do not relax thresholds, deploy it, change OCR engines, or combine this with reconstruction/geometry changes.
