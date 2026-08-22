# Checkpoint 11.1 — Machine Safety + Resource Baseline

## Objective

Establish factual macOS resource telemetry, a configurable safety-state
contract, and a reusable single-heavy-inference guard before Reader V2 work.

## Background

The target is a fanless Apple Silicon MacBook Air M4. Existing EasyOCR runs in
the backend Python process on CPU; Vision, dialogue, Story, and script model
calls use Ollama's local HTTP API. Current instrumentation measures durations
and model-call counts but not memory/swap or admission safety.

## Files/modules likely involved

- `backend/app/services/performance.py`
- `backend/app/services/model_runtime.py`
- `backend/app/services/ollama_vision.py`
- `backend/app/services/ollama_text.py`
- focused backend tests
- one small baseline script/artifact under `scripts/` and `benchmarks/day11/`

## Scope

- Add standard-library macOS/resource sampling with explicit unavailable data.
- Add configurable NORMAL/WARNING/CRITICAL classification.
- Enforce process-local heavy model concurrency of one at both Ollama callers.
- Record resource start/end/peak observations in existing performance reports.
- Run a single smallest representative benchmark using existing persisted data.
- Document the current runtime architecture and factual limitations.

## Out of scope

OCR/model replacement, Reader V2, panel ordering, hard-region batching, Story
semantics, Ground Truth changes, threshold reductions, worker architecture,
frontend work, large chapters, commits, pushes, and Checkpoint 11.2.

## Safety constraints

- Do not kill services or external model processes.
- Reject a new heavy launch at CRITICAL; at WARNING, allow only an already-held
  slot and reject additional concurrent work.
- Always release the slot after failure.
- Preserve persisted user-approved data and benchmark comparability.
- Do not fabricate unavailable macOS metrics or temperatures.

## Acceptance criteria

1. Telemetry includes UTC timestamps, wall time, process RSS, available memory
   when reliable, swap used/delta, safety state, and model-call count.
2. Thresholds are environment-configurable, conservative, documented, and
   unit-testable against injected samples.
3. At most one heavy Ollama request launches per backend process; WARNING and
   CRITICAL pre-launch behavior is tested.
4. Exceptions release the guard without deadlock.
5. Existing model/pipeline behavior and data semantics are unchanged.
6. A secret-free machine-readable baseline artifact records measured facts.

## Required tests

- New focused resource-safety/performance tests with no real model calls.
- Existing performance and Ollama unit tests.
- Full backend unittest suite because backend production code changes.
- Python compile for added/changed Python.
- `git diff --check`.

## Benchmark permission

ALLOWED only for one representative expensive run on the smallest existing
persisted benchmark workload needed to separate Story/model and deterministic
cost. No repeated runs, thermal stress, or 40–50-page processing. Read-only
idle and machine samples are allowed. Do not reprocess verified page data.

## Stop condition

After report and independent review, stop at `AWAITING_HUMAN_APPROVAL`. Do not
start Checkpoint 11.2, commit, or push.
