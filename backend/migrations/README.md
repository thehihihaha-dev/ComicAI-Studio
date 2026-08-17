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
