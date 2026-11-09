# BUILD-00177 Verification

## Source provenance and recovery

- Materialized BUILD-00167 through BUILD-00174 from the Library root and extracted each archive.
- Selected BUILD-00174 as the latest recovered application-source baseline.
- Compared BUILD-00174 against the prior BUILD-00176 package. The prior package was missing the BUILD-00168–00174 source helpers, tests, and `Studio3DViewer.tsx` integration changes.
- Restored the BUILD-00174 files, then reapplied the BUILD-00175/00176 animation-frame controller and its tests.
- BUILD-00176 Library archive SHA-256 matched the local BUILD-00176 archive exactly: `e9a869f9823d0a3fb67c8bca72babb8ce3f13bf6d13a5249e821c922abeb58ef`.
- All recovered ZIP archives passed `unzip -t`.

## Test results

| Area | Result |
|---|---:|
| Viewer dependency-free JavaScript scripts | 17 passed |
| Three.js resource integration | Blocked: `three` package not installed |
| Viewer Python scripts | 7 passed |
| Backend pytest | 367 passed in 19.17s |
| Backend Python compileall | Passed |
| TypeScript syntax/transpile | 10 source + 14 declarations, 0 errors |
| API contract | 63/63 calls matched; 0 findings |
| Request contract | 15 JSON body calls checked; 0 findings |
| Request contract tests | 2 passed |
| Response contract | 50 JSON endpoints documented across 52; 0 missing routes/schemas |
| Package integrity | 0 findings |
| Package integrity tests | 4 passed |
| Animation frame controller | 46 assertions passed |

## Explicitly blocked / not verified

- `npm run typecheck` cannot complete because `react` and React type declarations are absent from this runtime. The observed TypeScript errors include unresolved React module/JSX types; syntax/transpile validation is not a substitute for semantic typechecking.
- `npm run test:three-resource-integration` cannot start because `three` is absent (`ERR_MODULE_NOT_FOUND`).
- React browser E2E, actual Three.js WebGLRenderer context loss/restoration, GPU resource stress, and target-device performance are not verified.
- No dependency version or lockfile was modified to bypass the missing packages.

## Key regression coverage restored

- Transactional React Viewer setup rollback and failure injection.
- GLTF parse-result commit rollback and stale-result disposal.
- Stale GLTF parse-error suppression and owner-aware error notification.
- Keyed model request ownership across fetch/parse/cleanup.
- WebGL context listener registration rollback and bounded retry.
- Animation-frame scheduler failure, stale-generation callback suppression, reentrant restart, and cancellation-failure state consistency.
