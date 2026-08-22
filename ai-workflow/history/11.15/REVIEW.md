# Checkpoint 11.15 — Independent Reviewer

## Verdict: PASS

Independent recomputation confirms crop fairness, 71 VERIFIED/10 UNREADABLE handling, primary/residual/HARD/STRUCTURAL metrics, disagreement, false-safe replay, non-deployable oracle, performance and resource math. The verdict `C. CANDIDATE DOES NOT JUSTIFY COST` is supported.

After one narrowly scoped reproducibility correction, manifest and candidate artifacts persist the actual PaddleX `create_model` recognizer runtime 3.7.2, PaddleOCR 3.7.0, PaddlePaddle 3.2.1, exact 76,863,990-byte cache size, and matching SHA-256 values for all three inference/config files. The canonical protocol hash independently recomputes to `69325b808e0640d5b482f197a6e2048c78dab45ffca43f4e3737b7ba5cb9ca00` in both artifacts.

Focused tests pass 19/19 and full backend tests pass 318/318; compile, six JSON files, workflow and diff checks pass. The fix did not rerun inference or change metrics, GT, R2, Reading Order, production or authoritative state. VLM/Ollama calls are zero. No commit or push occurred.
