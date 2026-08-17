BEGIN;

ALTER TABLE project_story_analyses
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS approval_source_revision VARCHAR,
ADD COLUMN IF NOT EXISTS approval_story_fingerprint VARCHAR;

COMMIT;
