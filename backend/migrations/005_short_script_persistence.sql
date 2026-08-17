BEGIN;

CREATE TABLE IF NOT EXISTS project_short_scripts (
    id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    result JSONB NOT NULL,
    segment_edits JSONB,
    style VARCHAR NOT NULL,
    source_story_fingerprint VARCHAR NOT NULL,
    source_story_approved_at TIMESTAMPTZ NOT NULL,
    status VARCHAR NOT NULL,
    approved_at TIMESTAMPTZ,
    approval_fingerprint VARCHAR,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_project_short_scripts_project_id UNIQUE (project_id)
);

CREATE INDEX IF NOT EXISTS ix_project_short_scripts_project_id
ON project_short_scripts(project_id);

COMMIT;
