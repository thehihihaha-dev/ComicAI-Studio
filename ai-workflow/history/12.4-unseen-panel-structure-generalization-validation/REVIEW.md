# Checkpoint 12.4 — Final Unseen Generalization Review

## Verdict

**PASS**

Independent outcome: **A. UNSEEN GENERALIZATION PASS — READY FOR PANEL ORDERING VALIDATION**.

The frozen panel-structure evidence justifies beginning a separately planned and reviewed Panel Ordering validation checkpoint only after Human approval. This review does not evaluate Reading Order, claim the Reader is finished, start 12.5, or authorize automatic continuation.

## Frozen inputs and protocol

- Prediction semantic fingerprint independently matches `a0f7d0559922376be3bb665bce814d003425c59fdfbafb77c0a6bda78457e26a`; freeze file SHA-256 remains `d4a78fe375ff15f7b49798cdf7c0ee389140ea2f7d00f329b3c2cf02aa475dae`.
- Canonical authoritative GT independently reproduces `f62e38d5ed28531681b9165cca77e0f62ab37b7cf92a5161cab0c9f0cb6216ea` for exactly Pages 3, 4, 5, 7, 18, and 38.
- The evaluator imports only the geometry evaluator/resource guard and reads persisted freeze/raw/graph/output/GT artifacts. It neither imports nor executes extractor, resolver, database mutation, production Reader, or Reading Order code.
- Protocol is the predeclared inclusive IoU `0.50` one-to-one maximum-cardinality, then maximum-total-IoU matching with lexicographic stable-ID tie-breaking. It is explicitly `EVALUATION_ONLY_PREDECLARED_CONVENTION_NOT_PRODUCTION_THRESHOLD`; threshold sweep and tuning are false.

## Independent metric reconciliation

Direct recomputation from frozen resolver selections plus authoritative GT, without trusting the summary, gives 21 Human panels, 16 selected, 16 matched, five missed, zero false promoted, precision `1.000000`, recall `0.761905`, F1 `0.864865`, and one unresolved page of six (`0.166667`).

The 16 actual match records independently give IoU minimum `0.881640`, mean `0.941328`, median `0.947820`, and maximum `0.975207`.

Per-page results reconcile exactly:

- Page 3: GT/selected/matched/missed/false `4/2/2/2/0`; IoUs `0.913932, 0.899134`; frozen page flag resolved.
- Page 4: `3/3/3/0/0`; IoUs `0.972823, 0.939199, 0.952640`; resolved.
- Page 5: `3/0/0/3/0`; no match IoUs; unresolved.
- Page 7: `2/2/2/0/0`; IoUs `0.960163, 0.957457`; resolved.
- Page 18: `3/3/3/0/0`; IoUs `0.975207, 0.951940, 0.943699`; resolved.
- Page 38: `6/6/6/0/0`; IoUs `0.932851, 0.954872, 0.962575, 0.920482, 0.942635, 0.881640`; resolved.

## Safety-critical audits

- All 16 selected predictions have legitimate one-to-one matches against trustworthy full-panel GT, with minimum IoU `0.881640`. There are zero unmatched selected boxes, zero selected under-splits, and zero selected over-splits; the false-promotion audit is correctly empty.
- Page 3 `human-3-8` and `human-3-5` are resolver failures: accurate candidates `PN_f213d1da9efd` (`0.908951`) and `PN_6792c0bfba14` (`0.948437`) exist but remain `CONFLICT_NOT_RESOLVED`; the latter also conflicts with whitespace candidate `PN_da66c62e69c6` (`0.678739`).
- Page 5 `human-5-1` and `human-5-5` are `MISSING_CANDIDATE_GENERATION`: no raw candidate reaches the frozen evaluation convention. Page 5 `human-5-4` is a resolver failure: `PN_6bc262100136` exists at `0.942608` but remains unresolved.
- The primary failure split is therefore extractor 2 / resolver 3. Raw DETECTED control is 5 selected/5 matched/0 false; resolved output reaches 16 matches and does not regress below control.

## Generalization, comparison, and outcome gate

The successful pages support limited cohort-level generalization evidence for adjacent panels, horizontal/vertical division, spanning-parent replacement, tall-beside-stacked layouts, page-edge completion, and nested/internal-contour rejection. This is not universal coverage: Page 3 retains bottom conflict-resolution misses, and Page 5 exposes both missing candidate generation and unresolved contour recovery.

Relative to the fixed 12.3 reference, precision remains `1.000000`; recall improves by `0.095238`; F1 improves by `0.064865`; unresolved rate changes from `0.250000` to `0.166667`, an improvement of `0.083333`. The exhaustive correctness-blind complement and preserved precision provide no evidence of unsafe cohort overfitting, while the Page 5 failures prevent any claim of complete recovery.

Every frozen A gate passes: zero false; precision 1.0; recall at least 0.60; F1 at least 0.75; unresolved at most 2/6; no selected duplicate/internal-fragment/spanning under-split; resolver matches not below raw control; valid identities/GT; deterministic output; no leakage, resource, or production regression. No new threshold was introduced.

## Leakage, determinism, tests, and resources

- Cohort selection was the exhaustive six-page complement before correctness was known. Prediction freeze demonstrably predates the empty Human queue; Human annotation was prediction-blind and independently validated.
- Extractor/resolver hashes remain unchanged. No prediction regeneration, unseen-specific prediction rule, post-GT tuning, threshold sweep, or Human feature entered prediction runtime; `gt_runtime_features: []` throughout.
- Full hashes independently match: protocol `eecaa49ce0969c8ced0f14911b5278f3a4a0d4d6cee855cc7599478ab1eadb8a`; evaluation `1363ee8a7822207ffd216c6bc00168a347cdb0ed0bb079ccc590bb4bc3898275`; evaluation semantic `3733d42b022490f7cfd18e966aedff001b8fc9d5b2ca9b7ddf54175865f1792c`; summary `dd4d7212c0c5b126c54c9cedae2c8dd0c1e18d6301337604416c0b2b854fda5b`. Independent generation tests prove byte identity and semantic reconciliation.
- Evaluator tests 10/10 PASS; focused package 44/44 PASS; full backend 406/406 PASS; frontend coordinate/privacy 9/9 PASS; lint, production build/typecheck, Python compile, 37-file JSON/reconciliation, workflow validation, and `git diff --check` PASS.
- Resource Guard independently samples `NORMAL`; OCR/VLM/Ollama/Reading Order calls remain `0/0/0/0`. No production integration occurred.

No correction is required. Stop at `AWAITING_HUMAN_APPROVAL`; do not start Panel Ordering, Checkpoint 12.5, commit, or push.
