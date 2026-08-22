# Checkpoint 11.11 — Reader V2 Correctness & Uncertainty Validation

Reuse the exact cached 40-page Gate D outputs and construct an approximately ten-page deterministic stratified Human GT queue covering flagged/review, unusual geometry, low-confidence OCR, high-confidence/easy, at least two ordinary random pages, and the known 11.9 Page 3 regression. Record selection reasons and preserve source hashes.

Implement a human-only UI that validates Reading Order and OCR independently. Show predicted layout/order/grouping, but never prefill OCR transcription and keep OCR predictions hidden until the corresponding human transcription is saved. Support ORDERED/ORPHAN/AMBIGUOUS/EXCLUDED and OCR VERIFIED/UNREADABLE. Do not use AI to create GT.

Stop at HUMAN TESTING REQUIRED once the queue/UI is ready. Do not perform post-human metrics, call VLM/Ollama, change production OCR/validators/thresholds, begin 11.12, commit, or push.
