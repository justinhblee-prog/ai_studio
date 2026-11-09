-- Durable Lookbook Draft aggregate: planning drafts with review workflow, image roles,
-- referenced entities, events, immutable approved Photo outputs, assembly review,
-- manifest export and package export audit. Server-side access only.
CREATE TABLE IF NOT EXISTS lookbook_drafts (
    draft_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    created_by TEXT NOT NULL,
    payload_json JSONB NOT NULL CHECK (jsonb_typeof(payload_json) = 'object'),
    workflow_status TEXT NOT NULL DEFAULT 'DRAFT'
        CHECK (workflow_status IN ('DRAFT','IN_REVIEW','CHANGES_REQUESTED','APPROVED')),
    submitted_at TIMESTAMPTZ,
    submitted_by TEXT,
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    review_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    UNIQUE (draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_lookbook_drafts_workspace ON lookbook_drafts(workspace_id, archived_at, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_lookbook_drafts_review ON lookbook_drafts(workspace_id, workflow_status, updated_at DESC);

CREATE TABLE IF NOT EXISTS lookbook_draft_assets (
    draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    role TEXT NOT NULL CHECK (role IN ('product','person')),
    PRIMARY KEY (draft_id, asset_id, role)
);
CREATE INDEX IF NOT EXISTS idx_lookbook_draft_assets_asset ON lookbook_draft_assets(asset_id);

CREATE TABLE IF NOT EXISTS lookbook_draft_entities (
    draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('project','character','product','product_variant')),
    entity_id TEXT NOT NULL,
    PRIMARY KEY (draft_id, entity_type, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_lookbook_draft_entities_ref ON lookbook_draft_entities(entity_type, entity_id);

CREATE OR REPLACE FUNCTION acs_check_lookbook_draft_asset_workspace() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE draft_workspace TEXT; asset_workspace TEXT; asset_media_type TEXT; asset_deleted_at TIMESTAMPTZ;
BEGIN
  SELECT workspace_id INTO draft_workspace FROM public.lookbook_drafts WHERE draft_id=NEW.draft_id;
  SELECT workspace_id,media_type,deleted_at INTO asset_workspace,asset_media_type,asset_deleted_at
    FROM public.assets WHERE asset_id=NEW.asset_id;
  IF draft_workspace IS NULL OR asset_workspace IS NULL OR draft_workspace <> asset_workspace
     OR asset_media_type NOT LIKE 'image/%' OR asset_deleted_at IS NOT NULL THEN
    RAISE EXCEPTION 'lookbook draft asset must be an active image asset in the same workspace';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_lookbook_draft_assets_workspace ON lookbook_draft_assets;
CREATE TRIGGER trg_lookbook_draft_assets_workspace BEFORE INSERT OR UPDATE OF draft_id,asset_id ON lookbook_draft_assets
FOR EACH ROW EXECUTE FUNCTION acs_check_lookbook_draft_asset_workspace();

CREATE OR REPLACE FUNCTION acs_check_lookbook_entity_workspace() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE draft_workspace TEXT; entity_workspace TEXT;
BEGIN
  SELECT workspace_id INTO draft_workspace FROM public.lookbook_drafts WHERE draft_id=NEW.draft_id;
  IF NEW.entity_type = 'project' THEN
    SELECT workspace_id INTO entity_workspace FROM public.projects WHERE project_id=NEW.entity_id;
  ELSIF NEW.entity_type = 'character' THEN
    SELECT workspace_id INTO entity_workspace FROM public.characters WHERE character_id=NEW.entity_id;
  ELSIF NEW.entity_type = 'product' THEN
    SELECT workspace_id INTO entity_workspace FROM public.products WHERE product_id=NEW.entity_id;
  ELSE
    SELECT workspace_id INTO entity_workspace FROM public.product_variants WHERE variant_id=NEW.entity_id;
  END IF;
  IF draft_workspace IS NULL OR entity_workspace IS NULL OR draft_workspace <> entity_workspace THEN
    RAISE EXCEPTION 'lookbook entity reference must exist in the same workspace';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_lookbook_draft_entities_workspace ON lookbook_draft_entities;
CREATE TRIGGER trg_lookbook_draft_entities_workspace BEFORE INSERT OR UPDATE OF draft_id,entity_type,entity_id ON lookbook_draft_entities
FOR EACH ROW EXECUTE FUNCTION acs_check_lookbook_entity_workspace();

CREATE TABLE IF NOT EXISTS lookbook_draft_events (
    event_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (length(btrim(event_type)) BETWEEN 1 AND 80),
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (draft_id, workspace_id) REFERENCES lookbook_drafts(draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_lookbook_draft_events ON lookbook_draft_events(draft_id, created_at DESC, event_id DESC);
DROP TRIGGER IF EXISTS trg_lookbook_draft_events_no_update ON lookbook_draft_events;
CREATE TRIGGER trg_lookbook_draft_events_no_update BEFORE UPDATE OR DELETE ON lookbook_draft_events
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

CREATE TABLE IF NOT EXISTS lookbook_output_assets (
    output_item_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    photo_run_id TEXT NOT NULL,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    asset_version_id TEXT NOT NULL,
    provenance_id TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL CHECK (length(checksum_sha256) = 64),
    product_id TEXT,
    product_sku TEXT,
    product_variant_id TEXT,
    variant_sku TEXT,
    variant_options_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    page_order INTEGER NOT NULL CHECK (page_order BETWEEN 1 AND 100),
    caption TEXT CHECK (caption IS NULL OR length(caption) <= 240),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (draft_id, photo_run_id),
    UNIQUE (draft_id, page_order),
    FOREIGN KEY (draft_id, workspace_id) REFERENCES lookbook_drafts(draft_id, workspace_id),
    FOREIGN KEY (photo_run_id, workspace_id) REFERENCES photo_processing_runs(run_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_lookbook_outputs_draft ON lookbook_output_assets(draft_id, page_order);

CREATE OR REPLACE FUNCTION acs_check_lookbook_output_asset_workspace() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE asset_workspace TEXT;
BEGIN
  SELECT workspace_id INTO asset_workspace FROM public.assets WHERE asset_id=NEW.asset_id;
  IF asset_workspace IS NULL OR asset_workspace <> NEW.workspace_id THEN
    RAISE EXCEPTION 'lookbook output asset must belong to the same workspace';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_lookbook_outputs_workspace ON lookbook_output_assets;
CREATE TRIGGER trg_lookbook_outputs_workspace BEFORE INSERT ON lookbook_output_assets
FOR EACH ROW EXECUTE FUNCTION acs_check_lookbook_output_asset_workspace();
DROP TRIGGER IF EXISTS trg_lookbook_outputs_immutable ON lookbook_output_assets;
CREATE TRIGGER trg_lookbook_outputs_immutable BEFORE UPDATE OR DELETE ON lookbook_output_assets
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

CREATE TABLE IF NOT EXISTS lookbook_output_export_events (
    event_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    output_count INTEGER NOT NULL CHECK (output_count > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (draft_id, workspace_id) REFERENCES lookbook_drafts(draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_lookbook_output_exports ON lookbook_output_export_events(draft_id, created_at, event_id);
DROP TRIGGER IF EXISTS trg_lookbook_output_exports_no_update ON lookbook_output_export_events;
CREATE TRIGGER trg_lookbook_output_exports_no_update BEFORE UPDATE OR DELETE ON lookbook_output_export_events
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

CREATE TABLE IF NOT EXISTS lookbook_output_assembly_review_events (
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    event_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('submitted','approved','rejected')),
    comment TEXT NOT NULL DEFAULT '' CHECK (length(comment) <= 2000),
    snapshot_sha256 TEXT NOT NULL CHECK (length(snapshot_sha256) = 64),
    output_count INTEGER NOT NULL CHECK (output_count > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (draft_id, workspace_id) REFERENCES lookbook_drafts(draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_lookbook_assembly_reviews ON lookbook_output_assembly_review_events(draft_id, seq);
DROP TRIGGER IF EXISTS trg_lookbook_assembly_reviews_no_update ON lookbook_output_assembly_review_events;
CREATE TRIGGER trg_lookbook_assembly_reviews_no_update BEFORE UPDATE OR DELETE ON lookbook_output_assembly_review_events
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

CREATE TABLE IF NOT EXISTS lookbook_output_package_exports (
    export_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    package_sha256 TEXT NOT NULL CHECK (length(package_sha256) = 64),
    package_size_bytes BIGINT NOT NULL CHECK (package_size_bytes >= 0),
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    snapshot_sha256 TEXT NOT NULL CHECK (length(snapshot_sha256) = 64),
    output_count INTEGER NOT NULL CHECK (output_count > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at BIGINT NOT NULL,
    FOREIGN KEY (draft_id, workspace_id) REFERENCES lookbook_drafts(draft_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_lookbook_package_exports ON lookbook_output_package_exports(draft_id, created_at DESC);
DROP TRIGGER IF EXISTS trg_lookbook_package_exports_no_update ON lookbook_output_package_exports;
CREATE TRIGGER trg_lookbook_package_exports_no_update BEFORE UPDATE OR DELETE ON lookbook_output_package_exports
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

ALTER TABLE lookbook_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE lookbook_draft_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE lookbook_draft_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE lookbook_draft_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE lookbook_output_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE lookbook_output_export_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE lookbook_output_assembly_review_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE lookbook_output_package_exports ENABLE ROW LEVEL SECURITY;
