# Checkpoint 12.0 — Independent Re-review After Fix

## Verdict

**PASS**

Independent checkpoint verdict: **C. CURRENT GEOMETRY INSUFFICIENT**.

## Independent evidence

- Frozen baseline independently recomputes exactly from the Day 11 candidate outputs: 7/10 exact pages, 43/50 exact positions, 120/124 correct pairs (96.77%), and four inversions. Page 3 remains exact. The rule is normalized vertical overlap `>= 0.50` and remains `BENCHMARK_FITTED`, not production-calibrated.
- Page 15 source bytes show the two Human-before regions in the bottom-right panel and `LR_f3054b9c1820` (`PÍP!`) in the separate bottom-left phone panel. Human GT completes the right panel before the left panel; the frozen prediction instead promotes the higher sound-effect bbox. Both inversions are cross-panel failures. Panel containment/order and text-to-panel assignment explain the intended sequence; bbox tier splitting is only the observed mechanism of reversal.
- Page 17 source bytes show `LR_554cd55f1a6a` in the top-right panel and `LR_8a526b453c10` (`HỬ?`) in the top-left panel. Human and manga panel policy read right before left. The previous tall-region label was therefore weaker than the visible cross-panel cause; `PAGE_FALLBACK` loses the decisive ownership and panel order.
- Page 38 similarly places `LR_505a871ebd18` in the bottom-right panel and `LR_563eb986d1f9` in the bottom-left panel. All four inversions now have the supported primary class `panel/group construction`, with failed overlap/tier separation recorded only as a contributing geometric symptom. No distinct residual failure class is being forced into this taxonomy.
- Current Human evidence supports exactly three missing structural elements: panel containment identifies each region's owner; panel adjacency/order sequences the observed right and left panels; text-to-panel assignment transfers that sequence to logical regions. All four failures motivate all three elements. A larger reading-order graph is not claimed as proven.
- Direct SHA-256 recomputation matches the three affected current upload files: Page 15 `a54e8e…8b19`, Page 17 `45e957…ed39`, and Page 38 `969152…7e30`. The immutable Human GT artifact hash remains `743628…f235`; its source/representation identities and ordered/excluded sets remain internally consistent.
- The corrected synthetic fixture calls the actual frozen `tier_order` path. Independent execution produces `C,B,A` in one tier with bridge B and `A,C` in separate tiers without B, demonstrating non-transitive tier membership and unrelated-region influence. It is labeled `SYNTHETIC`, excluded from Human metrics, and explicitly not presented as the cause of the four Human failures.
- `COMPLETE_LINK` and `ANCHOR_LINK` remain unchanged diagnostics: both reproduce 7/10, 43/50, 120/124, four inversions, repair zero known errors, create zero new inversions, and have 0 improved/10 unchanged/0 regressed pages. They do not threshold-shop or use page-specific prediction rules.
- The small ten-page/shared-style benchmark and benchmark-fitted threshold do not support production calibration. Verdict C follows because text-region coordinates with `PAGE_FALLBACK` cannot represent the visible panel ownership/order that determines all four residual Human pairs; it is not attributed to a tie bug, manga RTL error, or the synthetic bridge risk.

## Validation rerun

- Focused Reading Order/final-contract/fast-pass tests: 26/26 PASS.
- Canonical backend suite: 335/335 PASS in 2.722 s.
- Python compilation: PASS.
- Five Day 12 JSON artifacts and corrected cross-artifact invariants: PASS.
- Workflow validation in `FIXED` state: PASS.
- `git diff --check`: PASS.
- Resource Guard: NORMAL. OCR/VLM/Ollama calls: 0/0/0.
- Git diff contains no production Reading Order, OCR, Story, R2, Repair Boundary, Human GT, or Day 11 historical artifact modification. No commit or push was made.

## Smallest next experiment

Checkpoint 12.1, if Human-approved later, should test one offline panel-aware ordering prototype on the existing immutable ten-page Human click-order GT first. Use a separate benchmark-only manual panel containment/adjacency fixture for Pages 15, 17 and 38; do not alter Human GT. Hypothesis: explicit panel containment/order plus text-to-panel assignment repairs the four cross-panel inversions without regressing any currently exact page or creating a new inversion. Report exact pages, positions, pairwise accuracy, inversions, page deltas, and failure-level changes.

No new Human GT is needed before that first structural experiment. Unseen annotation remains deferred until the existing-GT prototype demonstrates value.

All previous blockers are resolved. Stop at `AWAITING_HUMAN_APPROVAL`; do not start 12.1.
