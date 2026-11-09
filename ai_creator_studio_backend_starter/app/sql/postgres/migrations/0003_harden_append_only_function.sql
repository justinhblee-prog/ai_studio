-- Fix mutable search_path on the append-only guard function.
CREATE OR REPLACE FUNCTION public.acs_reject_append_only_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'append-only event records cannot be updated or deleted';
END;
$$;
