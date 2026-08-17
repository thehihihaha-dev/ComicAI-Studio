BEGIN;

ALTER TABLE project_story_analyses
ADD COLUMN IF NOT EXISTS review_state JSONB,
ADD COLUMN IF NOT EXISTS review_source_revision VARCHAR,
ADD COLUMN IF NOT EXISTS review_status VARCHAR;

COMMIT;
