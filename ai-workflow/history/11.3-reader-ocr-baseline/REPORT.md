# Checkpoint 11.3 Report — Reader OCR/Text-Detection Baseline

## A. Current Reader V1 architecture

`Asset` image → `extract_ocr_blocks()` → EasyOCR coupled detection/recognition →
persisted `ocr_text`/`ocr_blocks` → VLM layout regions and reading order →
`build_dialogues()` joins block text → correction/recovery → human review and
`DialogueGroundTruth`. EasyOCR is a lazy singleton initialized with `['vi','en']`
and `gpu=False`; normal full-page input has no explicit preprocessing before
`readtext(detail=1)`. Blocks contain polygon `box`, `text`, and numeric
`confidence`. Bubble regions originate from Vision/VLM associations of OCR block
IDs, not EasyOCR boxes alone.

The full page is sent to VLM for layout. Conditional calls may include missing
block recovery, reading-order analysis, one full-page empty-text fallback, and
dialogue correction using crops/full-page fallback. Consequently calls per page
are data-dependent; the observable minimum layout path is one Vision call. The
11.3 benchmark invoked none of these paths and recorded zero VLM calls.

## B. Benchmark dataset

The immutable manifest reuses the existing persisted pages 6–8: 3 source images,
22 audit-important dialogue/narration regions, SHA-256 content hashes, dimensions,
asset identity, region provenance, and Ground Truth references. It is suitable
only for architecture selection/regression, not general manga accuracy.

## C. Ground Truth sufficiency

There are 21 audit regions with trustworthy persisted OCR-block-union geometry;
the standalone page-7 `Hây` has human GT and a recovered persisted crop but no
geometry in the immutable visual audit, so it is excluded from detection recall.
Only 2 regions have human-verified transcription. Detection precision is N/A
because the audit intentionally does not exhaustively label all text/SFX.

## D. Control configuration

EasyOCR 1.7.2, languages `vi,en`, `gpu=False`, CPU/PyTorch, fresh isolated Reader,
and production-equivalent `readtext(detail=1)`. No persistence endpoint was used.

## E. Candidate inventory

EasyOCR and PaddleOCR/PaddlePaddle were installed. Cached PP-OCRv6 small/medium
detector and recognizer assets existed locally. MangaOCR was absent and, as a
Japanese-specialized recognizer, was not a justified Vietnamese/English candidate.

## F. Candidate selected

Exactly one candidate: PaddleOCR 3.7.0 + PaddlePaddle 3.2.1 with the already cached
`PP-OCRv6_small_det` and `PP-OCRv6_small_rec` assets.

## G. Candidate role: detector/recognizer/combined

Mode A is combined detection + recognition. Mode B directly invokes only the
small recognition model on the same two trusted crops. Detection claims are made
only for Mode A.

## H. Downloads/installations

None. Candidate libraries and approximately 31 MB of selected small-model cache
directories were already present. The first candidate initialization attempt
stopped before inference because Paddle's default medium name conflicted with the
explicit small directory; declaring the matching small model names resolved it.

## I. End-to-end detection result

At documented intersection-over-smaller-region ≥ 0.5, both engines matched all
21 geometry-evaluable important regions: recall 1.0 each. Precision is N/A.

## J. Recognition-only result

On 2 identical crops, EasyOCR: 0 exact, mean CER 0.8333, mean WER 1.0, 0.0244 s.
Paddle: 0 exact, mean CER 0.6667, mean WER 1.0, 0.0459 s. This denominator is too
small for a general recognition conclusion; Paddle emitted a CJK character on one
Vietnamese crop, which is a concrete multilingual reliability warning.

## K. Structural segmentation result

Both produced line-level boxes against bubble/narration-level trusted regions:
19 over-split trusted regions, 0 merged-region errors, and only 2 one-to-one
matches each. No repair or bubble grouping was implemented.

## L. Missing-region analysis

Mode A missed 0/21 geometry-evaluable regions for both engines. The 22nd expected
standalone region remains excluded from detection scoring because its audit has no
trusted geometry; it is included only in transcription through its GT-linked
persisted recovery crop.

