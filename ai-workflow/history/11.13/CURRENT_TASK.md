# Checkpoint 11.13 — Frozen OCR Router Out-of-Sample Validation

Freeze 11.12 candidate R2 exactly (`confidence >= 0.98`, single fragment, no crop-boundary warning) and validate it only against new page-grouped Human OCR Ground Truth from Gate D pages excluded from the 11.11/11.12 calibration set.

Before Human GT, deterministically select unseen pages, prove source-hash separation, expose one blinded logical crop at a time, persist Human-only transcription/unreadable state separately, and stop at `HUMAN TESTING REQUIRED`. Do not expose OCR prediction, confidence or R2 status before annotation. Do not run OCR/VLM/Ollama, tune R2, modify Reading Order/production/authoritative GT, start 11.14, commit or push.
