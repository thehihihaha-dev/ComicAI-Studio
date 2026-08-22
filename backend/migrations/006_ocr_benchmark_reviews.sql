BEGIN;

CREATE TABLE IF NOT EXISTS ocr_benchmark_reviews (
    sample_id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    asset_id VARCHAR NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    region_id INTEGER NOT NULL,
    page_order INTEGER NOT NULL,
    bbox JSON,
    text_role VARCHAR NOT NULL DEFAULT 'unknown',
    source_image_hash VARCHAR NOT NULL,
    crop_hash VARCHAR,
    state VARCHAR NOT NULL DEFAULT 'PENDING',
    provenance VARCHAR NOT NULL DEFAULT 'human',
    source_compatible BOOLEAN NOT NULL DEFAULT TRUE,
    revision INTEGER NOT NULL DEFAULT 0,
    benchmark_cache_revision INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    note TEXT,
    CONSTRAINT uq_ocr_benchmark_asset_region UNIQUE (asset_id, region_id),
    CONSTRAINT ck_ocr_benchmark_state CHECK (state IN ('PENDING','VERIFIED','SKIPPED','UNREADABLE','SOURCE_UNAVAILABLE')),
    CONSTRAINT ck_ocr_benchmark_provenance CHECK (provenance = 'human')
);

CREATE INDEX IF NOT EXISTS ix_ocr_benchmark_reviews_project_id ON ocr_benchmark_reviews(project_id);
CREATE INDEX IF NOT EXISTS ix_ocr_benchmark_reviews_asset_id ON ocr_benchmark_reviews(asset_id);

COMMIT;
