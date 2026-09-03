# Checkpoint 12.6 — Final Re-review After Provenance Fix

## Verdict

**PASS**

The final Human-derived provenance leakage is removed. The clean one-pixel experiment satisfies GT isolation, chronology, integrity, determinism, and zero-regression gates and independently supports **B. TOLERANCE HELPS BUT REMAINS INCOMPLETE**.

## Provenance and chronology evidence

- The persisted pre-freeze control integrity manifest contains only schema/checkpoint/status, artifact identity/path, approved raw-byte SHA-256, deferred internal-verification state, and explicit empty GT/Human-derived dependency declarations. It contains no control metrics, Human sequences, positions, correctness, pair labels, inversions, outcomes, or semantic hash of a parsed evaluation object.
- Its internal semantic fingerprint independently recomputes to `ace5f6c1cf6655f74cb498ecb310c1e505332644b105308c5f2d282cd306d06d`, matching the required value.
- The pre-freeze input audit no longer contains `expected_post_freeze_metric_region_count`. Recursive audit of the actual input-audit, integrity manifest, and frozen protocol finds no forbidden Human-order-derived field.
- Oracle and Realistic candidate provenance references exactly the sanitized input audit, opaque approved raw-byte integrity manifest, and frozen protocol. Both persist `human_order_derived_provenance_dependencies=[]`, `gt_runtime_features=[]`, and three closure rows marked `human_order_derived=false`.
- A nested transitive dependency containing `resolved_pages` fails closed. Perturbing mock post-freeze Human metrics leaves provenance and all RUN_A/RUN_B Oracle/Realistic real relation-path candidate bytes unchanged.
- The enforced event trace is `RUN_A_FROZEN → RUN_B_FROZEN → GLOBAL_FREEZE_BARRIER_ACTIVE → POST_FREEZE_OPEN`. Early Human access, early evaluation, and candidate generation after GT access all fail explicitly.
- All 12.5 control JSON/internal hashes and Human metrics are opened/reconciled only after the barrier. No control evaluation metric participates in candidate provenance.

## Formula, control, and clean metrics

- Tolerance remains exactly `τx=1/W`, `τy=1/H`, algebraically one source pixel on the split axis. Equality is accepted; `>1px`, genuine overlap, cycle/conflict, and unsupported structure remain unresolved. There is one configuration, no sweep, alternative threshold, page branch, or isolation-fix geometry change.
- Frozen 12.5 bytes remain unchanged. Post-freeze control reconciles to Oracle `2/10` pages, `11/50` regions, `27/27` pairs, zero inversions; Realistic `6/10`, `24/50`, `47/47`, zero inversions.
- Oracle candidate page records independently sum to `3/10` resolved/exact pages, `19/50` regions/positions, `55/55` resolved pairs (`55/124` population coverage), zero confident/cross-panel/intra-panel inversion. Delta is `+1` page, `+8` regions, `+28` population pairs, `0` inversion. Page 5 is the newly exact page from the predeclared tolerant relation.
- Realistic independently sums to `6/10`, `24/50`, `47/47`, zero inversions, with all deltas zero. Track provenance says `NO_ORACLE_FALLBACK`, and its panel nodes remain distinct from Oracle.
- No newly resolved wrong page, previously correct confident regression, unsupported confident relation, forced ambiguity/cycle order, assignment mutation, or intra-panel regression is present.
- Historical inversions reconcile post-freeze: Page 15 inversion 1/2 unresolved both tracks; Page 17 repaired both; Page 38 Oracle unresolved and Realistic repaired. No page-specific candidate branch exists.

## Remaining blocker taxonomy

- Oracle: seven pages are blocked solely by relation representation/construction; all 50 metric regions are contained/reference-agreeing, with zero ambiguity/unassigned region.
- Realistic: 18 regions on Pages 1/3/5/15 (`4/3/8/3`) lack usable selected-panel coverage. These are upstream panel-coverage gaps, not assignment-policy ambiguity or intra-panel ordering failures.

## Validation rerun

- Synthetic real-service fixture groups: 20/20 PASS, including exact/below/beyond tolerance, genuine overlap, cycle, bridge/non-transitivity, layouts, hierarchy, permutation, and assignment regression.
- Actual-input and provenance mutations: source bytes, logical geometry, frozen Realistic panels, page set, Human-order contamination, control bytes, tolerance config, direct manifest, and nested dependency all fail closed.
- Focused 12.6 plus retained 12.5: 38/38 PASS.
- Canonical backend: 444/444 PASS.
- Python compile: PASS.
- Nine JSON/internal hashes: PASS.
- Independent RUN_A/RUN_B raw-byte equality: 9/9 PASS.
- Independent RUN_A/RUN_B semantic equality: 9/9 PASS.
- Workflow validation and `git diff --check`: PASS after final handoff.
- Resource Guard: NORMAL. OCR/VLM/Ollama: 0/0/0.
- Production Reader/Reading Order, extractor, resolver, Human GT, frozen predictions, sources, and archived 12.5 evidence remain unchanged.

## Independent outcome and boundary

**B. TOLERANCE HELPS BUT REMAINS INCOMPLETE** applies mechanically: Oracle safely gains exact page/region/pair coverage; Realistic does not improve; no tracked metric decreases and no hard gate fails. Outcome A fails because both tracks do not improve. C fails because Oracle has a useful strict gain. D does not apply because provenance/isolation and ordering safety now pass.

No new Human GT is required. The only recommended next experiment is **relation-model representation for the remaining seven Oracle relation-construction blockers**—not a larger tolerance. It is not authorized or started by this review.
