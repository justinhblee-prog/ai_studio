-- Durable Project aggregate. Access is server-side only until tenant RLS policies
-- and end-to-end PostgreSQL runtime parity are explicitly approved.
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    project_type TEXT NOT NULL CHECK (length(btrim(project_type)) BETWEEN 1 AND 64),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','ARCHIVED','COMPLETED')),
    description TEXT CHECK (description IS NULL OR length(description) <= 2000),
    external_reference TEXT CHECK (external_reference IS NULL OR length(external_reference) <= 128),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_projects_workspace_status_updated
    ON projects(workspace_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_projects_workspace_created
    ON projects(workspace_id, created_at DESC);
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
