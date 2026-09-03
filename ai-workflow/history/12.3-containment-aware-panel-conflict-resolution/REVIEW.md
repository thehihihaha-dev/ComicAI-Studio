# Checkpoint 12.3 — Independent Re-review After Fix

## Verdict

**PASS**

Independent outcome: **A. CONFLICT RESOLUTION PASS — SAFE STRUCTURAL RECOVERY**.

## Fixed-blocker verification

- The graph now contains seven explicit `SPANNING_PARENT_SUBPANEL_SET` relations. Each has a semantic-derived stable relation ID, parent candidate ID, deterministically sorted member IDs, structural reason, parent/member provenance, frozen `edge_join_fraction`, and derived tolerance. These relations are separate from generic pairwise `CONTAINS` edges.
- `UNDER_SPLIT_SPANNER` parents and `GUILLOTINE_TILING_CHILD` selections reference the corresponding relation IDs. Relation construction uses only candidate geometry/provenance and the frozen configuration; the resolver still accepts only `panels` and `config`, with no page, source, GT, pixel, or Reading Order argument/branch.
- The corrected adjacent fixture contains exactly two independent neighboring multi-source candidates, no parent, nested fragment, or duplicate. The real resolver selects both as `MULTI_SOURCE_ATOMIC`, and the graph emits no spanning relation for the fixture.
- Executed fail-closed tests cover both a wrong frozen file hash and a mutated frozen candidate whose semantic material no longer matches. Neither path regenerates data or updates expected hashes.
- The behavioral isolation test executes the real resolver twice around deliberately different mock evaluation-GT values and verifies byte/semantic-identical graph/output. Static runtime evidence also remains `gt_runtime_features: []`.

## Independent metrics and safety

- Frozen prediction SHA-256 independently remains `80e46d5c6216e3d18e9686af149a0012911795a246d1323ae4bb74d516b4b735`; persisted Human GT independently remains `5ac1383fdbd611bd203fa1e1b35d8fb0eb4e4e082f62e04907adc493c5635fd3`.
- Independent replay over reversed candidate permutations exactly matched the persisted graph/output, including relations, selection, reasons, ordering, and semantic hashes.
- Candidate metrics independently recompute to 10/15 matched, five missed, zero false, precision `1.0`, recall `0.666667`, F1 `0.800000`, and one unresolved evaluation page. No selected under-split spanner, internal fragment, or duplicate remains.
- Page 1 is honestly unresolved at `0/3`; no bbox was synthesized. Page 2 remains `2/2`, zero false, byte-identical geometry, IoUs `0.978158` and `0.918092`, and no extra fragment. Page 15 remains `3/5`; Page 17 remains `5/5` through generic behavior.
- Eight synthetic fixtures remain separate from Human metrics and cover the spanning parent, nested fragment, duplicate, standalone adjacent pair, large panel, tall-beside-stacked layout, unresolved overlap, and Page 2-style locked control.
- Resolver tests: `18/18 PASS`; focused panel suite: `57/57 PASS`; canonical backend: `392/392 PASS`; Python compile and five-artifact JSON/hash/cross-metric reconciliation: PASS.
- The earlier failed runner attempt reached only a sandbox-blocked localhost DB connection after graph/output persistence. The runner has no database mutation call, and the successful read-only rerun produced a fully cross-linked consistent five-artifact set.
- Resource Guard is `NORMAL`; OCR/VLM/Ollama calls are `0/0/0`. No production caller imports the resolver. Detector, Reader, Reading Order, Story/OCR, Human GT, and frozen 12.2 inputs remain isolated and unchanged.

## Recommendation

A small separately approved unseen Human panel-structure validation is justified before any production or Reader integration. Use only a few previously unused pages representing simple adjacent panels, spanning rows, tall-beside-stacked layouts, nested contours, and at least one difficult unresolved page. Annotate panel boxes/ambiguity only; do not collect OCR transcription or Reading Order yet. Measure precision, recall, false promotions, and unresolved-page rate without tuning on the unseen results.

No unseen validation, production integration, next checkpoint, commit, or push was performed during review.
