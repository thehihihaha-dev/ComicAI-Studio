# Checkpoint 12.8 — Review Failure Fix #2

## A. What changed

Accepted the irreparable blindness failure and removed Outcome B/C from authoritative evidence. Checkpoint 12.8 now ends as **D. AUDIT INVALID / SAFETY FAILURE**. No clean audit rerun was performed, no Phase A representation was expanded again, and no row/spanning finding is treated as blind evidence.

The current runner fails closed before execution with `Checkpoint 12.8 is invalidated; authoritative audit rerun is forbidden`. A separate invalid-status record preserves the known original fingerprints, documents that exact original Phase A bytes are unavailable, and labels all post-exposure structural findings non-authoritative.

## B. Files changed

- `scripts/panel_geometry_identifiability_audit_12_8.py`: immutable invalidation gate; no audit logic or production ordering change.
- `backend/tests/test_panel_geometry_identifiability_audit_12_8.py`: executable invalidated-rerun rejection test; useful historical safety/property tests retained.
- `benchmarks/day12/panel-geometry-identifiability-invalid-status-12.8.json`: authoritative Outcome D/status evidence.
- Existing eight 12.8 artifacts are preserved unchanged as invalidated failure provenance, not authoritative identifiability results.
- Workflow report/state only.

## C. Architecture/logic

The known original blind protocol fingerprint is `e29b2797c4c8f9d1a808b838c306e9585bce657f0454b27235a7a2b9f8d416d6`; the known original frozen Phase A raw hash is `91cfbe30539c4fd6090e98607d4de30c5d7c6cbb623b19c58e3e19b27e682912`. Exact original Phase A bytes were searched for but were unavailable and were not reconstructed.

The post-exposure protocol fingerprint is `79f609d8354903d0a1b39ec9ecc19ec172172b5d6491f648f3de9bb620ececb7`, and the post-exposure Phase A hash is `f96ebcb4bc7bc661c564a69ffabbe4c76eac3076dddde6c0dcf632ff89a360a8`. The four added directional rules and all `15/20 IDENTIFIABLE`/Outcome B claims are explicitly non-authoritative.

Because the finite vocabulary cannot be made blind after label exposure, there is no scientifically acceptable clean re-execution under this checkpoint's permission. The historical ready-set enumeration remains valid at 20 (`1/1/3/12/1/2`), but every identifiability classification is `null` authoritatively. Target-specific contradiction count is authoritatively zero because applicability was not frozen and cannot be reconstructed after exposure. The previous 23-to-460 attachments are retained only inside invalidated artifacts and are not endorsed.

The invalidation status records:

- blindness restored: false;
- clean rerun performed: false;
- conclusion: `NO_VALID_IDENTIFIABILITY_CONCLUSION`;
- synthetic authoritative pass count: null;
- `gt_runtime_features=[]`;
- OCR/VLM/Ollama `0/0/0`;
- production changed: false.

## D. Tests

- Corrected 12.8 focused safety/status suite: **18/18 PASS**.
- Expanded relevant retained suite: **76/76 PASS**.
- Canonical backend: **482/482 PASS**.
- Invalidated authoritative rerun: executable fail-closed PASS.
- Existing barrier, mutation, Human-perturbation, exact geometry/property, and historical artifact tests remain green but do not reauthorize the invalid audit.
- Existing invalidated artifact envelope still recomputes 8/8 raw and 8/8 semantic as provenance only.
- Invalid-status JSON validation and raw SHA-256: PASS.
- Python compile, workflow validation, and `git diff --check`: PASS after handoff.

There is no authoritative end-to-end synthetic PASS count. The prior `31/31` belongs to the invalidated Phase A family and is explicitly not used as audit evidence.

## E. Benchmark if allowed

No benchmark was rerun. Authoritative outcome: **D. AUDIT INVALID / SAFETY FAILURE**.

The only preserved scientific statement is that the original six-rule run did not establish a complete representation result. Post-exposure row/column/spanning findings cannot justify an implementation experiment.

## F. Regressions

Production Reader/Reading Order, PCPDAG V1, extractor, resolver, detector, assignment, intra-panel behavior, Human Panel GT, Human Reading Order GT, frozen predictions, sources, and accepted archives remain unchanged. Resource Guard is NORMAL; no model call occurred.

## G. Remaining limitations

Checkpoint 12.8 cannot answer its identifiability question because blindness is irrecoverable under its frozen-run contract. No new Human GT is required. This evidence neither confirms a geometry representation limit nor justifies a row/spanning ordering experiment. The Human must decide how to close Day 12; no Checkpoint 12.9 is created or recommended here.

## H. Git diff summary

Fix #2 adds only an audit invalidation gate/status/test and workflow handoff. It does not rerun the experiment, edit production/GT, commit, or push.
