# BUILD-00170 Verification Report

## Baseline
- Source baseline: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00169.zip`.
- Baseline SHA-256 rechecked: `4d6db42ab4599968c9b654f18c22a108ce41ff7f208696ecb6de5c00272993a5`.
- `unzip -t` passed before extraction.

## Implementation verified
- Partial WebGL listener registration rollback retries removal of the first listener at most twice.
- Transient removal failure is retried and the original registration error remains visible.
- Persistent removal failure raises an `AggregateError` containing the registration error and both cleanup errors.
- The existing normal loss/restoration, handler failure isolation, teardown retry, and bounded retry behavior remain covered.

## Fresh test results
| Area | Result |
|---|---:|
| Viewer dependency-free JavaScript scripts | 14 scripts passed |
| WebGL context lifecycle suite | 57 assertions passed |
| Resource rollback suite | 19 assertions passed |
| Viewer Python scripts | 7 scripts passed |
| Backend pytest | 367 passed in 16.63s |
| TypeScript syntax/transpile | 10 source + 13 declaration files, 0 errors |
| API contract | 63/63 matched |
| Request contract | 15 checked, 0 findings |
| Response contract | 50 JSON endpoints / 52 endpoints, 0 missing routes or schemas |
| Package integrity | 0 findings |
| Python compileall | passed |

## Explicit blockers / not verified
- `test_three_resource_integration.mjs`: blocked with `ERR_MODULE_NOT_FOUND` for the declared `three` dependency.
- `npm run typecheck`: blocked because `react` and `@types/react` are not installed; semantic typecheck did not pass.
- Bounded npm registry probe: `EAI_AGAIN registry.npmjs.org`; no package versions or lockfiles were changed.
- Headless Chromium starts and requestAnimationFrame/ResizeObserver work, but WebGL2 context creation is unavailable; triangle rendering and context loss/restoration probe are blocked.
- React/Three.js browser E2E, actual WebGLRenderer recovery, GPU stress, and target-device performance remain unverified.

## Logs
See `build170_logs/` for raw test, contract, browser, dependency, and compile outputs.
