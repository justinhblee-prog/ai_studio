-- Durable Photo Draft aggregate: drafts, image roles, events, processing runs,
-- append-only processing/review/export events. Server-side access only.
CREATE TABLE IF NOT EXISTS photo_drafts (
    draft_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    created_by TEXT NOT NULL,
    payload_json JSONB NOT NULL CHECK (jsonb_typeof(payload_json) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    UNIQUE (draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_drafts_workspace
    ON photo_drafts(workspace_id, archived_at, updated_at DESC);

CREATE TABLE IF NOT EXISTS photo_draft_assets (
    draft_id TEXT NOT NULL REFERENCES photo_drafts(draft_id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    role TEXT NOT NULL CHECK (role IN ('source','mask','reference')),
    PRIMARY KEY (draft_id, asset_id, role)
);
CREATE INDEX IF NOT EXISTS idx_photo_draft_assets_asset ON photo_draft_assets(asset_id);

CREATE OR REPLACE FUNCTION acs_check_photo_draft_asset_workspace() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE draft_workspace TEXT; asset_workspace TEXT; asset_media_type TEXT; asset_deleted_at TIMESTAMPTZ;
BEGIN
  SELECT workspace_id INTO draft_workspace FROM public.photo_drafts WHERE draft_id=NEW.draft_id;
  SELECT workspace_id,media_type,deleted_at INTO asset_workspace,asset_media_type,asset_deleted_at
    FROM public.assets WHERE asset_id=NEW.asset_id;
  IF draft_workspace IS NULL OR asset_workspace IS NULL OR draft_workspace <> asset_workspace
     OR asset_media_type NOT LIKE 'image/%' OR asset_deleted_at IS NOT NULL THEN
    RAISE EXCEPTION 'photo draft asset must be an active image asset in the same workspace';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_photo_draft_assets_workspace ON photo_draft_assets;
CREATE TRIGGER trg_photo_draft_assets_workspace BEFORE INSERT OR UPDATE OF draft_id,asset_id ON photo_draft_assets
FOR EACH ROW EXECUTE FUNCTION acs_check_photo_draft_asset_workspace();

CREATE TABLE IF NOT EXISTS photo_draft_events (
    event_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (length(btrim(event_type)) BETWEEN 1 AND 80),
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (draft_id, workspace_id) REFERENCES photo_drafts(draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_draft_events ON photo_draft_events(draft_id, created_at DESC, event_id DESC);
DROP TRIGGER IF EXISTS trg_photo_draft_events_no_update ON photo_draft_events;
CREATE TRIGGER trg_photo_draft_events_no_update BEFORE UPDATE OR DELETE ON photo_draft_events
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

CREATE TABLE IF NOT EXISTS photo_processing_runs (
    run_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    created_by TEXT NOT NULL,
    idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 200),
    payload_hash TEXT NOT NULL,
    processor_version TEXT NOT NULL,
    operation TEXT NOT NULL,
    source_version_id TEXT,
    source_checksum_sha256 TEXT,
    status TEXT NOT NULL CHECK (status IN ('processing','succeeded','failed')),
    attempts INTEGER NOT NULL DEFAULT 1 CHECK (attempts >= 1),
    claimed_by TEXT,
    lease_expires_at TIMESTAMPTZ,
    output_asset_id TEXT,
    output_version_id TEXT,
    output_checksum_sha256 TEXT,
    quality_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, idempotency_key),
    UNIQUE (run_id, draft_id, workspace_id),
    UNIQUE (run_id, workspace_id),
    FOREIGN KEY (draft_id, workspace_id) REFERENCES photo_drafts(draft_id, workspace_id),
    CHECK ((status = 'processing') = (claimed_by IS NOT NULL AND lease_expires_at IS NOT NULL)),
    CHECK (status <> 'succeeded' OR (output_asset_id IS NOT NULL AND output_version_id IS NOT NULL
                                     AND output_checksum_sha256 IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_photo_runs_draft ON photo_processing_runs(draft_id, created_at DESC, run_id);

CREATE TABLE IF NOT EXISTS photo_processing_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (length(btrim(event_type)) BETWEEN 1 AND 80),
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (run_id, draft_id, workspace_id) REFERENCES photo_processing_runs(run_id, draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_run_events ON photo_processing_events(run_id, created_at, event_id);
DROP TRIGGER IF EXISTS trg_photo_run_events_no_update ON photo_processing_events;
CREATE TRIGGER trg_photo_run_events_no_update BEFORE UPDATE OR DELETE ON photo_processing_events
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

CREATE TABLE IF NOT EXISTS photo_output_review_events (
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved','changes_requested','rejected')),
    comment TEXT NOT NULL DEFAULT '' CHECK (length(comment) <= 2000),
    asset_id TEXT NOT NULL,
    asset_version_id TEXT NOT NULL,
    provenance_id TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL CHECK (length(checksum_sha256) = 64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (run_id, draft_id, workspace_id) REFERENCES photo_processing_runs(run_id, draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_output_reviews ON photo_output_review_events(run_id, seq);
DROP TRIGGER IF EXISTS trg_photo_output_reviews_no_update ON photo_output_review_events;
CREATE TRIGGER trg_photo_output_reviews_no_update BEFORE UPDATE OR DELETE ON photo_output_review_events
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

CREATE TABLE IF NOT EXISTS photo_output_export_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (run_id, draft_id, workspace_id) REFERENCES photo_processing_runs(run_id, draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_output_exports ON photo_output_export_events(run_id, created_at, event_id);
DROP TRIGGER IF EXISTS trg_photo_output_exports_no_update ON photo_output_export_events;
CREATE TRIGGER trg_photo_output_exports_no_update BEFORE UPDATE OR DELETE ON photo_output_export_events
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

ALTER TABLE photo_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE photo_draft_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE photo_draft_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE photo_processing_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE photo_processing_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE photo_output_review_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE photo_output_export_events ENABLE ROW LEVEL SECURITY;
