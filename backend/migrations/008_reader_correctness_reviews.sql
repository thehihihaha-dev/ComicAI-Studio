BEGIN;

CREATE TABLE IF NOT EXISTS reader_correctness_reviews (
    review_id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    asset_id VARCHAR NOT NULL UNIQUE REFERENCES assets(id) ON DELETE CASCADE,
    page_order INTEGER NOT NULL,
    source_image_hash VARCHAR NOT NULL,
    selection_reasons JSON NOT NULL,
    predicted_regions JSON NOT NULL,
    predicted_sequence JSON NOT NULL,
    predicted_groups JSON NOT NULL,
    predicted_ambiguity JSON NOT NULL,
    human_sequence JSON,
    human_groups JSON,
    human_dispositions JSON,
    reading_state VARCHAR NOT NULL DEFAULT 'PENDING',
    ocr_reviews JSON NOT NULL DEFAULT '{}',
    source_compatible BOOLEAN NOT NULL DEFAULT TRUE,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_reader_correctness_reading_state CHECK (reading_state IN ('PENDING','VERIFIED','SOURCE_UNAVAILABLE'))
);

CREATE INDEX IF NOT EXISTS ix_reader_correctness_project_id ON reader_correctness_reviews(project_id);
CREATE INDEX IF NOT EXISTS ix_reader_correctness_asset_id ON reader_correctness_reviews(asset_id);

COMMIT;
