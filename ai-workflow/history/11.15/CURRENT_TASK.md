# Checkpoint 11.15 — Controlled Residual OCR Recognition Benchmark

Benchmark one already-local stronger recognizer, PP-OCRv6 medium recognition, on the frozen 11.13 logical crops and optional frozen 11.14 adaptive crops. Compare against persisted EasyOCR control and 11.14 structural comparator using 71 VERIFIED labels; keep 10 UNREADABLE diagnostic-only.

Use recognizer-only Paddle inference with no detector, semantic correction or GT-derived construction. Measure residual HARD/STRUCTURAL repairs, regressions, disagreement, non-deployable oracle and resource cost. Preserve Human GT, R2, Reading Order and production state. Zero VLM/Ollama; no 11.16, commit or push.
