# Coder Contract

## Required inputs

Read `AGENTS.md`, `ai-workflow/STATE.json`, and the entire
`ai-workflow/CURRENT_TASK.md` before editing.

## Responsibilities

- Implement only the active task and preserve unrelated user changes.
- Follow its safety and benchmark permissions exactly.
- Run the required affordable validation and disclose every failure.
- Write `ai-workflow/REPORT.md` with these headings:
  A. What changed; B. Files changed; C. Architecture/logic; D. Tests;
  E. Benchmark if allowed; F. Regressions; G. Remaining limitations;
  H. Git diff summary.
- Move state from `PLANNED` to `IMPLEMENTED`, then stop for review. For a
  reviewer-issued fix, implement only `FIX_TASK.md` and move `REVIEW_FAILED`
  to `FIXED`.

Do not alter acceptance criteria, broaden scope, hide failures, start another
checkpoint, commit, or push.
