# Checkpoint 12.4 — Phase 2 Frozen Unseen Panel Generalization Evaluation

## A. What changed

Evaluated only the persisted frozen 12.4 resolver selections against the independently approved authoritative unseen Human GT. No extractor, resolver, candidate generation, threshold, GT, production Reader, or Reading Order state was changed.

The mechanically selected predeclared outcome is **A. UNSEEN GENERALIZATION PASS — READY FOR PANEL ORDERING VALIDATION**.

## B. Files changed

- Added evaluation-only runner `scripts/panel_unseen_evaluation_12_4.py`.
- Added five focused tests in `backend/tests/test_panel_unseen_evaluation_12_4.py`.
- Added non-overwriting artifacts:
  - `benchmarks/day12/panel-unseen-evaluation-protocol-12.4.json`
  - `benchmarks/day12/panel-unseen-evaluation-12.4.json`
  - `benchmarks/day12/panel-unseen-summary-12.4.json`
- Updated this report and workflow handoff.

## C. Architecture/logic

The runner fails closed unless the frozen prediction semantic fingerprint is `a0f7d0559922376be3bb665bce814d003425c59fdfbafb77c0a6bda78457e26a`, the authoritative Human GT canonical fingerprint is `f62e38d5ed28531681b9165cca77e0f62ab37b7cf92a5161cab0c9f0cb6216ea`, the cohort is exactly Pages 3, 4, 5, 7, 18, and 38, all prediction artifact bytes match the freeze manifest, and every runtime artifact has `gt_runtime_features: []`.

Matching uses the unchanged one-to-one maximum-cardinality, then maximum-total-IoU convention at inclusive IoU `0.50`, with stable-ID tie-breaking and no threshold sweep. It is labeled `EVALUATION_ONLY_PREDECLARED_CONVENTION_NOT_PRODUCTION_THRESHOLD`.

The runner constructs protocol, evaluation, and summary twice in memory and requires byte-identical generations before any write. Tests independently regenerate all artifacts and reconcile page totals, metrics, audits, gates, and semantic hashes.

## D. Tests

- Evaluator plus new Phase 2 tests: 10/10 PASS.
- Focused evaluator/GT/freeze/resolver package: 44/44 PASS.
- Full backend: 406/406 PASS.
- Frontend coordinate/privacy: 9/9 PASS; only harmless Node module-type warnings.
- Frontend lint: PASS.
- Frontend production build/typecheck: PASS.
- Python compile: PASS.
- JSON, frozen fingerprint, source, metric, audit, outcome, and file/semantic-hash reconciliation: PASS.
- Workflow validation and `git diff --check`: required after final workflow handoff update.

## E. Benchmark if allowed

Aggregate frozen resolver result: 21 Human panels, 16 selected predictions, 16 matched, five missed, zero false promoted; precision `1.000000`, recall `0.761905`, F1 `0.864865`; one unresolved page of six, rate `0.166667`. Matched IoUs: minimum `0.881640`, mean `0.941328`, median `0.947820`, maximum `0.975207`.

Per page:

- Page 3: Human 4, selected 2, matched 2, missed 2, false 0, IoUs `0.913932 / 0.899134`, resolved flag; remaining failure is conflict resolution of accurate bottom-panel candidates.
- Page 4: Human 3, selected 3, matched 3, missed 0, false 0, IoUs `0.972823 / 0.939199 / 0.952640`, resolved.
- Page 5: Human 3, selected 0, matched 0, missed 3, false 0, no matched IoU, unresolved; two candidate-generation misses and one resolver-conflict miss.
- Page 7: Human 2, selected 2, matched 2, missed 0, false 0, IoUs `0.960163 / 0.957457`, resolved.
- Page 18: Human 3, selected 3, matched 3, missed 0, false 0, IoUs `0.975207 / 0.951940 / 0.943699`, resolved.
- Page 38: Human 6, selected 6, matched 6, missed 0, false 0, IoUs `0.932851 / 0.954872 / 0.962575 / 0.920482 / 0.942635 / 0.881640`, resolved.