## M. Transcription CER/WER

Mode A matched-region aggregation on 2 human GT records: EasyOCR mean CER 0.5938,
WER 0.8571, 0 exact, and 50% empty; Paddle mean CER 0.03125, WER 0.1429, 1 exact,
and 0% empty. These strong candidate numbers are explicitly limited to two GTs.

## N. Confidence usefulness

Calibration is N/A with only two human-GT observations. Mode A nevertheless shows
a useful warning: Paddle's correct `Hây` was medium confidence and its near-correct
long region was high confidence; Mode B's incorrect `Háy` was also high confidence.
Confidence therefore cannot yet be trusted as a final correctness threshold.

## O. Potential easy/hard split

Using simulation-only buckets high ≥0.85, medium 0.50–0.85, low <0.50: EasyOCR
reported 18 potential-easy and 60 potential-hard line regions; Paddle reported 71
potential-easy and 10 potential-hard. This is not a production VLM-savings claim.

## P. Control latency

EasyOCR Mode A page inference total 5.0186 s; wall clock including initialization
and measurement 7.5245 s.

## Q. Candidate latency

Paddle Mode A page inference total 4.2231 s (about 15.8% lower than control), but
wall clock 8.5144 s due to slower initialization.

## R. Initialization/load time

EasyOCR 2.4266 s; Paddle combined candidate 4.0374 s. Recognition-only fresh load:
EasyOCR 2.3670 s and Paddle recognizer 1.8571 s.

## S. Memory/RSS

Peak benchmark-process RSS was 6,830,784,512 bytes for EasyOCR and 1,235,255,296
bytes for Paddle Mode A. These are fresh-process measurements; they do not imply
steady-state backend residency and should be rechecked on a larger dataset.

## T. Swap

Mode A swap delta was 0 bytes for both engines. Mode B swap delta was also 0.

## U. Safety state

Resource Guard remained NORMAL before/after initialization and after inference for
both Mode A runs; no safety rejection occurred.

## V. Apple Silicon runtime

Both measured paths used CPU: EasyOCR via PyTorch CPU and Paddle via Paddle
Inference CPU. No MPS, Metal, CoreML, or MLX migration was attempted.

## W. Cache design recommendation

Future key: `page_content_sha256 + reader_pipeline_version + detector_version +
recognizer_version + preprocessing_version`. Existing source content hashes and
Story source/fingerprint patterns demonstrate stable hash usage, but no Reader
cache or migration was implemented.

## X. Data-integrity verification

The canonical snapshot includes complete Asset OCR/Vision/Dialogue fields, all
Ground Truth fields, Story result/review/approval fields, and Short Script fields.
Before/after hash is identical (`e3936875…5ea3`) in manifest, control, and candidate.

## Y. Tests

Six targeted unit tests pass for normalization, CER/WER, geometry, merge, split,
schema, and immutable-state guards. Python compile, JSON parsing, workflow
validation, and `git diff --check` pass. Production code was unchanged, so the
full backend suite is not required by the active task.

## Z. Files changed

Added benchmark-only `scripts/reader_benchmark.py`,
`scripts/reader_benchmark_lib.py`, targeted tests, four required JSON artifacts,
and 11.3 workflow documents. No production OCR module changed.

## AA. Candidate verdict

CONDITIONAL PASS

Paddle is materially lighter, modestly faster in page inference, and better on the
two available GT records, with no known-region recall/structure regression. The
tiny GT, high-confidence error, Mode B weakness, and non-exhaustive geometry make
automatic replacement unsafe.

## AB. Reader V2 architecture recommendation

D. INSUFFICIENT EVIDENCE — EXPAND BENCHMARK

Keep production EasyOCR unchanged. PaddleOCR small is the sole candidate worth a
focused expanded bake-off; both engines still require a separate deterministic
line-to-bubble structural layer.

## AC. Recommendation for Checkpoint 11.4

Before choosing/replacing OCR, add manually annotated region polygons and more
Vietnamese/English transcription GT, then evaluate deterministic reading order on
that evidence while preserving the 11.3 raw outputs and bbox geometry. Do not use
confidence alone as the routing threshold.
