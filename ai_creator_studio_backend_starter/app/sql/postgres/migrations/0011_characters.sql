-- Durable Character aggregate (workspace-scoped, soft delete, asset associations).
-- Server-side access only; no client policies or grants (see 0004).
CREATE TABLE IF NOT EXISTS characters (
    character_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    character_json JSONB NOT NULL CHECK (jsonb_typeof(character_json) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (character_id, workspace_id)
);
CREATE INDEX IF NOT EXISTS idx_characters_workspace
    ON characters(workspace_id, deleted_at, updated_at DESC);

CREATE TABLE IF NOT EXISTS character_assets (
    character_id TEXT NOT NULL REFERENCES characters(character_id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    relation TEXT NOT NULL DEFAULT 'model' CHECK (length(btrim(relation)) BETWEEN 1 AND 40),
    sort_order INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (character_id, asset_id, relation)
);
CREATE INDEX IF NOT EXISTS idx_character_assets_asset ON character_assets(asset_id);

CREATE OR REPLACE FUNCTION acs_check_character_asset_workspace() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE character_workspace TEXT; asset_workspace TEXT; asset_deleted_at TIMESTAMPTZ;
BEGIN
  SELECT workspace_id INTO character_workspace FROM public.characters WHERE character_id=NEW.character_id;
  SELECT workspace_id,deleted_at INTO asset_workspace,asset_deleted_at
    FROM public.assets WHERE asset_id=NEW.asset_id;
  IF character_workspace IS NULL OR asset_workspace IS NULL
     OR character_workspace <> asset_workspace OR asset_deleted_at IS NOT NULL THEN
    RAISE EXCEPTION 'character asset must be an active asset in the same workspace';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_character_assets_workspace ON character_assets;
CREATE TRIGGER trg_character_assets_workspace BEFORE INSERT OR UPDATE OF character_id,asset_id ON character_assets
FOR EACH ROW EXECUTE FUNCTION acs_check_character_asset_workspace();

ALTER TABLE characters ENABLE ROW LEVEL SECURITY;
ALTER TABLE character_assets ENABLE ROW LEVEL SECURITY;
