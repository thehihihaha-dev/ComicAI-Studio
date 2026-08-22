# Coder Report — Checkpoint 11.2

## A. What changed

Added minimal Story-only Ollama model resolution, leaving the production fallback
and Vision model at `qwen3-vl:8b-instruct`. Added a read-only candidate benchmark,
artifact validation/source-based event diff, tests, and three comparison
artifacts. Pulled and tested only `qwen3:4b-instruct`; production was not switched.

## B. Files changed

- `backend/app/services/model_runtime.py`
- `backend/app/services/story_analyzer.py`
- `backend/app/services/story_reliability.py`
- `backend/app/services/ollama_text.py` (Ollama load/eval telemetry only)
- `backend/app/services/story_model_benchmark.py`
- `backend/tests/test_story_model_routing.py`
- `backend/tests/test_story_model_benchmark.py`
- `scripts/story_model_benchmark.py`
- `benchmarks/day11/story-model-control-11.1.json`
- `benchmarks/day11/story-model-candidate-11.2-qwen3-4b-instruct.json`
- `benchmarks/day11/story-model-comparison-11.2.json`
- `AGENTS.md` and active/history workflow artifacts

## C. Architecture/logic

`resolve_story_model()` accepts a validated context override or `STORY_MODEL`,
then falls back to `qwen3-vl:8b-instruct`. Story Analyzer and Coverage Recovery
pass that value explicitly to the existing Ollama text caller. Vision remains
independently fixed; Short Script routing was not changed. Invalid/remote/blank
model references fail before a call. Benchmark override is context-local and
automatically restored.

Candidate selection: local inventory contained only VL models. The single new
candidate was official Ollama `qwen3:4b-instruct`: text-only, 4.0B Q4_K_M,
download ~2.5 GB, observed resident 3,856,589,127 bytes, context 8192 at runtime.
It was selected for instruction/JSON behavior, Qwen multilingual lineage, ample
declared context, and materially smaller residency. No second model was pulled.

Experiment equality:

- same current source revision and persisted 3-page project
- exact analyzer prompt hash matched 11.1:
  `01081a941bbae94afc1b0a8754b1d6713e987e216973515887694975d8981195`
- same deterministic options and `num_ctx=8192`
- no prompt, schema, grounding, coverage, validator, or threshold changes
- Coverage prompt template unchanged; payload hash differed because candidate
  output produced a different uncovered-region set
- authoritative state hash unchanged

## D. Tests

- Targeted routing/benchmark/Story/Ollama tests: 56 passed.
- Full backend suite: 231 passed in 2.335 seconds.
- Python compile: passed.
- Candidate artifact schema and all JSON artifacts: passed.
- Workflow validation and `git diff --check`: passed.
- Unit tests made no real model calls.

An earlier read-only DB inspection failed inside the sandbox with an expected
network permission error; the authorized read-only rerun succeeded. No data was
written by either inspection.

## E. Benchmark if allowed

Exactly one deterministic candidate Story/Coverage run was performed. Control
8B inference was not rerun. OCR, Vision, Dialogue, and Short Script did not run.

Performance:

- Story Analyzer: 89.853922 s inference versus control 120.199019 s;
  1.3377x, saving 30.345097 s.
- Coverage Recovery: 30.314860 s versus control 17.273153 s;
  0.5698x, 13.041707 s slower.
- Total inference: 120.168782 s versus 137.472172 s;
  1.1440x, saving 17.303390 s.
- Total Story wall: 121.202181 s versus 138.287860 s;
  1.1410x, saving 17.085679 s.
- Calls: 2, one Analyzer and one Coverage Recovery, no retry.
- First-call model load: 1.142130 s; Ollama first-call total: 89.808206 s.

Resources:

- preflight NORMAL; no model resident
- available approximation: 8.002 GB -> 4.792 GB
- backend RSS start ~394.3 MB; peak observed ~397.8 MB
- swap: 1,749,947,514 -> 1,741,558,906 bytes (delta -8 MiB)
- observed state remained NORMAL
- candidate residency ~3.86 GB, 100% GPU, context 8192
- after safe unload: 80% system free, available approximation ~7.78 GB,
  swap unchanged around 1.74 GB, NORMAL
- no second inference was run

Correctness:

- output structurally valid; source references valid
- 8 events, 5 main_story, 10 grounded claims, 7 script-ready
- model generated one unsupported named-attribution in `event_2`; grounding
  rejected it and marked the event unsupported/not script-ready
- detected/rejected unsupported claims: 1
- accepted unsupported claims: 0 (hard invariant preserved)
- unsupported events: 1
- eligible/important/covered/non-story/unresolved: 22/22/11/3/8
- coverage score: 0.6364
- language: mixed language, predominantly English with Vietnamese quoted text

Event-level diff uses deterministic source overlap and exact normalized claim
text: 2 `less complete`, 5 `more specific but supported`, 1 `unsupported`;
seven comparisons require human judgment. Exact 11.1 latency/prompt/call and
unresolved-region control is retained, but 11.1 did not persist its returned
event payload. Therefore event-level comparison is explicitly against the
same-source-revision persisted 8B result, labeled as a proxy rather than falsely
claimed as the exact 11.1 event output.

Candidate verdict: `FAIL — QUALITY` because it produced an unsupported event,
even though grounding prevented acceptance. It also delivered only modest total
speedup because Coverage Recovery became materially slower.

## F. Regressions

No test or data regression observed. Production fallback is unchanged, no
production environment value was set, and no persisted Story/review/Ground
Truth was overwritten. Routing changes only which explicitly selected model
Story calls use; Vision/Short Script behavior remains unchanged.

## G. Remaining limitations

- Exact 11.1 event payload was not retained, so event-level control is a clearly
  labeled same-input persisted proxy.
- One run is diagnostic, not a variance estimate.
- Language is mostly English because prompts were intentionally unchanged.
- Candidate improves Analyzer time but worsens Coverage Recovery.
- Model download remains installed locally; production does not reference it.
- Process-local resource guard limitation from 11.1 remains.

Recommendation: do not switch production to `qwen3:4b-instruct`. For 11.3,
retain the 8B production default and investigate the existing unsupported-event
and Coverage Recovery behavior without weakening validators. Any prompt work
must be a separately approved controlled checkpoint; do not begin it now.

## H. Git diff summary

Changes are limited to model routing, telemetry fields, benchmark analysis,
tests, artifacts, documentation, and workflow history. No OCR/Vision/Dialogue/
Short Script prompt or behavior, schema/migration, Ground Truth, production
model setting, commit, or push occurred.
