# BUILD-00124 Release Notes

- Product Catalog UI now supports up to 12 Variant-specific image Asset references on Variant creation and editing.
- Existing Variants can be edited through `PUT /v1/products/{product_id}/variants/{variant_id}` to update SKU, color/size option values and image references.
- Existing non-color/size option-value keys are preserved when editing through the UI.
- Clearing the Variant-specific image list restores the existing Lookbook fallback to the parent Product image gallery.
- Updated contract coverage: Viewer API 59/59, request bodies 11 checked, response schemas 48 JSON endpoints / 49 total method-path endpoints; runtime JSON coverage 48/48.
- Backend 359 passed; Viewer scripts 8 passed; structural checks 68/68; TypeScript syntax/transpilation 8 files / 0 diagnostics; package integrity 0 findings.
- No backend route/schema or dependency version changed.
