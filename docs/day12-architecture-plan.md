# ComicAI Day 12 architecture plan

Status: **PLANNING ONLY**. Day 11 is closed. This document does not open or implement a Day 12 checkpoint.

## Evidence and primary objective

Day 11 established a scalable, deterministic and failure-safe Reader V2 foundation, but OCR remains 8/71 exact with 14.85% CER and 38.88% WER. All 858 replayed regions require repair. This is safe but too conservative. High OCR confidence cannot be treated as correctness: frozen R2 produced a known false-safe and two Human UNREADABLE safe risks, while global PP-OCRv6 did not justify its cost.

Day 12's primary objective is therefore to transform an immutable **OBSERVED TEXT** record into exactly one qualified outcome:

- **VALIDATED TEXT**, supported by explicit evidence and a recorded validation decision; or
- **UNRESOLVED TEXT**, retained without guessing and routed away from authoritative Story facts.

Day 12 must improve useful coverage without increasing unsafe validation. It should use cheap Reader output first and invoke expensive repair selectively, under the existing Resource Guard.

## Proposed architecture

```text
ReaderRegion (immutable observation)
        │
        ▼
Repair Boundary ───────────────► UNRESOLVED
        │                         reason + evidence gaps
        ▼
VALIDATED
text + method + evidence + validation result
        │
        ▼
Page Understanding
ordered panels/regions + supported text roles + ambiguity
        │
        ▼
Scene / Chunk Construction
        │
        ▼
Grounded Carry-over State
        │
        ▼
Story Evidence Boundary
source references + validated text + unresolved markers + provenance
```

### Repair record

A future repair record should contain:

- immutable original OCR observation and source-region reference;
- repaired candidate, if one exists;
- repair method and exact configuration/version;
- image/text/context evidence used;
- validation result: `VALIDATED` or `UNRESOLVED`;
- reliability state and reasons;
- provenance, cache fingerprint and deterministic output hash;
- explicit indication of whether Human evidence participated.

The original observation is never overwritten. Repair methods—deterministic cleanup, punctuation normalization, justified crop reconstruction, selective OCR retry, selective VLM repair, context assistance or Human fallback—remain hypotheses until benchmarked separately.

### Page understanding

Page Understanding consumes only qualified Reader/repair records. It may represent ordered panels and text regions, supported speaker/dialogue relationships, narration, SFX, decorative/non-story text, ambiguity and unresolved regions. It must not infer semantic facts from unresolved OCR.

### Scene, chunk and carry-over state

Candidate chunk signals include page/panel transitions, dialogue continuity, supported location or character continuity and narration transitions. Carry-over may track active characters, unresolved speakers, ongoing dialogue, current location/action and unresolved references. Every field needs source evidence, status and provenance; speculative state cannot silently become fact.

### Story boundary

Story receives ordered evidence with source references, validated text, unresolved markers and provenance. It does not receive raw unqualified OCR as an authoritative claim. Unresolved evidence may constrain or block a story claim rather than being filled creatively.

## Proposed checkpoint sequence

### 12.0 — Repair boundary contract and replay harness

- Objective: define immutable observation, repair attempt, `VALIDATED`/`UNRESOLVED`, provenance and cache contracts.
- Scope: schemas, offline adapters, deterministic replay, GT isolation and Resource Guard; no repair algorithm.
- Benchmark: replay the Day 11 71 VERIFIED + 10 UNREADABLE set and 40-page scale manifest through a no-op boundary.
- Acceptance gate: observation bytes/hashes preserved, unsafe authoritative promotions zero, deterministic hashes/cache invalidation proven, production/Story unchanged.
- Human testing: none.

### 12.1 — Deterministic low-risk repair baseline

- Objective: measure whether explicitly reversible normalization can validate any text safely.
- Scope: predeclared cleanup/normalization candidates only; original text retained; no model calls or post-GT tuning.
- Benchmark: existing 71 VERIFIED correctness set, with the 10 UNREADABLE samples reported separately and known false-safe cases pinned.
- Acceptance gate: report repair precision, coverage, regressions and unsafe validations against the frozen no-op control. Any selected rule remains benchmark-fitted until out-of-sample validation.
- Human testing: none unless an existing label is internally inconsistent; never synthesize GT.

### 12.2 — Selective repair routing experiment

