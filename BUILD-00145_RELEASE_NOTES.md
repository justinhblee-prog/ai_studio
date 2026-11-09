# BUILD-00145 Release Notes

## Authenticated GLTF/GLB AssetVersion Loading
- The 3D AssetWorkspace now previews the exact current immutable AssetVersion through the authenticated preview-content endpoint.
- Studio3DViewer fetches bytes with the current Bearer token and no-store caching, aborts stale fetches on model/token change or unmount, and parses the in-memory bytes with GLTFLoader.parse.
- External glTF buffer/image URIs remain rejected. GLB and self-contained data-URI glTF are the supported single-file formats.
- No backend route/schema, database migration, dependency version, Provider, credit, publication or rights behavior changed.

## Verification
- Backend: 367 passed.
- Authenticated GLTF checks: 9/9.
- Object URL registry: 5 assertions. Request scope: 7. Keyed request: 7. Project events: 4. Lookbook links: 12. Lookbook recovery: 19/19.
- TypeScript syntax: 10 source + 5 declaration files, 0 syntax errors (not semantic typecheck).
- API: 63/63. Request body: 15 checked, 0 findings. Response: 50 JSON / 52 endpoints / 28 models / 0 missing. Package integrity: 0 findings.
- Actual React/Three.js browser E2E and semantic TypeScript remain unverified.
