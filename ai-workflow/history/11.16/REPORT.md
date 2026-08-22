# Checkpoint 11.16 — Isolated Reading Order Geometry Experiment

## Baseline and frozen evidence

The frozen ten-page 11.11 Human click-order set reproduces exactly: 6/10 exact pages (60%), 37/50 exact positions (74%), 116/124 correct pairs (93.55%) and eight inversions. Page 3 and the earlier 11.9 artifact/source remain preserved. Human GT and frozen control hashes are unchanged.

Current production benchmark behavior is documented before candidate evaluation: logical bboxes use `[x1,y1,x2,y2]`; `tiered_order` groups by vertical center distance against mean tier center with threshold `max(4 px, min(item height, maximum tier-member height) × 0.5)`; overlap is not used; tiers follow insertion/top order; manga peers use x descending with stable IDs.

## Inversion audit

All eight control inversions were classified using geometry only: five tall-panel interference, one different-row incorrectly merged, one vertical-overlap ambiguity and one same-row misclassification. Human panel/tier labels do not exist in the simplified 11.11 click-order GT, so exact group structure, same-tier accuracy and tier merge/split counts are explicitly `N/A`; none were inferred.

## Candidate comparison

Three predeclared, interpretable, BENCHMARK-FITTED candidates were evaluated on logical-region geometry:

- A — normalized vertical overlap >= 0.50: 7/10 exact pages, 43/50 positions (86%), 120/124 pairs (96.77%), four inversions; 3 pages improved, 7 unchanged, 0 regressed.
- B — normalized center distance <= 0.50: 5/10 exact pages, 38/50 positions (76%), 117/124 pairs (94.35%), seven inversions; 2 improved, 7 unchanged, 1 regressed.
- C — overlap/center hybrid with tall-box protection: 6/10 exact pages, 40/50 positions (80%), 118/124 pairs (95.16%), six inversions; 2 improved, 7 unchanged, 1 regressed.

Candidate A is selected. It fixes Page 4 completely and removes one inversion each on Pages 17 and 38. It repairs three of five audited tall-panel interference pairs and the same-row case; two tall-panel cases, the different-row merge and overlap ambiguity remain. The explicit hybrid tall protection does not outperform the simpler overlap rule.

Page 3 remains exact under CONTROL and all three candidates. Candidate A is selected in all ten leave-one-page-out folds; this is stable on the small page-grouped set but remains benchmark-fitted, not production-calibrated.

## Performance and safety

All three candidates across ten pages execute in 0.934 ms total, approximately 31.1 μs/page/candidate and 6.22 μs/region/candidate. Process RSS remains about 26.6 MB; available memory about 6.856 GB; swap delta zero; Resource Guard NORMAL.

OCR inference, VLM and Ollama calls are all zero. Candidate code is experiment-only; production Reading Order, OCR, R2 and authoritative state are unchanged. Source type is explicit: manga uses top-to-bottom tiers/right-to-left peers, while webtoon policy remains separately representable and unbenchmarked.

## Decision

**A. GEOMETRY FIX PASS.** Vertical-overlap grouping halves inversions, improves page/position/pairwise metrics, introduces no page regression, preserves Page 3 and remains selected in every leave-one-page-out fold. It must not be deployed from ten benchmark-fitted pages.

Recommended final Reader V2 integration experiment: apply the frozen overlap rule only in an offline end-to-end Reader V2 replay with explicit predicted panel/group geometry and a new page-grouped Human validation set; preserve uncertainty for orphan/ambiguous cases and do not deploy until out-of-sample confirmation.

Focused tests pass 18/18 and full backend tests pass 327/327. Python compile, five JSON artifacts, workflow validation and diff hygiene are included in final handoff. No commit or push was performed.
