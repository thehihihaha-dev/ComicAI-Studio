BEGIN;

CREATE TABLE IF NOT EXISTS reading_order_benchmark_reviews (
    review_id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    asset_id VARCHAR NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    page_order INTEGER NOT NULL,
    source_image_hash VARCHAR NOT NULL,
    reader_revision VARCHAR NOT NULL,
    reading_policy VARCHAR NOT NULL DEFAULT 'MANGA_RTL',
    predicted_groups JSON NOT NULL,
    predicted_sequence JSON NOT NULL,
    predicted_ambiguity JSON NOT NULL,
    human_groups JSON,
    human_sequence JSON,
    human_dispositions JSON,
    state VARCHAR NOT NULL DEFAULT 'PENDING',
    source_compatible BOOLEAN NOT NULL DEFAULT TRUE,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    CONSTRAINT uq_reading_order_benchmark_asset UNIQUE (asset_id),
    CONSTRAINT ck_reading_order_benchmark_state CHECK (state IN ('PENDING','VERIFIED','SOURCE_UNAVAILABLE'))
);

CREATE INDEX IF NOT EXISTS ix_reading_order_benchmark_project_id ON reading_order_benchmark_reviews(project_id);
CREATE INDEX IF NOT EXISTS ix_reading_order_benchmark_asset_id ON reading_order_benchmark_reviews(asset_id);

COMMIT;
