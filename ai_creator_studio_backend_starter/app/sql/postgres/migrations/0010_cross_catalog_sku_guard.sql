-- Serialize Product/Variant SKU writes and enforce cross-table uniqueness.
CREATE OR REPLACE FUNCTION acs_guard_cross_catalog_sku() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE collision BOOLEAN;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.workspace_id || ':' || lower(NEW.sku), 0));
  IF TG_TABLE_NAME = 'products' THEN
    SELECT EXISTS (
      SELECT 1 FROM public.product_variants v
      WHERE v.workspace_id=NEW.workspace_id AND lower(v.sku)=lower(NEW.sku)
    ) INTO collision;
  ELSE
    SELECT EXISTS (
      SELECT 1 FROM public.products p
      WHERE p.workspace_id=NEW.workspace_id AND lower(p.sku)=lower(NEW.sku)
    ) INTO collision;
  END IF;
  IF collision THEN
    RAISE EXCEPTION 'SKU already exists in this workspace' USING ERRCODE='23505';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_products_cross_catalog_sku ON products;
CREATE TRIGGER trg_products_cross_catalog_sku BEFORE INSERT OR UPDATE OF workspace_id,sku ON products
FOR EACH ROW EXECUTE FUNCTION acs_guard_cross_catalog_sku();
DROP TRIGGER IF EXISTS trg_product_variants_cross_catalog_sku ON product_variants;
CREATE TRIGGER trg_product_variants_cross_catalog_sku BEFORE INSERT OR UPDATE OF workspace_id,sku ON product_variants
FOR EACH ROW EXECUTE FUNCTION acs_guard_cross_catalog_sku();
