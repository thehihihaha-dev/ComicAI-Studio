# Coder Report — Checkpoint 11.1

## A. What changed

Added macOS-oriented resource sampling, NORMAL/WARNING/CRITICAL classification,
a process-local non-blocking heavy inference guard shared by text and vision
Ollama calls, richer performance reports, focused unit tests, and a read-only
machine baseline runner/artifact. No OCR, Story, Ground Truth, or model semantics
changed.

Current runtime inspection found:

- Backend and AI service are FastAPI; production inference logic is in backend.
- OCR is EasyOCR (`vi`, `en`) on CPU, loaded lazily as a backend singleton.
- All Vision and text generation uses Ollama HTTP at `127.0.0.1:11434`.
- Both use `qwen3-vl:8b-instruct`; observed model is 8.8B Q4_K_M, 6.4 GB
  resident, 100% GPU/Metal, context 8192.
- Page OCR loops sequentially inside one background task. Independent FastAPI
  background requests could previously overlap heavy calls; there was no shared
  admission guard. Ollama reported `OLLAMA_NUM_PARALLEL=1`, but backend callers
  could still queue concurrently.
- Ollama call timeout is 180 seconds. Low-level callers have no generic retry.
  Story Analyzer allows two retries (up to three full calls), structural repair
  can add a call, coverage recovery can add calls, and dialogue correction has
  evidence fallbacks. Short Script uses one call then deterministic fallback.

Actual processing path:

- Vision: OCR blocks -> `analyze_comic_page` -> Ollama VLM -> validation,
  missing/empty recovery where needed -> reading order fallback.
- OCR: EasyOCR in backend Python -> normalized blocks/text -> database.
- Dialogue: deterministic building -> VLM correction -> scoring/decision ->
  VLM recovery only for uncertainty -> Ground Truth overlay/review gate.
- Story: persisted authoritative dialogue -> Story Input -> Ollama text call ->
  deterministic grounding/coverage -> optional Ollama coverage recovery.
- Short Script: approved grounded Story -> deterministic content plan -> one
  Ollama style-selection call -> validated output or deterministic fallback.

## B. Files changed

- `AGENTS.md`
- `backend/app/services/resource_safety.py`
- `backend/app/services/performance.py`
- `backend/app/services/ollama_text.py`
- `backend/app/services/ollama_vision.py`
- `backend/tests/test_resource_safety.py`
- `scripts/machine_baseline.py`
- `benchmarks/day11/machine-baseline-11.1.json`
- active `ai-workflow/` artifacts and archived Checkpoint 11.0 artifacts

## C. Architecture/logic

Telemetry captures UTC start/end timestamps, wall time, current/peak backend
process RSS, reclaimable available-memory approximation from `vm_stat`, swap
from `sysctl vm.swapusage`, process CPU time/utilization, model-call counts,
prompt/output character counts already available, and per-sample safety state.
Unavailable metrics remain `null`; temperature and unified GPU memory are not
claimed.

Default thresholds are based on the inspected 16 GiB machine:

- WARNING: available <= 3 GiB or swap >= 2 GiB
- CRITICAL: available <= 1.5 GiB or swap >= 4 GiB

They are configurable with `COMICAI_WARNING_AVAILABLE_GIB`,
`COMICAI_CRITICAL_AVAILABLE_GIB`, `COMICAI_WARNING_SWAP_GIB`, and
`COMICAI_CRITICAL_SWAP_GIB`. Invalid/inverted settings fail fast.

The shared `HeavyInferenceGuard` permits exactly one call in a backend process.
CRITICAL rejects before launch. WARNING permits one slot but rejects any
additional overlapping call. Acquisition is non-blocking; `finally` releases
the slot after success or exception. It never kills a process or cancels an
external request.

## D. Tests

