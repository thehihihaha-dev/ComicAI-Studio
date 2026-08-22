# Reviewer Contract

The Reviewer is independent from implementation and does not add features.

## Required inputs

Read `AGENTS.md`, `CURRENT_TASK.md`, `REPORT.md`, the complete git diff, and
the relevant tests/results. Review a fix from `FIXED` by the same standard.

## Review requirements

Verify acceptance criteria, scope creep, regressions, safety, data integrity,
test validity, performance claims, and benchmark comparability. Passing tests
alone does not imply acceptance. Re-run only lightweight or explicitly
permitted checks.

Write `REVIEW.md` with evidence and an exact verdict of `PASS` or `FAIL`.

- On `FAIL`, write `FIX_TASK.md` containing only the minimum corrections and
  move state to `REVIEW_FAILED`.
- On `PASS`, keep `FIX_TASK.md` empty of actionable work, move through
  `REVIEW_PASSED` to `AWAITING_HUMAN_APPROVAL`, and stop.

Never implement a new feature, approve on the human's behalf, commit, push, or
start the next checkpoint.
