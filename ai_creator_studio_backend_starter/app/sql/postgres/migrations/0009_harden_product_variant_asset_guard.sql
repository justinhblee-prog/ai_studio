-- Variant imagery must be a live image Asset in the same Workspace.
CREATE OR REPLACE FUNCTION acs_check_product_variant_asset_workspace() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE variant_workspace TEXT; asset_workspace TEXT; asset_media_type TEXT; asset_deleted_at TIMESTAMPTZ;
BEGIN
  SELECT workspace_id INTO variant_workspace FROM public.product_variants WHERE variant_id=NEW.variant_id;
  SELECT workspace_id,media_type,deleted_at INTO asset_workspace,asset_media_type,asset_deleted_at
    FROM public.assets WHERE asset_id=NEW.asset_id;
  IF variant_workspace IS NULL OR asset_workspace IS NULL OR variant_workspace <> asset_workspace
     OR asset_media_type NOT LIKE 'image/%' OR asset_deleted_at IS NOT NULL THEN
    RAISE EXCEPTION 'product variant image must be an active image asset in the same workspace';
  END IF;
  RETURN NEW;
END;
$$;
