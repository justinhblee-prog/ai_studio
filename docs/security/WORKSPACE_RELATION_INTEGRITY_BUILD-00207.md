# Workspace Relation Integrity — BUILD-00207

## Scope

Reviewed Product image associations, Product Variant image associations, Character Asset associations, and Lookbook asset/entity references. The review covered both normal API workflows and direct database mutation paths.

## Findings and changes

1. **Cross-workspace relation rows were not protected by database constraints.** API validators checked workspace membership, but direct SQL writes or future internal code paths could insert a relation whose parent and Asset belonged to different workspaces. Added SQLite `BEFORE INSERT` and `BEFORE UPDATE` triggers for `product_assets`, `product_variant_assets`, `character_assets`, and `lookbook_draft_assets`. Product Variant checks also require the Variant and its parent Product to agree on workspace. Lookbook asset links require an active image Asset.
2. **Lookbook entity references lacked database-level workspace validation.** Added insert/update triggers for project, character, product, and product_variant entity references. Variant references must agree with both the parent Product and Lookbook Draft workspace.
3. **Active Lookbook references did not freeze all referenced source entities.** Product Variant mutation was already blocked, but Product and Character updates could still change the source after a draft had captured its references. Product and Character updates now return HTTP 409 while an active Lookbook Draft references them. Once the draft is archived, edits resume.
4. **Reference cleanup checks were made explicitly workspace-scoped** for Product and Character lifecycle protection queries.

## Verification

- Focused Asset/Product/Lookbook API tests: 72 passed / 0 failed.
- Full Backend suite: 473 passed / 0 failed.
- Python compileall: PASS.
- Runtime OpenAPI snapshot check: PASS (no API contract change).
- Direct SQL adversarial tests verify that cross-workspace Product, Variant, Character, Lookbook Asset, and Lookbook entity relations fail at the database boundary.

## Compatibility and limits

- Existing valid relation rows are not rewritten. The triggers protect new inserts and updates; they do not automatically audit or repair historical corrupt rows. A separate read-only integrity audit/migration is still advisable before production rollout.
- The triggers are SQLite-specific. Equivalent PostgreSQL composite foreign keys/constraints or trigger functions must be designed and validated before PostgreSQL deployment.
- Live PostgreSQL, React/Three.js E2E, and live AI provider tests remain deferred by project decision.
