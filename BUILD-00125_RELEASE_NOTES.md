# BUILD-00125 Release Notes

- Product Catalog UI now supports editing existing Product SKU, name, description, category and ordered image Asset references.
- The edit flow calls the existing `PUT /v1/products/{product_id}` route; create/archive operations remain available.
- Added an explicit cancel-edit action. Active Lookbook reference conflicts continue to be enforced by the backend and surfaced in the UI.
- Updated Viewer contract coverage: API 60/60, JSON request bodies 12 checked, response schemas 49 JSON endpoints / 50 total method-path endpoints, runtime JSON coverage 49/49.
- Backend 359 passed; Viewer scripts 8 passed; structural checks 70/70; TypeScript syntax/transpilation 8 files / 0 diagnostics; package integrity 0 findings.
- No backend route/schema or dependency version changed.
