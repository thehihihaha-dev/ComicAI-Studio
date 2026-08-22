# Database migrations

Run migrations in filename order against the configured PostgreSQL database.
Migration `000` can bootstrap an empty database and does not replace existing
tables.

Example:

```sh
psql "$DATABASE_URL" -f migrations/001_day8_ground_truth_integrity.sql
```

Back up production data before applying a migration. Migration `001` keeps the
newest Ground Truth row for each asset/region pair, adds uniqueness, and makes
Ground Truth rows follow their parent asset on deletion.

Migration `002` adds one persisted Story Analysis result per project. Its
deterministic source revision is used to report current or stale results.

Migration `003` adds human Story Review state alongside the preserved AI Story
result. Existing Story Analysis rows and JSON results are not modified.

Migration `004` adds explicit Final Story approval metadata. Approval validity
is checked against the current source revision and deterministic Story fingerprint.

Migration `005` persists one Short Script per project, including manual segment
edits, approved Story linkage, and deterministic Script approval metadata.

Migration `006` adds project-scoped OCR benchmark review state and immutable crop
provenance. Authoritative text remains in the existing Ground Truth table.

Migration `007` adds source-revision-bound human reading-order benchmark reviews.
Human sequences remain separate from immutable Reader V2 predictions.
8. `008_reader_correctness_reviews.sql` — combined 11.11 Reading Order and blinded OCR Human GT queue.
9. `009_reader_logical_reviews.sql` — versioned logical-region Reading Order GT, isolated from incompatible fragment-level GT.
10. `010_reader_click_order_gt.sql` — click-to-order logical Human GT and independent logical transcription fields.
11. `011_reader_router_validation_reviews.sql` — blinded, out-of-sample 11.13 OCR validation annotations isolated from production and prior Human GT.
