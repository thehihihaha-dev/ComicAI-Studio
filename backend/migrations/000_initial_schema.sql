BEGIN;

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    content_type VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL REFERENCES projects(id),
    filename VARCHAR NOT NULL,
    file_type VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    page_order INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'ready',
    ocr_text TEXT,
    ocr_blocks TEXT,
    vision_regions TEXT,
    reading_order TEXT,
    vision_status VARCHAR NOT NULL DEFAULT 'pending',
    dialogues TEXT,
    dialogue_status VARCHAR NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS dialogue_ground_truths (
    id VARCHAR PRIMARY KEY,
    asset_id VARCHAR NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    region_id INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    ai_text TEXT,
    verified_text TEXT NOT NULL,
    correction_score DOUBLE PRECISION,
    recovery_confidence DOUBLE PRECISION,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT uq_dialogue_ground_truth_asset_region
        UNIQUE (asset_id, region_id)
);

CREATE INDEX IF NOT EXISTS ix_dialogue_ground_truths_asset_id
ON dialogue_ground_truths(asset_id);

COMMIT;
