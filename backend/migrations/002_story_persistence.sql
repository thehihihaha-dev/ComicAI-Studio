BEGIN;

CREATE TABLE IF NOT EXISTS project_story_analyses (
    id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    result JSONB NOT NULL,
    status VARCHAR NOT NULL,
    source_revision VARCHAR NOT NULL,
    pipeline_version VARCHAR,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_project_story_analyses_project_id UNIQUE (project_id)
);

CREATE INDEX IF NOT EXISTS ix_project_story_analyses_project_id
ON project_story_analyses(project_id);

COMMIT;
