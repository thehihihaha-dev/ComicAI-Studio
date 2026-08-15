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
