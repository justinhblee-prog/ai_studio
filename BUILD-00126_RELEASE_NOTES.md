# BUILD-00126 Release Notes

- Adds an exported `ProjectWorkspace` React component for workspace-scoped Project create/list/edit and non-destructive ACTIVE/COMPLETED/ARCHIVED lifecycle actions.
- Uses existing `POST /v1/projects`, `GET /v1/projects`, and `PUT /v1/projects/{project_id}` routes; no backend route/schema change.
- Active Lookbook Project references remain protected by the backend 409 guard. External reference is displayed read-only after creation because the current update contract does not support changing it.
- Adds responsive styling, Viewer package exports, and README integration example.
- Updated Viewer API contract 63/63; request bodies 15 checked; response schemas 51 JSON endpoints / 52 total endpoints; runtime JSON coverage 51/51.
- Backend 359 passed; Viewer scripts 8 passed; structural checks 75/75; TypeScript syntax/transpilation 9 files / 0 diagnostics; package integrity 0 findings.
