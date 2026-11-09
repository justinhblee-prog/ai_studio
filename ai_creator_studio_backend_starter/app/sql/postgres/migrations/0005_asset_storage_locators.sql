-- Persist the object-store locator alongside Asset metadata.
-- Existing rows are explicitly marked as local for backwards compatibility.
ALTER TABLE assets
    ADD COLUMN IF NOT EXISTS storage_backend TEXT NOT NULL DEFAULT 'local',
    ADD COLUMN IF NOT EXISTS storage_bucket TEXT NOT NULL DEFAULT 'private_assets';
ALTER TABLE asset_versions
    ADD COLUMN IF NOT EXISTS storage_backend TEXT NOT NULL DEFAULT 'local',
    ADD COLUMN IF NOT EXISTS storage_bucket TEXT NOT NULL DEFAULT 'private_assets';

ALTER TABLE assets
    ADD CONSTRAINT assets_storage_backend_check
    CHECK (storage_backend IN ('local','supabase_storage')) NOT VALID;
ALTER TABLE asset_versions
    ADD CONSTRAINT asset_versions_storage_backend_check
    CHECK (storage_backend IN ('local','supabase_storage')) NOT VALID;

ALTER TABLE assets VALIDATE CONSTRAINT assets_storage_backend_check;
ALTER TABLE asset_versions VALIDATE CONSTRAINT asset_versions_storage_backend_check;
