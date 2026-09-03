# Checkpoint 12.7 — Final Independent Re-review After Fix #2

## Verdict

**PASS**

Fix #2 resolves all four final blockers. The independently reconciled result is **B. PARTIAL RELATION RECOVERY**. This verdict authorizes only the workflow handoff to Human approval; it does not authorize production integration, a new checkpoint, commit, or push.

## Final blocker and isolation review

- Pre-freeze control reference is sanitized: `artifacts=[]`, `artifact_hashes=[]`, `human_derived_pre_freeze_dependencies=[]`, `human_order_derived_provenance_dependencies=[]`, and `gt_runtime_features=[]`. Candidate provenance closes only over the input audit, sanitized control identity, frozen protocol, and service/runner code hashes. No Human-derived 12.6 evaluation/summary hash or transitive manifest fingerprint is present.
- All nine accepted 12.6 artifact raw hashes and internal hashes are opened and verified only after both candidates are frozen and the global barrier is active.
- Persisted chronology begins exactly `RUN_A_GENERATED`, `RUN_B_GENERATED`, both freeze documents built, both runs frozen, and `GLOBAL_FREEZE_BARRIER_ACTIVE`. Human Reading Order opens later; both evaluations record `EVALUATION_ALLOWED` afterward.
- `evaluate()` calls `barrier.assert_evaluation()` itself. Executable tests reject evaluation before any freeze, with only RUN_A frozen, and with A+B frozen but the barrier inactive; valid post-barrier evaluation succeeds. Early Human access and candidate generation after Human access/freeze are rejected.
- Every declared artifact records independently recomputable RUN_A/RUN_B raw-byte and canonical-semantic SHA-256 values. Independent on-disk recomputation passes **10/10 raw** and **10/10 semantic**, including the summary's declared exclusion convention; final enveloped summaries are byte-identical.

## Representation and behavioral evidence

- Stable node IDs use exact normalized rational bbox coordinates plus deterministic duplicate ordinals and remain stable under input permutation/opaque-ID mutation.
- PCPDAG relation decisions use exact `Decimal`/`Fraction` semantics. Tolerance remains exactly inclusive `tau_x=1/W`, `tau_y=1/H`; no binary float participates in relation decisions.
- The synthetic cycle invokes the real PCPDAG and produces a real directed cycle. Actual-input mutation, nested/transitive contamination, protocol/cohort, Human-order/metric perturbation, and post-GT construction tests remain executable and pass.
- Accepted 12.6 control independently reconciles to `3/10` exact pages, `19/50` regions, `55/124` population pairs, and zero confident inversion.
- 12.7 reconciles to `4/10`, `21/50`, `56/124`, and zero confident inversion: delta `+1` page, `+2` regions, `+1` pair, `+0` inversion. Page 7 is the sole newly exact page and its complete order is correct.
- Pages 1, 2, 3, 15, 18, and 38 are acyclic, have no unsupported direct edge, each admits at least two topological orders, and fail closed as `MULTIPLE_TOPOLOGICAL_ORDERS`. Assignment is not the Oracle bottleneck. This is a PCPDAG V1 information/representation limit on the frozen geometry, not an observed implementation defect.
- Historical audit: Page 15 inversion #1/#2 `UNRESOLVED`, Page 17 `REPAIRED`, Page 38 `UNRESOLVED`; new confident inversions are zero.

## Validation and safety

- Synthetic: **26/26 PASS**.
- Coder-declared fixed focused package: **44/44 PASS**; reviewer rerun of the relevant 12.5/12.6/12.7 suites: **58/58 PASS**.
- Canonical backend: **464/464 PASS**.
- Python compile, ten JSON/internal stamps, raw/semantic hash reconciliation, workflow validation, and `git diff --check`: PASS.
- Wrong newly resolved pages, confident regressions, new confident inversions, unsupported relations, forced cycles, GT leakage, frozen-input violations, and nondeterminism: all zero.
- Resource Guard `NORMAL`; OCR/VLM/Ollama `0/0/0`.
- Production Reader/default Reading Order wiring, detector/extractor/resolver, Human Panel GT, Human Reading Order GT, frozen predictions, sources, and archived evidence remain outside the experiment and unchanged by Fix #2. No production integration is approved.

## Next scientific recommendation

Recommend exactly one smallest next experiment: a **frozen geometry-identifiability audit of the six unresolved ready sets**. Before opening Human order, compute for every simultaneously ready panel pair its complete existing PCPDAG geometry signature (exact normalized edges, axis gaps/overlaps, containment, and direct/transitive predicates); post-freeze, test whether any single deterministic signature relation separates Human precedence without contradicting already resolved controls. If indistinguishable signatures require different Human precedence, record an information-limit result; otherwise the one supported relation becomes evidence for a later separately approved candidate. Do not increase tolerance, sweep thresholds, rerun extraction, or modify GT.

No new Human GT is required.
