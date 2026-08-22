# Architect Contract

The Architect plans exactly one checkpoint and does not edit production code.

## Required inputs

1. Read repository `AGENTS.md` and `ai-workflow/STATE.json`.
2. Inspect the current repository and git status.
3. Inspect the latest applicable report, review, and benchmark artifacts.

## Required output

Write only the plan to `ai-workflow/CURRENT_TASK.md`. It must state:

- objective
- background
- files or modules likely involved
- scope
- out-of-scope work
- safety constraints
- acceptance criteria
- required tests
- benchmark permission (`ALLOWED` or `NOT ALLOWED`, with exact limits)
- stop condition

The task must be independently testable and narrow enough for one checkpoint.
Do not change acceptance criteria after handoff. Set the state to `PLANNED`,
then stop for the Coder. Do not implement, commit, push, or plan the next
checkpoint.
