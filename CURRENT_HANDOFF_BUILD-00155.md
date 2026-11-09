# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00155
- Base: BUILD-00154
- Focus: failure-isolated Viewer renderer teardown and model replacement.

## Completed
- Added `runViewerCleanupSteps.mjs` with `.d.mts` types.
- Cleanup steps execute independently; a throwing controls/observer/renderer/etc. cleanup cannot prevent later steps.
- Structured result reports attempted/completed counts and named errors.
- Renderer teardown isolates frame cancellation, ResizeObserver disconnect, controls disposal, mixer stop/root uncache, GLTF and stage-resource disposal, shadow disposal, renderer disposal, canvas removal, and ref clearing.
- Model replacement similarly isolates scene removal, prior mixer stop/root uncache, GLTF disposal and ref clearing.
- Added runtime failure injection and structural order tests; exposed `npm run test:viewer-cleanup`.
- No dependency/API/schema/DB/Provider/credit/publication/rights/production-data/deployment changes.

## Verification
- Backend full pytest: 367 passed.
- GLTF disposal: 33 assertions; Viewer cleanup runtime: 10; lifecycle structural: 13/13.
- Authenticated GLTF 15/15; model base path 10/10; bounded download 17 runtime / 19 structural.
- Preview Object URL 5; RequestScopeGate 7; KeyedRequestGate 7; project lifecycle 4; Lookbook links 12; Lookbook recovery 19/19.
- Viewer API 63/63; request body 15 checked / 0 findings; response contract 50 JSON / 52 total / 28 models / 0 missing.
- TypeScript syntax 10 source + 9 declarations / 0 errors; package integrity 0 findings; Python compileall passed.
- Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader. It is not React/Three E2E and did not load GLTF.
- Semantic `npm run typecheck` attempted but blocked by missing React/Three packages and declarations; no dependency install or lockfile modification.
- Independent clean extraction and rerun documented in `BUILD-00155_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining blockers / limitations
- Actual React/Three browser component E2E and visible GLB/GLTF rendering remain unverified.
- Semantic TypeScript checking remains blocked until trusted pinned dependencies are provisioned.
- Production-size or target-device memory profiling remains unavailable.
- External glTF buffer/image URIs remain rejected; multi-file glTF import is not implemented.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous priorities
1. Continue viewer lifecycle hardening and add a realistic renderer/scene integration harness when trusted Three.js dependencies are available.
2. Provision trusted pinned React/Three.js dependencies only when registry access is available; then run semantic typecheck and actual browser E2E with minimal GLB/data-URI GLTF fixtures.
3. Profile target-device memory and representative large assets.
4. Continue readiness work without crossing approval boundaries.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved security/policy decisions without explicit approval.