False-promotion audit is explicitly empty because every selected panel has an eligible one-to-one Human match. Selected under-splits and over-splits are both zero.

Every miss is audited:

- Page 3 `human-3-8`: `CONFLICT_RESOLUTION`; accurate `PN_f213d1da9efd` exists at IoU `0.908951` but remains `CONFLICT_NOT_RESOLVED`.
- Page 3 `human-3-5`: `CONFLICT_RESOLUTION`; accurate `PN_6792c0bfba14` exists at `0.948437`; whitespace spanner `PN_da66c62e69c6` also reaches `0.678739`; both remain unresolved.
- Page 5 `human-5-1`: `MISSING_CANDIDATE_GENERATION`; no frozen raw candidate reaches IoU 0.50.
- Page 5 `human-5-5`: `MISSING_CANDIDATE_GENERATION`; no frozen raw candidate reaches IoU 0.50.
- Page 5 `human-5-4`: `CONFLICT_RESOLUTION`; accurate `PN_6bc262100136` exists at `0.942608` but remains unresolved.

Failure split is extractor 2, resolver 3. Raw DETECTED control has 5 selected/5 matched/0 false; resolver output has 16 matched and therefore does not regress below control.

Compared with 12.3, precision stays `1.0`; recall rises by `0.095238`, F1 rises by `0.064865`, and unresolved rate falls from `0.25` to `0.166667`. Adjacent panels, horizontal/vertical divisions, spanning-row replacement, tall-beside-stacked layouts, page-edge completion, and nested/internal-contour rejection generalize on the successful pages. Page 3 residual conflicts and Page 5 candidate absence/conflict remain layout-specific weaknesses. The exhaustive unseen cohort gives no aggregate evidence of unsafe precision overfitting, but Page 5 shows recovery is not uniformly complete.

All exact A gates pass: false promoted 0; precision 1.0; recall at least 0.60; F1 at least 0.75; unresolved pages at most 2/6; no selected duplicate/internal fragment/spanning under-split; resolver matches not below raw control; no identity, determinism, leakage, resource, or production regression.

## F. Regressions

Frozen prediction, raw candidate, graph, output, and authoritative GT artifacts remain unchanged. Human GT is consumed only in the evaluator. No evaluation result feeds extractor, resolver, candidate generation, conflict graph, spanning relations, or production Reader.

Artifact hashes:

- Protocol file: `eecaa49ce0969c8ced0f14911b5278f3a4a0d4d6cee855cc7599478ab1eadb8a`.
- Evaluation file: `1363ee8a7822207ffd216c6bc00168a347cdb0ed0bb079ccc590bb4bc3898275`.
- Evaluation semantic: `3733d42b022490f7cfd18e966aedff001b8fc9d5b2ca9b7ddf54175865f1792c`.
- Summary file: `dd4d7212c0c5b126c54c9cedae2c8dd0c1e18d6301337604416c0b2b854fda5b`.

Resource Guard remained `NORMAL`; OCR/VLM/Ollama/Reading Order calls are `0/0/0/0`.

## G. Remaining limitations

Recall remains incomplete at 16/21. Page 5 loses all three panels, with two extraction-origin failures and one resolver-origin failure; Page 3 retains two resolver-origin misses despite accurate candidates. No fixes or tuning are included.

Outcome A establishes sufficient panel-structure generalization to justify a separately planned and reviewed panel-order validation. It does not claim Reading Order correctness, authorize starting it automatically, or make the IoU convention a production threshold.

## H. Git diff summary

Phase 2 adds one evaluation-only runner, one focused test module, three finite artifacts, and workflow documentation. Detector/resolver/GT/Reader/Reading Order code and frozen artifacts were not modified. No commit or push was performed.
