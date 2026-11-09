# BUILD-00152 — Complete GLTF Resource Lifecycle Disposal

## Summary
Hardened Three.js/GLTFLoader resource cleanup so all scenes returned by GLTFLoader are covered, including non-active scenes and nested material-uniform textures. Shared resources are disposed once per cleanup call.

## Changes
- Added dependency-free `disposeGltfResources.mjs` plus `.d.mts` declaration.
- Traverse every `gltf.scenes` entry (falling back to `scene` or a supplied scene root).
- Collect geometries, single/array materials, and textures nested in material properties/uniforms.
- Guard cyclic object graphs and dispose shared resources exactly once per call.
- Retain the complete parsed GLTF object through viewer lifecycle so model replacement and WebGL teardown dispose resources from all scenes, not only `gltf.scene`.
- Late parse completion after cancellation disposes the complete GLTF result.
- Added executable tests for shared resources, inactive scenes, nested textures, legacy scene-root input, null/empty inputs, and cyclic uniforms.
- No dependency, API/schema, database, Provider, credit, publication, rights, production-data or deployment changes.

## Verification
- Backend pytest: 367 passed.
- GLTF disposal: 11 assertions passed.
- Authenticated GLTF structural: 11/11.
- Model base path: 10/10.
- Bounded download: runtime 17/17; structural 19/19.
- Preview Object URL 5; RequestScopeGate 7; KeyedRequestGate 7; project lifecycle 4; Lookbook signed-link 12; Lookbook recovery 19/19.
- Viewer API 63/63; request-body contract 15 checked / 0 findings; response contract 50 JSON / 52 total / 28 models / 0 missing.
- TypeScript syntax/transpilation: 10 source + 8 declaration files / 0 syntax errors (not semantic typecheck).
- Package integrity 4 tests; Python compileall passed.
- Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader; this does not prove React/Three.js component E2E or actual GLTF rendering.
- Semantic `npm run typecheck` attempted and remains blocked because `react`, `three`, and their type packages are not installed in this environment; registry provisioning remains unavailable/unverified.
