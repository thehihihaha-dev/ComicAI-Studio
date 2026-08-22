# Checkpoint 11.2 — Small Text Model A/B Benchmark

## Objective

Compare exactly one smaller text-only Story model with the unchanged 11.1
`qwen3-vl:8b-instruct` control using identical Story/Coverage prompts, inputs,
validators, deterministic options, and resource policy.

## Background

The 11.1 3-page Story run spent 137.472172 of 138.287860 seconds in model
inference and reached CRITICAL memory pressure. No text-only model is installed;
local inventory contains only Qwen VL models. The conservative candidate is
`qwen3:4b-instruct` (official Ollama tag: text-only, ~2.5 GB, 256K context).

## Files/modules likely involved

- `backend/app/services/model_runtime.py`
- Story Analyzer and Coverage Recovery call sites only
- routing/schema unit tests
- a read-only Story candidate benchmark/comparison helper
- `benchmarks/day11/` artifacts

## Scope

- Add minimal Story-only model resolution with unchanged production fallback.
- Keep Vision and Short Script defaults unchanged.
- Pull and run one candidate once after safe cooldown/admission checks.
- Reuse the exact persisted 3-page snapshot and 11.1 latency control.
- Produce candidate and comparison artifacts with correctness/resource evidence.

## Out of scope

Prompt/schema/validator changes, OCR, Vision, Dialogue, Short Script, Reader V2,
model cascade, production model switch, cloud inference, large chapter work,
commit, push, or Checkpoint 11.3.

## Safety constraints

- Use the 11.1 guard and concurrency one.
- Do not keep the 8B control resident with the candidate.
- If CRITICAL is observed before launch, reject; if reached during the allowed
  run, finish safely and stop further candidates.
- Never overwrite authoritative project, Ground Truth, or persisted Story data.
- Do not weaken correctness or grounding checks.

## Acceptance criteria

1. Story model resolves from an explicit validated override/environment value,
   otherwise the production 8B default; Vision remains separately fixed.
2. Candidate receives the same prompt hashes/options/input fingerprint as 11.1.
3. Candidate artifact records structure, source validity, grounding, coverage,
   language, timings, load/residency, memory/swap, and unchanged data hash.
4. Comparison artifact computes speedups and compact source-based event diff.
5. Accepted unsupported claims/events remain zero or candidate fails quality.
6. Production Story default is not switched.

## Required tests

- Story config resolution/separation/fallback/invalid configuration.
- Benchmark artifact schema and deterministic event comparison.
- Targeted tests, full backend suite, Python compile, workflow validation, and
  `git diff --check`; unit tests must not call a real model.

## Benchmark permission

ALLOWED: download only `qwen3:4b-instruct` (~2.5 GB) and perform one read-only,
deterministic candidate Story/Coverage run. Reuse 11.1 control; do not rerun it.
No second candidate after CRITICAL or merely to improve statistics.

## Stop condition

Write report/review and stop at `AWAITING_HUMAN_APPROVAL`. Do not switch the
production default or begin Checkpoint 11.3.