- Focused resource/performance/Ollama tests: 15 passed.
- Full backend suite: 223 passed in 2.185 seconds.
- Python compile: passed.
- `git diff --check`: passed after the final artifact/review update.
- First root-level targeted module invocation failed with `ModuleNotFoundError:
  app`; it exposed and led to correction of the targeted test documentation.
- One compile invocation used backend-prefixed paths while already inside
  `backend/` and failed with file-not-found; corrected invocation passed.

No unit test called Ollama.

## E. Benchmark if allowed

One and only one representative expensive run used the existing persisted
3-page benchmark project. Page OCR/Vision/dialogue stages were not reprocessed
because the existing page benchmark runner overwrites persisted results. This
data-integrity decision is recorded as `not_run_data_integrity_guard` rather
than fabricating latency.

- Idle backend-script RSS: 389.5 MB; available approximation: 6.42 GB; swap:
  174.8 MB; state NORMAL.
- Story Input deterministic build: 0.003218 s, no model call.
- Story wall clock: 138.288 s.
- Model inference: 137.472 s (99.41% of Story wall clock).
- Story Analyzer: 120.199 s; 11,462 prompt chars; 5,048 output chars.
- Coverage recovery: 17.273 s; 4,236 prompt chars; 222 output chars.
- Calls: 2 (one analyzer, one recovery); no retry.
- Peak observed backend-process RSS: 396.1 MB. Ollama is separate and excluded.
- Ollama resident model: 6,417,662,606 bytes, 100% GPU, context 8192.
- Swap: 174.8 MB -> 1,568.0 MB during measured Story (+1,393.2 MB).
- Available approximation: 6.42 GB -> 1.40 GB; overall state CRITICAL.
- After safe Ollama shutdown: memory free recovered to 77%; swap allocation
  remained about 1.87 GB. No second inference was run.
- Persisted asset/Ground Truth state hash was unchanged.

## F. Regressions

No test regression was observed. A heavy request can now be rejected instead of
queued when another call is active or pre-launch state is CRITICAL; this is the
intended safety behavior. Deterministic lightweight work remains unserialized.

## G. Remaining limitations

- Guarding is process-local; multiple backend worker processes need a future
  shared coordinator.
- Backend RSS does not include the separate Ollama runner. Ollama-reported model
  residency is recorded instead.
- `vm_stat` available memory is a documented reclaimable approximation.
- CPU utilization is for the instrumented backend process, not Ollama/system.
- No reliable standard-library temperature or unified GPU-memory measurement.
- Page-stage latency was deliberately not measured because the existing runner
  mutates persisted results.
- The representative Story result still had 10 unresolved regions; this is a
  baseline observation, not changed semantics.

Answers to the checkpoint questions:

1. The current pipeline is slow primarily because the 8.8B multimodal model is
   used for generation; the Story analyzer call alone took 120.199 seconds.
2. Model inference was 137.472/138.288 seconds, or 99.41%; measured deterministic
   Story work plus telemetry was about 0.816 seconds of wall-clock remainder.
3. Yes. A single resident 6.4 GB model lowered available memory to ~1.40 GB and
   increased measured swap by ~1.30 GiB, reaching CRITICAL.
4. Concurrency one is necessary but not sufficient: it prevents overlapping
   heavy jobs, yet one 8.8B/8192-context workload still produced meaningful
   pressure. CRITICAL admission rejection and cooldown remain necessary.
5. The largest likely speedup is a correctness-gated, smaller text-only model
   for Story/Script work instead of the 8.8B VLM. This checkpoint did not switch
   models; Checkpoint 11.2 should compare exactly that one change while holding
   prompts/data/acceptance thresholds fixed.

## H. Git diff summary

Production-adjacent changes are limited to telemetry/admission wrapping around
the two existing Ollama callers plus performance reporting. New tests, runner,
artifact, documentation, and workflow records are additive. No frontend,
database model/migration, OCR logic, reliability threshold, or persisted user
data changed. No commit or push was performed.
