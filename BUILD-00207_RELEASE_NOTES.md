# BUILD-00207 — Workspace Relation Integrity

- Added database-level workspace integrity triggers for Product images, Product Variant images, Character Assets, Lookbook Assets, and Lookbook entity references.
- Added adversarial direct-SQL tests proving cross-workspace relation writes are rejected, including Variant-to-parent workspace agreement.
- Product and Character edits are now blocked while an active Lookbook Draft references those source entities; edits resume after draft archival.
- Scoped Product and Character reference-protection queries to the owning workspace.
- Focused tests: 72 passed. Full Backend: 473 passed. Python compileall and runtime OpenAPI snapshot check passed.
- No API schema changes. PostgreSQL equivalents and historical-row integrity audit remain open.
