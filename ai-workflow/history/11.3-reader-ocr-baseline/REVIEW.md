# Checkpoint 11.3 Independent Review

## Verdict

PASS

## Scope and architecture

The active checkpoint adds only benchmark scripts, pure metric helpers, tests,
artifacts, and workflow documentation. `backend/app/services/ocr_service.py` and
all production OCR/Vision/Dialogue/Story/Script paths are unchanged. The runner
queries the database without `add`, `flush`, `commit`, or endpoint invocation.
No reading-order implementation, detector repair, training, cache migration,
production model switch, Ollama call, commit, push, or 11.4 work is present.

The worktree also contains earlier approved 11.0–11.2 changes; review separated
those pre-existing cumulative changes from the new 11.3 untracked files.

## Benchmark validity

- Control constructs EasyOCR with the production `['vi','en']`, `gpu=False`, and
  `readtext(detail=1)` configuration in an isolated process.
- Exactly one candidate was evaluated: cached PP-OCRv6 small detector/recognizer.
  Artifacts record no download or installation and zero VLM calls.
- Mode A and Mode B are labeled separately. Recognition-only output is never
  credited with detection recall.
- Normalization is representational only (NFC and whitespace); case is preserved.
- Geometry uses a documented overlap metric/threshold and records bipartite
  edges, one-to-one matches, merges, splits, misses, and orphans. Large merged
  boxes cannot be counted as multiple one-to-one matches.
- The report does not fabricate precision: it is N/A because the oracle omits
  non-important text/SFX. Detection uses 21 regions; transcription uses exactly
  the 2 human GT records. The recovered `Hây` crop is explicitly excluded from
  detection geometry but retained for GT-linked transcription.
- Candidate verdict is the permitted exact `CONDITIONAL PASS`; recommendation is
  exact option D. The limitations support both decisions.

## Correctness and evidence

Raw engine boxes/text/confidence are retained in per-engine artifacts. Recomputed
metrics are derived from saved raw output, not extra page inference. The report's
latency, initialization, CER/WER, structure, RSS, swap, confidence, and safety
numbers agree with the JSON evidence. It correctly avoids generalization from
three pages and treats confidence calibration as N/A with only two observations.

The canonical database snapshot covers complete Asset OCR/Vision/Dialogue rows,
Ground Truth, Story/review/approval, and Short Script. Before/after hashes match in
manifest and both engine artifacts. The scripts do not expose database URLs or
other secrets; project identity in summary fields is hashed.

## Machine safety and regressions

Both sequential Mode A runs and both crop-only Mode B runs remained NORMAL with
zero swap delta. No concurrent candidate run occurred. The failed first Paddle
initialization performed no inference/download and is disclosed. Production code
was unchanged, and the full existing backend suite passed.

## Verification rerun/inspected

- `python -m unittest discover`: 237 tests passed.
- Targeted Reader tests: 6 passed within the suite.
- Python compilation: passed.
- Four required Reader JSON artifacts parsed successfully.
- Workflow validation: passed at IMPLEMENTED.
- `git diff --check`: passed.
- Manual artifact/schema/data-integrity and source mutation audit: passed.

## Required fixes

None.
