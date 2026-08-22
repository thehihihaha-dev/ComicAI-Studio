BEGIN;
CREATE TABLE IF NOT EXISTS reader_router_validation_reviews (
 sample_id VARCHAR PRIMARY KEY,
 project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 asset_id VARCHAR NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
 page_order INTEGER NOT NULL,
 logical_region_id VARCHAR NOT NULL,
 bbox JSON NOT NULL,
 source_image_hash VARCHAR NOT NULL,
 representation_hash VARCHAR NOT NULL,
 state VARCHAR NOT NULL DEFAULT 'PENDING',
 human_transcription TEXT,
 provenance VARCHAR NOT NULL DEFAULT 'human',
 revision INTEGER NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL,
 CONSTRAINT ck_reader_router_validation_state CHECK(state IN ('PENDING','VERIFIED','UNREADABLE','SOURCE_UNAVAILABLE')),
 CONSTRAINT uq_reader_router_validation_region UNIQUE(asset_id,representation_hash,logical_region_id)
);
CREATE INDEX IF NOT EXISTS ix_reader_router_validation_project_id ON reader_router_validation_reviews(project_id);
CREATE INDEX IF NOT EXISTS ix_reader_router_validation_asset_id ON reader_router_validation_reviews(asset_id);
COMMIT;
