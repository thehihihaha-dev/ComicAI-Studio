# Checkpoint 12.0 — Reading Order V3 Failure Audit

## A. What changed

Implemented an offline-only deterministic audit for the frozen Day 11 manga Reading Order rule. It reproduces the ten-page baseline, reconstructs all four remaining inversions, traces tier decisions, checks Human GT/artifact integrity, demonstrates the global single-link bridge risk with a separate synthetic fixture, and compares two narrowly justified tier-linkage prototypes. Production Reader, OCR, Story, Human GT, and historical artifacts are unchanged.

The initial Coder analysis misclassified Pages 15 and 17 as primarily row/tier or tall-region failures. Independent review inspected the available source images and rejected that taxonomy. This fix cycle corrects all four inversions to the evidence-backed primary cause: cross-panel ordering lost by `PAGE_FALLBACK`. Text-tier splitting remains only the contributing geometric symptom.

Final checkpoint verdict: **C. CURRENT GEOMETRY INSUFFICIENT**.

## B. Files changed

- Added `scripts/reading_order_failure_audit_12_0.py`.
- Added `backend/tests/test_reading_order_failure_audit_12_0.py`.
- Added five JSON artifacts under `benchmarks/day12/`, including a separately labeled `SYNTHETIC` bridge fixture.
- Updated `ai-workflow/REPORT.md` and workflow state for Coder handoff.
- Architect-owned `ai-workflow/CURRENT_TASK.md` remains the frozen plan.

No production module or Day 11 artifact was edited.

## C. Architecture/logic

### Frozen baseline and four inversions

Baseline reproduced exactly: 7/10 exact pages, 43/50 exact positions, 120/124 correct pairs (96.77%), four inversions, 3 pages improved, 7 unchanged, 0 regressed versus the old control, and Page 3 exact. The rule remains normalized vertical overlap `>= 0.50`, `BENCHMARK_FITTED`.

1. Page 15, `LR_0856a888b8df` before `LR_f3054b9c1820`: the first region is in the visible bottom-right panel and `PÍP!` is in the separate bottom-left phone panel. Manga panel order reads right before left. Lost panel containment/order makes the text-only sorter emit the higher `PÍP!` bbox first.
2. Page 15, `LR_5bdd1160b3a0` before `LR_f3054b9c1820`: this dialogue is also in the bottom-right panel, which must complete before the bottom-left phone panel. Zero text-bbox overlap is a symptom; missing text-to-panel assignment is the root cause.
3. Page 17, `LR_554cd55f1a6a` before `LR_8a526b453c10`: the first region is in the top-right panel and `HỬ?` is in the top-left panel. Manga panel order reads right before left. The prior tall-region label was incorrect; `PAGE_FALLBACK` discards the decisive panel boundary.
4. Page 38, `LR_505a871ebd18` before `LR_563eb986d1f9`: the first region is in the bottom-right panel and the second in the bottom-left panel. Missing panel containment/adjacency again lets top-to-bottom text tiers reverse the pair.

The artifact records full bboxes, dimensions/aspect ratios, horizontal/vertical and intersection/containment relationships, neighboring regions, tier traces, source/asset identity, and limitations for each case.

### Decision-flow audit

The frozen offline final contract calls `tier_order(A_VERTICAL_OVERLAP, MANGA)`. It sorts input by `(y1, x1, stable id)`, admits an item to the first tier where **any** peer overlaps vertically by at least 0.50, sorts tiers by minimum y, sorts manga peers by x descending, then flattens. Panel/group metadata is unused in this ten-page replay because every region is `PAGE_FALLBACK`. Ambiguity is recorded only when an item matches multiple tiers; the algorithm still forces the first match.

The production fast-pass is a distinct path: optional panel assignment followed by a center-distance `tiered_order`. The legacy model-backed Vision path is also separate and was not executed.

The emitted list is deterministic and globally transitive, so it cannot contain a cycle. However, the same-tier relation itself is non-transitive, and single-link admission allows an unrelated/tall bridge region to merge otherwise separate tiers and change whether x-order or y-order controls existing regions. The separate `SYNTHETIC` fixture demonstrates `A~B`, `B~C`, but `A!~C`; it is not counted as Human GT.

### Human GT integrity

