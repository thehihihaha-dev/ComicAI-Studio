CREATE TABLE IF NOT EXISTS panel_ground_truth_reviews (
    review_id VARCHAR PRIMARY KEY,
    benchmark_asset_id VARCHAR NOT NULL UNIQUE,
    page_order INTEGER NOT NULL UNIQUE,
    selection_role VARCHAR NOT NULL,
    source_image_hash VARCHAR NOT NULL,
    source_path VARCHAR NOT NULL,
    image_width INTEGER NOT NULL,
    image_height INTEGER NOT NULL,
    human_panels JSONB NOT NULL DEFAULT '[]'::jsonb,
    state VARCHAR NOT NULL DEFAULT 'PENDING',
    revision INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_panel_ground_truth_reviews_asset
    ON panel_ground_truth_reviews (benchmark_asset_id);
CREATE INDEX IF NOT EXISTS ix_panel_ground_truth_reviews_page
    ON panel_ground_truth_reviews (page_order);
