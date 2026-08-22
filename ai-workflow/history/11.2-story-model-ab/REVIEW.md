# Reviewer Report — Checkpoint 11.2

## Verdict

PASS

## Acceptance and experiment control

- Routing diff is minimal: Story Analyzer/repair and Coverage Recovery/repair
  resolve an explicit Story model; default remains `qwen3-vl:8b-instruct`.
- Vision constant and Short Script call routing are unchanged.
- Analyzer prompt hash exactly matches 11.1; deterministic options, source
  revision, page count, validators, grounding, coverage, and safety thresholds
  are unchanged. Coverage template did not change; payload difference is a
  legitimate result of different candidate coverage.
- Candidate benchmark is read-only and before/after authoritative hashes match.
- Exactly one candidate was downloaded and one candidate pipeline run occurred;
  the 8B control, page pipeline, and Short Script were not rerun.

## Correctness and data integrity

The candidate's `event_2` contains an unsupported named-attribution. Existing
grounding correctly moved it into rejected `unsupported_claims`, removed it from
accepted claims/progression, and marked the event not script-ready. Artifacts
now distinguish one detected/rejected claim from zero accepted unsupported
claims. No validator or threshold was weakened.

The candidate verdict `FAIL — QUALITY` is justified even though the safety
invariant held: the model generated an unsupported event and cannot be
recommended as a drop-in replacement. It also achieved only 1.144x total
inference speedup because Coverage Recovery was 1.76x as slow as control.

## Performance and machine safety

- Candidate remained NORMAL throughout; available memory ended around 4.79 GB
  and swap did not grow.
- Observed residency was ~3.86 GB versus control ~6.42 GB.
- Model load is separated (1.142 s) using Ollama response telemetry.
- Ollama was stopped after active calls completed; cooldown returned to NORMAL
  and no second inference was run.
- Heavy concurrency remained one; no process was destructively killed during a
  request.

## Event comparison validity

The exact 11.1 performance/prompt/call summary is reused. Reviewer confirms the
11.1 artifact did not retain returned events, so an exact event payload diff is
impossible without rerunning the 8B model. The implementation correctly avoids
that expensive rerun and labels its event comparison as a same-input/source-
revision persisted 8B proxy. Human-judgment cases are explicit; no synthetic
quality score is presented.

## Validation

- 56 targeted tests passed.
- 231 full backend tests passed.
- Python compile passed.
- Candidate schema/JSON validation passed.
- Workflow validation and `git diff --check` passed.
- No unit test called a real model.

## Scope and Git safety

No prompt optimization, production model switch, OCR/Vision/Dialogue/Script
change, Reader V2/11.3 work, commit, or push occurred. The locally downloaded
candidate is installed but unreferenced by the production default.

No fix task is required. Stop at `AWAITING_HUMAN_APPROVAL`.
