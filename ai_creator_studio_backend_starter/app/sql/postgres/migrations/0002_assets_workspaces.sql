-- Asset metadata and Workspace RBAC schema. Storage bytes remain in a separate private object store.
CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner','admin','editor','viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id,user_id)
);
CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id,workspace_id);

CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
    original_filename TEXT NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    media_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    checksum_sha256 TEXT NOT NULL CHECK (length(checksum_sha256)=64),
    gltf_version TEXT NOT NULL DEFAULT '',
    embedded_binary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_assets_owner_workspace ON assets(owner_id,workspace_id,deleted_at);
CREATE INDEX IF NOT EXISTS idx_assets_workspace ON assets(workspace_id,deleted_at);

CREATE TABLE IF NOT EXISTS asset_versions (
    version_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    storage_key TEXT NOT NULL UNIQUE,
    media_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    checksum_sha256 TEXT NOT NULL CHECK (length(checksum_sha256)=64),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(asset_id,version_number)
);
CREATE INDEX IF NOT EXISTS idx_asset_versions_asset ON asset_versions(asset_id,version_number DESC);

CREATE TABLE IF NOT EXISTS asset_relations (
    relation_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
    source_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    target_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    relation_type TEXT NOT NULL CHECK (relation_type IN ('derived_from','variant_of','uses_texture','paired_with')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(source_asset_id,target_asset_id,relation_type),
    CHECK(source_asset_id <> target_asset_id)
);
CREATE INDEX IF NOT EXISTS idx_asset_relations_workspace ON asset_relations(workspace_id);

CREATE TABLE IF NOT EXISTS asset_provenance (
    provenance_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    version_number INTEGER,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_asset_provenance_asset ON asset_provenance(asset_id,created_at DESC);

-- RLS is enabled with no client policies: service-side access only until tenant policies are reviewed.
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_relations ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_provenance ENABLE ROW LEVEL SECURITY;
