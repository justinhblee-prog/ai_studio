-- Durable Project ↔ Product assignment history with tenant-safe composite keys.
CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_id_workspace ON projects(project_id,workspace_id);
CREATE TABLE IF NOT EXISTS project_product_assignments (
    assignment_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    assigned_by TEXT NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_at TIMESTAMPTZ,
    sort_order INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
    FOREIGN KEY(project_id,workspace_id) REFERENCES projects(project_id,workspace_id) ON DELETE CASCADE,
    FOREIGN KEY(product_id,workspace_id) REFERENCES products(product_id,workspace_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_project_product_active
    ON project_product_assignments(project_id,product_id) WHERE removed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_project_product_workspace
    ON project_product_assignments(workspace_id,project_id,removed_at,assigned_at);

CREATE TABLE IF NOT EXISTS project_product_events (
    event_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY(project_id,workspace_id) REFERENCES projects(project_id,workspace_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_project_product_events
    ON project_product_events(project_id,created_at DESC,event_id DESC);

DROP TRIGGER IF EXISTS trg_project_product_events_no_update ON project_product_events;
CREATE TRIGGER trg_project_product_events_no_update BEFORE UPDATE OR DELETE ON project_product_events
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

ALTER TABLE project_product_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_product_events ENABLE ROW LEVEL SECURITY;