All ten pages have unique positions, no missing ordered regions, no ordered/excluded overlap, and no unclassified logical regions. Source and representation hashes match between Human and logical artifacts. All five 11.17 manifest input hashes match current Day 11 artifact bytes. Direct hashing also resolves each of the three affected source hashes to exactly one current upload file. Human GT hash is unchanged. Manual visual panel evidence is labeled `BENCHMARK_ONLY_MANUAL_AUDIT` and is not added to authoritative Human GT.

The smallest missing structure supported by all four failures is: panel containment to identify ownership, manga panel adjacency/order to sequence right before left, and text-to-panel assignment to apply that panel sequence to logical regions. No larger graph architecture is claimed by this checkpoint.

### Candidate directions and result

- `COMPLETE_LINK`: require overlap with every tier member. It reused 0.50, ran no sweep, and produced the exact frozen result: 7/10, 43/50, 120/124, four inversions, 0 improved/10 unchanged/0 regressed; all four failures unchanged and no new inversion.
- `ANCHOR_LINK`: compare each item with the stable first tier member. It also produced 7/10, 43/50, 120/124, four inversions, 0/10/0; all four failures unchanged and no new inversion.
- `PANEL_AWARE_AMBIGUITY`: not run because required validated panel/group and uncertainty metadata does not exist. This is the safest next controlled experiment, not a production candidate.

The unchanged prototypes show that the demonstrated bridge hazard is not the direct cause of these four errors. The four residual errors span tier splitting and absent panel/group structure; lowering a threshold would be benchmark fitting without evidence of generalization.

Future `AMBIGUOUS_ORDER` evidence could include multiple plausible tier constructions with different orders, multi-tier membership, absent/multiple panel ownership, or weak geometry that conflicts with panel sequence. No production ambiguity routing was added. The corrected synthetic fixture now executes the frozen algorithm: with bridge B it emits `C,B,A` in one RTL tier; without B it emits top-to-bottom `A,C`. This proves the architectural bridge risk but does not explain the four Human failures.

## D. Tests

- Focused Reading Order/final-contract/fast-pass tests after review fixes: 26/26 PASS when run from `backend/`.
- An initial root-level targeted invocation produced three `ModuleNotFoundError: app` import errors; rerunning with the repository's documented backend working directory passed. This was a command-context error, not a test failure in the implementation.
- Canonical backend suite after review fixes: 335/335 PASS in 2.632 s.
- Python compilation: PASS.
- Five JSON artifacts plus cross-artifact baseline, inversion, input-hash, and resource assertions: PASS.
- Workflow validation while in Coder state: PASS.
- `git diff --check`: PASS.

## E. Benchmark if allowed

Only the permitted offline ten-page geometry/GT replay and two narrow structural prototypes were run. No image or database mutation was involved. OCR calls = 0, VLM calls = 0, Ollama calls = 0. Resource Guard remained `NORMAL`.

Leave-one-page-out 10/10 remains encouraging but not production calibration: N is only ten pages/50 regions, pages share manga/layout style, geometry patterns repeat, the threshold was observed on this benchmark, and difficult panel/tier layouts are not authoritatively represented.

No new Human testing is required for the first next experiment. The smallest justified 12.1 scope is an offline panel-aware prototype on the existing immutable ten-page click-order GT, with a separate benchmark-only manual panel containment/adjacency fixture for Pages 15, 17 and 38. It must report the frozen metrics and accept no regression of an existing exact page and no new inversion. Unseen Human pages are deferred until this structural hypothesis demonstrates value.

## F. Regressions

No production behavior changed. Both diagnostic prototypes created zero new inversions, repaired zero known inversions, and left all ten page outcomes unchanged. Existing Day 11 Page 3, tall-region behavior, deterministic order, frozen overlap metrics, and excluded-region handling remain covered.

## G. Remaining limitations

- Current flattened `PAGE_FALLBACK` data cannot distinguish text-region tier membership from cross-panel sequence for the residual cases.
- Human click-order establishes expected sequence but not the structural reason behind it.
- The synthetic fixture proves an algorithmic possibility, not prevalence in Human data.
- New unseen pages remain deferred and would require a later justified plan; existing evidence is sufficient for the first structural prototype.

Recommended Checkpoint 12.1: controlled panel/group-aware ordering plus `AMBIGUOUS_ORDER` evaluation on the existing frozen ten-page GT first, with zero OCR inference and no new Human testing initially.

## H. Git diff summary

Changes are isolated to the frozen Architect workflow files, one offline diagnostic script, one focused test module, five Day 12 JSON artifacts, and this report. No commit or push was performed.
