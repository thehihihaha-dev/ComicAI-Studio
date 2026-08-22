# Checkpoint 11.9 — Human Reading-Order Validation

Build an internal, human-driven reading-order review queue for about 10 existing manga pages. Display source pages with Reader V2 region overlays/predicted numbers; allow explicit panel/group, region, orphan and ambiguity correction; persist human GT separately with source-hash invalidation and project isolation. Provide deterministic post-human metrics, but do not create GT or run evaluation before human completion.

Safety: zero VLM/Ollama/model downloads; no authoritative OCR/Vision/Dialogue/Story mutation; opening UI never verifies; no 11.10, commit or push. Required validation includes persistence/reload, invalidation, isolation, corrections, incomplete/duplicate review, prediction immutability, deterministic metrics, backend/full frontend checks. Stop when UI is ready and report URL plus VERIFIED/PENDING counts.
