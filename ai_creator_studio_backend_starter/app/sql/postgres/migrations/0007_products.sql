-- Workspace-scoped Product Catalog metadata and asset associations.
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    sku TEXT NOT NULL CHECK (length(btrim(sku)) BETWEEN 2 AND 64),
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 160),
    description TEXT CHECK (description IS NULL OR length(description) <= 2000),
    category TEXT NOT NULL CHECK (length(btrim(category)) BETWEEN 1 AND 64),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','ARCHIVED')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    UNIQUE(product_id,workspace_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_workspace_sku_ci ON products(workspace_id, lower(sku));
CREATE INDEX IF NOT EXISTS idx_products_workspace_status_updated ON products(workspace_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS product_assets (
    product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
    role TEXT NOT NULL CHECK (role IN ('primary','gallery')),
    PRIMARY KEY(product_id,asset_id)
);
CREATE INDEX IF NOT EXISTS idx_product_assets_asset ON product_assets(asset_id);

CREATE TABLE IF NOT EXISTS product_variants (
    variant_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY(product_id,workspace_id) REFERENCES products(product_id,workspace_id) ON DELETE CASCADE,
    sku TEXT NOT NULL CHECK (length(btrim(sku)) BETWEEN 2 AND 64),
    option_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','ARCHIVED')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_variants_workspace_sku_ci ON product_variants(workspace_id,lower(sku));
CREATE INDEX IF NOT EXISTS idx_product_variants_product_status ON product_variants(product_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS product_variant_assets (
    variant_id TEXT NOT NULL REFERENCES product_variants(variant_id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
    PRIMARY KEY(variant_id,asset_id)
);
CREATE INDEX IF NOT EXISTS idx_product_variant_assets_asset ON product_variant_assets(asset_id);

CREATE TABLE IF NOT EXISTS product_events (
    event_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY(product_id,workspace_id) REFERENCES products(product_id,workspace_id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_product_events_product_created ON product_events(product_id,created_at DESC,event_id);

CREATE OR REPLACE FUNCTION acs_check_product_asset_workspace() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE product_workspace TEXT; asset_workspace TEXT; asset_media_type TEXT; asset_deleted_at TIMESTAMPTZ;
BEGIN
  SELECT workspace_id INTO product_workspace FROM public.products WHERE product_id=NEW.product_id;
  SELECT workspace_id,media_type,deleted_at INTO asset_workspace,asset_media_type,asset_deleted_at
    FROM public.assets WHERE asset_id=NEW.asset_id;
  IF product_workspace IS NULL OR asset_workspace IS NULL OR product_workspace <> asset_workspace
     OR asset_media_type NOT LIKE 'image/%' OR asset_deleted_at IS NOT NULL THEN
    RAISE EXCEPTION 'product image must be an active image asset in the same workspace';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_product_assets_workspace ON product_assets;
CREATE TRIGGER trg_product_assets_workspace BEFORE INSERT OR UPDATE OF product_id,asset_id ON product_assets
FOR EACH ROW EXECUTE FUNCTION acs_check_product_asset_workspace();

CREATE OR REPLACE FUNCTION acs_check_product_variant_asset_workspace() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE variant_workspace TEXT; asset_workspace TEXT; asset_deleted_at TIMESTAMPTZ;
BEGIN
  SELECT workspace_id INTO variant_workspace FROM public.product_variants WHERE variant_id=NEW.variant_id;
  SELECT workspace_id,deleted_at INTO asset_workspace,asset_deleted_at FROM public.assets WHERE asset_id=NEW.asset_id;
  IF variant_workspace IS NULL OR asset_workspace IS NULL OR variant_workspace <> asset_workspace OR asset_deleted_at IS NOT NULL THEN
    RAISE EXCEPTION 'product variant asset must be active and belong to the same workspace';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_product_variant_assets_workspace ON product_variant_assets;
CREATE TRIGGER trg_product_variant_assets_workspace BEFORE INSERT OR UPDATE OF variant_id,asset_id ON product_variant_assets
FOR EACH ROW EXECUTE FUNCTION acs_check_product_variant_asset_workspace();

DROP TRIGGER IF EXISTS trg_product_events_no_update ON product_events;
CREATE TRIGGER trg_product_events_no_update BEFORE UPDATE OR DELETE ON product_events
FOR EACH ROW EXECUTE FUNCTION public.acs_reject_append_only_mutation();

ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_variants ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_variant_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_events ENABLE ROW LEVEL SECURITY;
