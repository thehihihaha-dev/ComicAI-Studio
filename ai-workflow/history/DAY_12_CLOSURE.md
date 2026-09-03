# ComicAI Studio — Day 12 Final Retrospective and Closure

## Final status

**DAY 12 = CLOSED**

There is no active checkpoint and no next experiment. New work requires a separate Day 13 planning session after Human discussion and approval. No Checkpoint 12.9 was created.

## Accepted checkpoint progression

- **12.2 — Deterministic manga panel structure extraction and Human GT validation:** established deterministic panel evidence, trustworthy Human panel GT, coordinate-system correction, audit isolation, and frozen correctness evaluation.
- **12.3 — Containment-aware panel conflict resolution:** accepted deterministic containment/conflict handling with fail-closed safety.
- **12.4 — Unseen panel extraction generalization:** accepted frozen unseen-cohort evaluation and Human GT trust gates.
- **12.5 — Panel-aware Reading Order validation:** established panel-aware ordering evaluation, assignment isolation, and unresolved-relation evidence.
- **12.6 — Source-normalized one-pixel relation tolerance:** accepted exact inclusive `tau_x=1/W`, `tau_y=1/H` behavior with zero confident inversion.
- **12.7 — Projection-Constraint Panel DAG V1:** accepted Outcome B partial relation recovery; Page 7 became exact while six pages remained fail-closed.
- **12.8 — Frozen panel-geometry identifiability audit:** **invalidated experiment**. Reviewer PASS applies only to invalidation handling; accepted outcome is **D. AUDIT INVALID / SAFETY FAILURE**. It makes no authoritative geometry-identifiability conclusion.

## Accepted scientific results

### Checkpoint 12.4 — unseen panel extraction

- Precision: `1.000000`
- Recall: `0.761905`
- F1: `0.864865`
- Matched panels: `16/21`
- False promotions: `0`
- Unresolved pages: `1/6`

### Checkpoint 12.6 — source-normalized relation tolerance

- Oracle: `3/10` pages, `19/50` regions, `55/124` population pairs, `0` confident inversions.
- Realistic: `6/10` pages, `24/50` regions, `47/47` resolved pairs, `0` confident inversions.

### Checkpoint 12.7 — PCPDAG V1

- Exact pages: `4/10`
- Resolved regions: `21/50`
- Population pair coverage: `56/124`
- Confident inversions: `0`
- Page 7 newly resolved and exact.
- Pages 1, 2, 3, 15, 18, and 38 remain fail-closed as `MULTIPLE_TOPOLOGICAL_ORDERS`.

## Invalidated and non-authoritative results

Checkpoint 12.8 does not prove a geometry representation limit or partial geometry identifiability. Outcome B, `15/20 IDENTIFIABLE`, row/spanning observations, contradiction classifications, equivalence claims, and the prior synthetic scientific result are non-authoritative failure provenance. They were produced after irreversible Human-order exposure or lack a valid frozen applicability contract. They were not integrated into production.

The potentially interesting row/spanning observations may be retained only as **NON-AUTHORITATIVE FUTURE RESEARCH NOTES**. Reconsideration would require a genuinely new, predeclared, blind protocol on a future day; it is not authorized here.

## Known limitations

- Panel extraction still misses some candidate geometry.
- Realistic panel coverage remains incomplete on some pages.
- Panel assignment can therefore remain incomplete.
- PCPDAG V1 cannot uniquely order six benchmark pages.
- Unresolved ordering is intentionally fail-closed.
- Geometry-only ordering remains an open research problem.
- Checkpoint 12.8 does not prove a geometry representation limit.
- Contaminated row/spanning observations are not accepted evidence.

## Technical debt and future work

### A. Validated technical debt

- Improve panel candidate coverage without lowering promotion/conflict safety gates.
- Preserve exact source-normalized geometry and deterministic identities across future extraction/ordering work.
- Maintain explicit assignment coverage and fail-closed unresolved states in production-facing work.
- Consolidate benchmark provenance and immutable artifact manifests to prevent accidental reuse of invalid evidence.

### B. Open research questions

- Which non-geometry signals can safely resolve panel precedence while remaining grounded and auditable?
- How should incomplete realistic panel coverage propagate into Reader confidence and Human review?
- What representation can express manga layouts that admit multiple PCPDAG topological orders without arbitrary tie-breaking?

### C. Invalidated observations requiring a fresh blind protocol

- Whether row membership can safely define precedence beyond existing PCPDAG evidence.
- Whether vertical spanning relationships provide a generalizable precedence constraint.
- Whether a complete geometry-signature family can establish identifiability without post-exposure design.

These are notes, not planned experiments or accepted hypotheses.

## Safety and isolation summary

- Production Reader and production Reading Order remain unchanged by the Day 12 offline experiments.
- Extractor/resolver behavior includes only previously reviewed and accepted checkpoint work.
- Human GT and Human Reading Order GT are preserved.
- Frozen predictions, source identities, and accepted checkpoint archives are preserved.
- Invalidated 12.8 evidence is isolated by an authoritative invalid-status artifact and a runner that rejects rerun.
- No contaminated 12.8 result entered production.
- Resource Guard remained `NORMAL`; OCR/VLM/Ollama were `0/0/0` where required.
- No commit or push was performed during closure.

## Closure boundary

Day 12 is closed with known limitations. It is not necessary to solve every remaining ordering problem before closure. No active task, automatic continuation, new heuristic, or Day 13 work is authorized by this document.
