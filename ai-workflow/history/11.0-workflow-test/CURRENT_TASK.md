# Workflow Test Task

## Objective

Inspect the repository and document the canonical backend test command.

## Background

Checkpoint 11.0 needs a harmless end-to-end exercise of the repository-native
handoff without changing ComicAI production behavior.

## Files/modules likely involved

- `AGENTS.md`
- `backend/tests/`
- `backend/.venv/`

## Scope

Confirm the test framework and record the root-relative discovery command.

## Out of scope

Production source edits, dependency installation, database writes, model calls,
Reader V2, Checkpoint 11.1, commits, and pushes.

## Safety constraints

Use read-only inspection. Do not run the full backend suite for this workflow
test because only command discovery is required.

## Acceptance criteria

1. The command uses the checked-in backend virtual environment.
2. It discovers tests below `backend/tests` with `backend` as the unittest
   top-level directory so imports such as `app.services` resolve correctly.
3. No production source is changed by the test task.

## Required tests

- Validate workflow files with `python3 scripts/agent_workflow.py validate`.
- Run `git diff --check`.

## Benchmark permission

NOT ALLOWED. Do not start Ollama or run any ComicAI benchmark/model call.

## Stop condition

After independent review, stop at `AWAITING_HUMAN_APPROVAL`.
