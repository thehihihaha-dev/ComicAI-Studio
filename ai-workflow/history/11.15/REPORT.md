# Checkpoint 11.15 — Controlled Residual OCR Recognition Benchmark

## Candidate and fairness

The single candidate is the already-local `PP-OCRv6_medium_rec` recognizer (76,863,990 bytes cached), executed through PaddleX `create_model` 3.7.2 with PaddleOCR 3.7.0 and PaddlePaddle 3.2.1 on CPU. Exact hashes for the three local inference/config files are persisted. No package/model download occurred. Paddle detection was disabled: Mode C recognizes the exact existing logical bbox; Mode D recognizes the frozen 11.14 adaptive bbox. Persisted EasyOCR 11.13 is Control A and frozen adaptive EasyOCR 11.14 is Control B. Human text enters only post-inference scoring.

Dataset is the frozen 81-region replay: 71 VERIFIED correctness labels and 10 intentional UNREADABLE diagnostics. Human GT, replay/source hashes and authoritative state remain unchanged.

## Primary results (N=71)

- Control A: exact 8/71 (11.27%), CER 14.85%, WER 38.88%.
- Control B: exact 8/71 (11.27%), CER 14.55%, WER 39.92%.
- Paddle exact bbox (C): exact 6/71 (8.45%), CER 92.80%, WER 98.34%; 5 improved, 7 unchanged, 59 regressed; 3 wrong→correct and 5 correct→wrong.
- Paddle adaptive bbox (D, selected candidate mode): exact 6/71 (8.45%), CER 92.65%, WER 98.34%; 6 improved, 7 unchanged, 58 regressed; 3 wrong→correct and 5 correct→wrong.

The recognizer-only line model is not suitable for these frequently multi-line logical crops. Enabling a detector would redefine the benchmark region and was intentionally not attempted.

## Residual and routing-state analysis

EasyOCR has 63 wrong samples. Mode D repairs 3 exactly: residual repair rate 3/63 = 4.76%. Six improve, four remain unchanged and 53 regress. Residual CER increases from 15.39% to 94.36%, a negative reduction of 78.97 percentage points.

HARD (N=21): exact remains 6, candidate repairs 3 but also offsets those gains; 5 improve, 6 unchanged, 10 regress. CER increases from 11.49% to 68.97%.

STRUCTURAL_REVIEW (N=49): control exact 2 versus candidate exact 0; candidate repairs zero, improves 1 and regresses 48. CER rises from 15.32% to 96.28%. This confirms that a single-line recognizer on ambiguous multi-line/structural crops does not solve the structural category.

## Error, disagreement and oracle analysis

The known high-confidence false-safe remains unrepaired: EasyOCR `\"STAR`, Paddle `\"STAR`, Human `STAR`. Candidate error observations are dominated by missing text (63) and multi-fragment reconstruction context (49), with punctuation/quote and extra-text errors also present.

Normalized EasyOCR/Paddle outputs agree on 6 samples and differ on 65. Among disagreements: EasyOCR correct/Paddle wrong 5; EasyOCR wrong/Paddle correct 3; both wrong 57.

**ORACLE UPPER BOUND — NOT PRODUCTION ACHIEVABLE:** either engine correct yields 11/71 exact (15.49%). This is descriptive complementarity only and is not a deployable router.

All ten UNREADABLE samples remain unscored and unmodified. Candidate produces output on 10/10 for both crop modes and disagrees with EasyOCR on 9/10; confidence and structural flags are preserved in the diagnostic artifact. No correctness claim is made.

## Performance and safety

Cold initialization is 1.104 s. Selected-mode warm mean is 39.44 ms/region; 81-region selected-mode time is 3.195 s. Both modes total 162 candidate calls and 7.710 s warm wall. Linear warm estimates per 100 regions are 0.394 s at 10%, 0.986 s at 25%, 1.972 s at 50% and 3.944 s at 100%, excluding cold initialization/concurrency effects.

Resource Guard remained NORMAL. Peak RSS was about 1.119 GB; ending available memory about 6.831 GB; swap delta zero. Execution was sequential. VLM/Ollama calls were zero. Production OCR, frozen R2 and Reading Order were unchanged.

## Decision

**C. CANDIDATE DOES NOT JUSTIFY COST.** Although runtime is manageable and three residuals are complementary repairs, the candidate reduces total exact accuracy, causes five correct→wrong regressions and catastrophically worsens CER/WER on logical multi-line crops. Do not add PP-OCRv6 medium recognizer-only to Reader V2.

Recommended 11.16 action: move to the already-isolated shared tier/row Reading Order geometry experiment. Do not continue OCR model shopping or modify OCR routing inside that checkpoint.

Focused tests pass 19/19 and full backend tests pass 318/318. Python compile, six JSON artifacts, workflow validation and diff hygiene are included in final handoff. No commit or push was performed.
