# BUILD-00157 Verification Report

## Build identity
- Build: BUILD-00157
- Base: BUILD-00156
- Focus: animation-frame lifecycle ownership, failure isolation, regression verification.

## Changes verified
- New animation frame controller is dependency-free and owns at most one scheduled frame.
- Duplicate start is ignored; stop is idempotent; controller restarts; render failures stop scheduling; error-handler failures do not escape or revive the loop.
- Studio3DViewer delegates RAF scheduling/cancellation to the controller and stops it in the existing teardown sequence.

## Results
| Check | Result |
|---|---:|
| Backend pytest | 367 passed |
| Viewer source structural validation | 143 passed |
| Viewer lifecycle integration | 32 assertions passed |
| Animation frame controller | 19 assertions passed |
| Viewer cleanup helper | 10 assertions passed |
| GLTF disposal | 33 assertions across disposal suites; failure-isolation cases passed |
| Authenticated GLTF loading | 15/15 passed |
| Bounded GLTF download | 19/19 structural; runtime suite passed |
| Model base path | 10/10 passed |
| Authenticated preview Object URLs | 5 passed |
| RequestScopeGate | 7 passed |
| KeyedRequestGate | 7 passed |
| Project lifecycle events | 4 passed |
| Lookbook preview links | 12 passed |
| Lookbook preview recovery | 19/19 passed |
| Viewer API contract | 63/63 matched |
| Request body contract | 15 checked, 0 findings |
| Viewer response contract | 50 JSON / 52 total endpoints / 28 models; 0 missing routes or schemas |
| Package integrity | 0 findings |
| TypeScript syntax/transpile | 10 TS/TSX sources + 11 declaration files; 0 errors |
| Chromium WebGL2 capability smoke | pass under Xvfb/SwiftShader |

## Blocked / unverified
- Semantic TypeScript typecheck: blocked by missing `react`, `three`, addon modules, and typings. `npm install --ignore-scripts --no-audit --no-fund --package-lock=false` timed out. No dependencies or lockfile were changed.
- Actual Three.js geometry/material/texture/render-target object graph integration: unverified; current lifecycle integration harness uses test doubles and must not be described as real Three.js E2E.
- React Viewer mount, authenticated GLTF fixture visual render, browser model replacement/unmount, GPU resource telemetry, and context-loss/recovery: unverified.
- Target-device performance and memory profiling: not run.

## Browser smoke interpretation
The Chromium probe succeeded with WebGL2, a rendered triangle pixel, ResizeObserver, and requestAnimationFrame under Xvfb/SwiftShader. The probe explicitly does not load React, Three.js, Studio3DViewer, or a GLTF fixture.

## Approval boundary
No external paid services, Provider calls, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, API/DB changes, or dependency-version changes were performed.
