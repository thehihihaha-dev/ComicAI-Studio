# Reviewer Report — Checkpoint 11.1

## Verdict

PASS

## Acceptance criteria

- Telemetry contract contains UTC timestamps, duration, backend RSS/peak RSS,
  available-memory approximation, swap/delta, process CPU, model-call counts,
  and explicit unavailable temperature data.
- NORMAL/WARNING/CRITICAL thresholds are conservative for the inspected 16 GiB
  Mac, environment-configurable, validated, documented, and injection-tested.
- Both Ollama callers share one non-blocking process-local guard. CRITICAL
  rejects before launch; WARNING permits one safe slot but rejects overlap.
- `finally` cleanup is tested after an inference exception; the next acquisition
  succeeds, demonstrating no retained lock/deadlock.
- No OCR, dialogue, Story, Ground Truth, or reliability semantics changed.
- The baseline artifact is machine-readable, secret-free, based on the existing
  3-page persisted dataset, and verifies unchanged persisted state.

## Scope, safety, and data integrity

Diff inspection shows production-adjacent changes only around resource
telemetry and admission at existing Ollama boundaries. No frontend, schema,
migration, model choice, threshold relaxation, commit, or push occurred. The
single expensive run complied with task permission and was not repeated.
Ollama was stopped only after both active requests completed; other services
were not killed.

The decision not to measure page OCR/Vision/dialogue latency is justified:
the existing runner reprocesses and overwrites asset results. Reporting those
fields as unavailable protects persisted approved data and is more trustworthy
than an unsafe or incomparable measurement.

## Tests and benchmark validity

- Focused tests: 15 passed.
- Full backend suite: 223 passed.
- Python compilation: passed.
- `git diff --check`: passed.
- Unit tests made no Ollama/model calls.
- Benchmark used deterministic generation settings and exactly one Story run.
- Model time and deterministic time are separately recorded. Backend RSS is
  correctly labeled as excluding Ollama; Ollama resident size is separately
  recorded.

## Reviewer observations

The observed CRITICAL state is not hidden: one 8.8B VLM caused about 1.30 GiB
swap growth and reduced reclaimable available memory to about 1.40 GB. Thus
concurrency one is necessary but not sufficient, which the report states. The
process-local limitation is also disclosed; it must be addressed before using
multiple backend workers.

No fix task is required. Stop at `AWAITING_HUMAN_APPROVAL`.
