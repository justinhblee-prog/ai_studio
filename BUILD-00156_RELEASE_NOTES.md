# BUILD-00156 Release Notes

## Viewer Lifecycle Integration & Disposal Diagnostics

- Added a realistic dependency-free integration harness that builds nested scene graphs with shared textures, materials, geometries and skeletons, then exercises model replacement and renderer teardown order.
- Disposal diagnostics are no longer silently discarded in the viewer's primary lifecycle paths: all resources are attempted first, then a summarized error is raised to the named cleanup runner, which records it and continues with later cleanup actions.
- Updated authenticated GLTF structural checks and source validation to match the current byte-fetch + `GLTFLoader.parse` path and immutable AssetVersion preview endpoint.
- Added npm scripts for the lifecycle integration and authenticated preview Object URL tests.
- Backend 367 passed; Viewer lifecycle integration 32 assertions; offline structural checks 143 passed; package integrity 0 findings.

## Boundaries
No API/schema/database/dependency version, Provider, credit, publication, rights, production-data, or deployment changes. Real React/Three browser E2E, semantic TypeScript checking and target-device memory profiling remain unverified.