- Objective: identify which unresolved regions justify a more expensive attempt without trusting OCR confidence.
- Scope: predeclare interpretable routing features from structure, disagreement and repair history; no global stronger OCR.
- Benchmark: Day 11 GT plus scale-cost simulation; compare candidate routing against repair-everything and repair-nothing controls.
- Acceptance gate: empirical trade-off among unsafe validation, reachable repair coverage, calls, latency and memory. Thresholds are benchmark-derived and explicitly labeled.
- Human testing: none.

### 12.3 — Controlled expensive repair benchmark

- Objective: test at most one justified expensive repair method on the frozen routed subset.
- Scope: selective calls only, sequential Resource Guard, immutable provenance, no Story integration and no silent fallback.
- Benchmark: routed VERIFIED samples; UNREADABLE samples are safety-only. Compare with original EasyOCR and deterministic repair baselines.
- Acceptance gate: demonstrate incremental correct repairs without unsafe validations or unacceptable machine cost; otherwise retain `UNRESOLVED` and reject the method.
- Human testing: expected only if existing GT does not cover the method's target failure mode; request a small, predeclared sample with a specific decision purpose.

### 12.4 — Page Understanding evidence contract

- Objective: classify qualified page evidence without inventing semantics.
- Scope: ordered region roles, supported speaker linkage, narration/SFX/decorative/ambiguous/unresolved representation and grounding references.
- Benchmark: reuse the ten Human Reading Order pages and validated text subset; prepare blinded evaluation fixtures before candidate output is inspected.
- Acceptance gate: provenance completeness, grounded-role accuracy, unresolved preservation and zero unsupported semantic facts.
- Human testing: likely required for a small page-level role/linkage set because Day 11 GT contains order/transcription but not authoritative semantic roles. Define pages and fields before collection.

### 12.5 — Scene/chunk and grounded carry-over experiment

- Objective: construct coherent multi-page chunks and explicit cross-page state from Page Understanding evidence.
- Scope: offline hypotheses for boundaries and carry-over; uncertainty and evidence references mandatory; no production Story switch.
- Benchmark: a small contiguous real-page sequence with Human boundary/state labels collected only after the representation is frozen.
- Acceptance gate: compare boundary consistency, evidence coverage, unsupported state transitions and deterministic replay against simple page-boundary control.
- Human testing: expected; annotate only chunk boundaries and a finite carry-over field set on a predeclared contiguous sequence.

### 12.6 — Final offline Reader-to-Story evidence integration

- Objective: prove the complete safe boundary from Reader observation through repair, page understanding and chunks to grounded Story evidence.
- Scope: offline integration and cache replay only; unresolved input must remain unresolved; production Story semantics unchanged.
- Benchmark: scale/performance replay plus correctness only on the corresponding Human-GT subsets from earlier checkpoints.
- Acceptance gate: no GT leakage, no unsafe authoritative promotion, no unsupported Story event, deterministic cache/output hashes, acceptable empirical latency/memory versus component baselines and independent Reviewer PASS.
- Human testing: no new campaign unless a documented coverage gap prevents the final decision.

## Human testing policy

Reuse Day 11 transcription, UNREADABLE and Reading Order GT wherever their semantics match the question. New Human work is expected only for semantic page roles/linkage in 12.4 and chunk/carry-over labels in 12.5. Before either gate, the task must state exact fields, predeclared sample size, source selection, annotation instructions and the decision the labels unlock. Sample sizes must follow a coverage audit; they are not chosen merely to reach a round number.

## Day 12 exit criteria

Day 12 closes only on measured evidence. Final reporting must include:

- repair precision and correct-repair coverage by method;
- unresolved count/rate and reasons;
- unsafe validation count/rate, including pinned false-safe and UNREADABLE cases;
- page-understanding grounding and unsupported-fact counts;
- scene/chunk consistency and unsupported carry-over transitions;
- provenance completeness and original-observation preservation;
- selective expensive-call count and avoided-call rate;
- cold/incremental and cached latency, peak RSS, available memory, swap delta and Resource Guard state;
- deterministic fingerprints/output hashes and cache invalidation;
- zero GT leakage and a clear production-integrity statement.

No arbitrary numeric pass threshold is declared in this plan. Each checkpoint must freeze its protocol before evaluation, compare against an evidence-backed control and label any selected threshold `BENCHMARK_FITTED` until independent out-of-sample evidence supports calibration.
