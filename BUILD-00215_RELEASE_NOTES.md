# BUILD-00215 Release Notes

- Added psycopg 3 dependency for the upcoming PostgreSQL runtime integration.
- Added a PostgreSQL migration runner with advisory transaction locking, checksum ledger, fail-closed configuration and read-only status inspection.
- Added initial PostgreSQL schema migration for 13 generation/runtime tables, constraints, indexes, leases and append-only review/export events.
- Enabled RLS on all new application tables with no client policies (default deny until tenant policy design is complete).
- Added migration discovery, schema safety, fail-closed and migration runner tests.
- Preserved SQLite as the only enabled runtime backend. No Supabase schema changes or Vercel deployments were performed in this build.
