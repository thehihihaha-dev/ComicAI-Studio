BEGIN;
CREATE TABLE IF NOT EXISTS reader_logical_reviews (
 review_id VARCHAR PRIMARY KEY, project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 asset_id VARCHAR NOT NULL REFERENCES assets(id) ON DELETE CASCADE, page_order INTEGER NOT NULL,
 source_image_hash VARCHAR NOT NULL, representation_version VARCHAR NOT NULL, representation_hash VARCHAR NOT NULL,
 logical_regions JSON NOT NULL, human_panel_order JSON, human_region_orders JSON, human_dispositions JSON,
 human_flattened_sequence JSON, state VARCHAR NOT NULL DEFAULT 'PENDING', revision INTEGER NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
 CONSTRAINT uq_reader_logical_asset_representation UNIQUE(asset_id,representation_hash),
 CONSTRAINT ck_reader_logical_state CHECK(state IN ('PENDING','VERIFIED','SOURCE_UNAVAILABLE'))
);
CREATE INDEX IF NOT EXISTS ix_reader_logical_project_id ON reader_logical_reviews(project_id);
CREATE INDEX IF NOT EXISTS ix_reader_logical_asset_id ON reader_logical_reviews(asset_id);
COMMIT;
