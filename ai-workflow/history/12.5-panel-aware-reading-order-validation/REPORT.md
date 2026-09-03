# Checkpoint 12.5 — Review Failure Fix #2

## A. What changed

Completed only the two remaining evidence corrections: actual mutated inputs now execute through fail-closed validation, and RUN_A/RUN_B independently build and byte/semantic-compare all eight deterministic artifacts. Zero-tolerance behavior is unchanged. The corrected outcome remains **C. PANEL STRUCTURE/ASSIGNMENT STILL BLOCKS ORDERING**.

## B. Files changed

- Updated the isolated 12.5 runner with injectable runtime paths/source overrides, source-dimension verification, pure final builders, and two-run artifact comparison.
- Added explicit assignment states and refined blocker taxonomy without changing assignment decisions.
- Expanded the existing fix test module with actual temporary-input mutations and artifact regeneration/hash checks.
- Regenerated only the eight 12.5 artifacts and updated workflow evidence.

## C. Architecture/logic

All mutations use temporary copies. The loader hashes actual logical/resolver JSON bytes before parsing, rejects Human-order-contaminated runtime documents, validates the exact page cohort, recomputes panel snapshots, hashes source bytes, and reads image dimensions from the source itself. Oracle and Realistic candidates are regenerated on both sides of a reversed mock Human-order object and remain byte/semantic identical.

RUN_A and RUN_B independently rebuild runtime audit, protocol, 18 synthetic traces, both candidates, freeze, final input/GT audit, evaluation, and summary. Raw rendered bytes and canonical hashes match for each named artifact. Human order remains post-freeze only.

Assignments now persist `ASSIGNED_CONTAINED` / `ASSIGNED_INTERSECTION`. Realistic unresolved taxonomy distinguishes missing panel coverage from assignment ambiguity; all four incomplete pages and 18 regions are missing-coverage cases, with zero assignment-ambiguity pages.

## D. Tests

- Focused Checkpoint 12.5: 21/21 PASS.
- Full backend: 427/427 PASS.
- Eighteen synthetic fixtures: 18/18 PASS.
- Actual source-byte, dimension, logical-bbox, realistic-panel, page-set, and Human-order-contamination tests: PASS.
- Oracle/Realistic Human-order perturbation regeneration: PASS.
- Eight-artifact RUN_A/RUN_B byte and semantic equality: PASS.
- Python compile, JSON/internal hash reconciliation, workflow validation, and diff check: PASS after handoff validation.
- Frontend not touched; frontend rebuild not required.

## E. Benchmark if allowed

Oracle: 2/10 resolved pages, 11/50 regions, 27/27 resolved pairs, pair coverage 27/124, zero confident inversion; 50 contained/reference-agreeing assignments; eight relation-construction blockers.

Realistic: 6/10 resolved pages, 24/50 regions, 47/47 resolved pairs, pair coverage 47/124, zero confident inversion; 32 contained/reference-agreeing, 18 unassigned; four missing-panel-coverage pages, zero assignment-ambiguity or relation/intra-panel failure among the remaining output.

Day 11 inversion audit remains: Page 15 ×2 unresolved in both tracks; Page 17 repaired in both; Page 38 unresolved Oracle and repaired Realistic. New confident inversions: zero.

## F. Regressions

No geometry epsilon/sweep, page rule, candidate selection change, detector/resolver rerun, GT mutation, production integration, OCR/VLM/Ollama call, or frozen input mutation occurred. Authoritative bytes remain unchanged after isolated tests.

## G. Remaining limitations

Exact zero-tolerance panel separation still leaves eight Oracle pages unresolved. Realistic additionally lacks coverage for 18 metric regions. No tolerance experiment is implemented or authorized.

## H. Git diff summary

Changes remain confined to the offline 12.5 runner/service evidence fields, focused tests, eight artifacts, and workflow documents. No commit or push was performed.
