# Coder Report

## A. What changed

Documented the canonical backend test command in the repository instructions.

## B. Files changed

- `AGENTS.md` (documentation only)

## C. Architecture/logic

The repository has `unittest`-style tests under `backend/tests`. The canonical
root-relative command is:

`backend/.venv/bin/python -m unittest discover -s backend/tests -t backend`

Using `-t backend` makes the existing `app.*` imports resolve while `-s` limits
discovery to the backend suite.

## D. Tests

Workflow validation and `git diff --check` are required after all workflow
files are created. The full backend suite was intentionally not run.

## E. Benchmark if allowed

Not run; the task explicitly forbids benchmarks and model calls.

## F. Regressions

None observed. The test task changed documentation only.

## G. Remaining limitations

The command documents the current repository layout and must be updated if the
test package or environment layout changes.

## H. Git diff summary

Documentation and repository-native workflow artifacts only; no ComicAI
production behavior changed.
