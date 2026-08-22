# Checkpoint 11.14 — Deterministic Structural Reconstruction Experiment

## Dataset and controls

The frozen replay contains all 81 unseen 11.13 logical regions: 71 VERIFIED transcription labels, the 47 observed structural-error cases, and 10 intentional UNREADABLE diagnostics. Every source file matches its recorded SHA-256. The 11.13 manifest and Human GT hashes remain unchanged. Human text was used only after OCR for evaluation; candidate crop, grouping, ordering and rejection decisions use geometry only.

CONTROL is the persisted 11.13 OCR output. Three candidates were declared before OCR: logical crop with 2% padding; bounded adaptive 4% padding (3–14 px); and per-fragment 2%-padded recognition followed by deterministic top-to-bottom/left-to-right reconstruction. EasyOCR 1.7.2 (`vi`, `en`, CPU) remained the sole controlled engine.

## Full VERIFIED comparison (N=71)

- CONTROL: exact 8/71 (11.27%), CER 14.85%, WER 38.88%.
- Logical 2%: exact 8/71, CER 14.60%, WER 38.67%; 12 improved, 42 unchanged, 17 regressed; zero correct→wrong; two large CER regressions.
- Adaptive bounded: exact 8/71, CER 14.55%, WER 39.92%; 14 improved, 35 unchanged, 22 regressed; one correct→wrong; five large CER regressions.
- Fragment-line 2%: exact 8/71, CER 14.75%, WER 38.46%; 1 improved, 69 unchanged, 1 regressed; zero correct→wrong and zero large regression.

Adaptive bounded is the best candidate by the predeclared lowest-micro-CER comparison, but the gain is only 0.29 percentage point CER (about 1.98% relative), exact match does not improve, WER worsens, and regression safety is unacceptable for integration. It is experiment evidence only.

## Structural focus and geometry audit

For the 47 structural-error cases, CONTROL has 0 exact and 15.45% CER. Adaptive bounded has 1/47 exact and 14.72% CER: 1 repaired, 13 improved, 17 unchanged and 17 regressed. All logical boxes are exact fragment unions and therefore have no source-pixel margin. Geometry signals include 49 multi-fragment samples, 42 vertically stacked sets, 30 overlap cases, 16 ambiguous/distant ownership cases and 3 fragment-order changes. These are deterministic warnings, not semantic ownership claims.

Regression audit for the selected candidate records one correct→wrong, five large CER regressions, zero newly clipped crops and fourteen regression cases coinciding with structural-review geometry. No newly split previously-correct multi-fragment sample was observed.

## False-safe and UNREADABLE replay

The 11.13 frozen-R2 false-safe remains unchanged: OCR and adaptive output are both `\"STAR` versus Human `STAR`. Structural reconstruction does not remove the error, and frozen R2 remains GENERALIZATION FAIL.

Across the 36 historical 11.12 baseline false-safe cases, adaptive bounded repairs 2 exactly; 15 improve, 12 are unchanged and 9 regress. This is reported as structural-fix behavior, not router success.

All ten UNREADABLE crops receive larger bounded crop geometry without modifying or inferring Human text. Accuracy is not scored; no claim is made that the hidden text became readable.

## Runtime, safety and preservation

The controlled run made 430 sequential EasyOCR calls (primary candidates plus selected-candidate historical false-safe replay). EasyOCR initialized in 1.355 s; primary 81-region benchmark took 9.732 s; measured primary OCR time was 9.366 s; deterministic crop overhead was 0.0131 s, about 0.162 ms/region. Total run wall time was approximately 14.242 s.

Resource Guard remained NORMAL before initialization, after initialization and throughout the run. Peak RSS was about 1.548 GB; available memory ended around 6.381 GB; swap delta was zero. VLM/Ollama calls were zero, OCR concurrency was one, and authoritative production state, Human GT, frozen R2, Reading Order and production code paths remained unchanged.

## Decision

**B. PARTIAL STRUCTURAL IMPROVEMENT.** Deterministic padding helps a subset and repairs one structural case, but exact accuracy is unchanged and regressions outweigh improvements for the best-by-CER candidate. Preserve the experiment candidate and per-sample evidence for later comparison; do not integrate or deploy it.

Recommended 11.15 experiment: one controlled residual recognition benchmark on the still-wrong HARD/STRUCTURAL_REVIEW regions, using the frozen structural candidate as a comparator and evaluating alternative recognition/repair without threshold-tuning R2.

Focused tests pass 14/14; full backend suite passes 313/313. Python compile, six JSON artifact validation, workflow validation and diff hygiene are included in final handoff. No commit or push was performed.
