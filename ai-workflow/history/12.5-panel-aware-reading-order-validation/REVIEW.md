# Checkpoint 12.5 — Fix #2 Final Independent Re-review

## Verdict

**PASS**

The two remaining review blockers are resolved without changing the zero-tolerance ordering policy, Human GT, frozen panel predictions, production Reader, or production Reading Order.

## Independent evidence

- Actual-input fail-closed tests mutate isolated temporary inputs consumed by the runtime loader: logical-region bbox bytes and frozen Realistic panel bytes fail on fingerprint mismatch before candidate generation; a copied source with changed bytes fails source fingerprint verification; a separately generated image with a matching recorded hash but wrong recorded dimensions fails dimension verification; a parsed page-set mutation fails explicitly. Authoritative inputs are never written.
- The pre-freeze loader recursively rejects Human-order fields. The behavioral proof regenerates both Oracle and Realistic candidates before and after reversing a mock Human sequence and requires identical serialized bytes and semantic hashes. Human order is first parsed only after candidate and freeze construction.
- Phase 0 independently reconciles ten source files against recorded SHA-256 and actual PIL dimensions, both authoritative panel snapshots, 63 persisted geometries, 50 post-freeze metric IDs, and 13 exclusions.
- RUN_A and RUN_B invoke the candidate, freeze, audit, evaluation, synthetic, protocol, and summary builders independently from the same frozen inputs. All eight corresponding artifacts are raw-byte equal; all eight content-derived semantic hashes are equal. The persisted final summary is also byte-equal after comparison evidence is inserted, and all persisted internal hashes recompute successfully.
- Oracle metrics recomputed from page records: 2/10 resolved pages, 11/50 resolved regions, 27/27 resolved comparable pairs, zero confident inversions. All 50 assignments are contained and reference-agreeing; eight pages remain unresolved from relation construction.
- Realistic metrics recomputed from page records: 6/10 resolved pages, 24/50 resolved regions, 47/47 resolved comparable pairs, zero confident inversions. There are 32 contained/reference-agreeing regions and 18 unassigned regions caused by missing selected-panel coverage on four pages; no assignment-ambiguity page is reported.
- Historical inversion audit is exact: Page 15 inversion 1 and 2 are unresolved in both tracks; Page 17 is repaired in both; Page 38 is unresolved in Oracle and repaired in Realistic. New confident inversions are zero.
- Previously verified evidence remains intact: correct Phase 0 chronology; Human order absent pre-freeze; Oracle/Realistic isolation; no Oracle fallback; exact zero tolerance; unchanged assignment hierarchy and fail-closed behavior; 18/18 synthetic fixtures through the real service path.

## Validation rerun

- Focused Reading Order tests: 21/21 PASS.
- Canonical backend suite: 427/427 PASS.
- Python compile: PASS.
- Eight JSON artifacts and internal semantic hashes: PASS.
- Eight RUN_A/RUN_B raw-byte comparisons: 8/8 PASS.
- Eight RUN_A/RUN_B semantic comparisons: 8/8 PASS.
- Source SHA-256/dimension and authoritative snapshot reconciliation: PASS.
- Resource Guard: NORMAL. OCR/VLM/Ollama: 0/0/0.
- Workflow validation and `git diff --check`: PASS after review handoff.

## Independent outcome

**C. PANEL STRUCTURE/ASSIGNMENT STILL BLOCKS ORDERING**

Outcome A fails because Oracle resolves only 2/10 pages and Realistic only 6/10. Outcome B fails because Oracle does not strictly improve the frozen baseline and leaves three of the four historical inversions unresolved. GT is sufficient, so Outcome D does not apply.

The next smallest experiment may be recommended as one predeclared source-normalized geometry-tolerance model on the same frozen ten-page cohort, with no parameter sweep, page-specific constants, Human-order runtime input, or acceptance of any new confident inversion. It is not authorized or started by this review.
