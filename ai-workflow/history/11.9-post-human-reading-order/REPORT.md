# Checkpoint 11.9 Report — Post-Human Reading-Order Analysis

## A. Human GT persisted state
Persisted queue confirms total 3, VERIFIED 3, PENDING 0, SOURCE_UNAVAILABLE 0. Every VERIFIED row has a human sequence and grouping; the agent did not alter them.

## B. Dataset size
Three real manga pages from one project, containing 4, 8 and 10 evaluated text regions respectively (22 total).

## C. Source integrity
All three current source SHA-256 values match the review-bound hashes. No stale/ineligible GT exists. Authoritative project snapshot matched before/after analysis.

## D. Reader prediction
Predicted sequences are preserved separately in the VERIFIED-only artifact with Reader revision `reader-v2.fast-pass.v1` and `MANGA_RTL` policy.

## E. Human ordering
Human sequences are exported verbatim beside, never over, predictions. Pages 1/2 match; Page 3 changed `[1,7,8,2,3,9,4,10,5,11]` to `[1,8,7,2,9,3,4,5,10,11]`.

## F. Human grouping
All pages retain one human `PAGE` group. Group accuracy compares ordered group IDs and membership sets; within-group region order is deliberately scored separately.

## G. Exact page-order accuracy
2/3 pages exact = 66.67%.

## H. Panel/group accuracy
3/3 group structures exact = 100%. This does not validate real panel detection because both prediction and GT use the fallback `PAGE` group.

## I. Region-order accuracy
Exact region sequence on 2/3 pages = 66.67%; 16/22 individual positions remained identical and 6 positions were human-corrected.

## J. Pairwise accuracy
76/79 ordered region pairs correct = 96.20%.

## K. Inversions
3 total, all on Page 3. Pages 1/2 have zero.

## L. Orphan/ambiguous results
Human marked no orphan or ambiguous regions/pages. Orphan assignment accuracy is therefore N/A, not 100%; ambiguous-page count/rate is 0/3 (0%).

## M. Per-page results
Page 1: exact, group exact, 6/6 pairs, 0 inversions/corrections. Page 2: exact, group exact, 28/28 pairs, 0 inversions/corrections. Page 3: not exact, group exact, 42/45 pairs (93.33%), 3 inversions, 6 changed positions.

## N. Error taxonomy
Page 3 is conservatively classified `WRONG_TEXT_ORDER`. No panel-tier, RTL cause, overlap, orphan or detection explanation is inferred without supporting human/geometry labels.

## O. Human correction count
One page required correction; 6 sequence positions changed. No group membership/order correction was observed.

## P. Geometry assessment
The deterministic heuristic is close pairwise but not exact on one of three pages. Evidence supports controlled scaling while retaining a minor-geometry-fix track; it does not support production correctness.

## Q. OCR safety reminder
11.8 false ACCEPT remains 16/19 (84.21%). Reading-order readiness does not make `ACCEPT_CANDIDATE` trusted OCR, justify an EASY/HARD production router or permit weaker uncertainty handling.

## R. Model/OCR call count
VLM 0, Ollama 0, OCR inference 0. Analysis reused persisted prediction and human GT only.

## S. Resource safety
Resource Guard NORMAL before/after. RSS 87,932,928→92,241,920 bytes; available memory 7,014,580,224→7,016,710,144 bytes; swap delta 0; analysis wall 0.0531 s.

## T. Tests
Focused reading-order/persistence/metrics tests pass 7/7. Full backend passes 274/274 in 2.301 s. Python compilation, three-artifact JSON validation, workflow validation and `git diff --check` pass.

## U. Files changed
Added zero-inference post-human analysis script, one focused group-metric test and three 11.9 artifacts; updated active workflow documents. Existing UI/persistence implementation remains unchanged.

## V. Limitations
N=3 from one project, no human panel splits, no orphan/ambiguous examples, and only the MANGA_RTL policy. Exact-page 66.67% has very high sampling uncertainty. Taxonomy identifies mismatch shape, not semantic cause.

## W. Final 11.9 verdict
**B. PASS WITH MINOR GEOMETRY FIXES.** Current geometry is sufficient to justify a controlled larger-scale benchmark, but Page 3 proves it is not exact.

## X. Recommendation for 11.10
Only after human approval, run a controlled larger, diverse human-labeled reading-order benchmark and specifically collect real panel grouping, uneven/overlap, orphan and ambiguity cases. Keep OCR trust as a separate blocked gate. Do not deploy or tune production routing from N=3.
