# BUILD-00169 Verification Report

## Baseline integrity
- BUILD-00168 archive SHA-256 rechecked: `17becf5bf9860aaf2fefa3f01c6a3b2526d4370ff31f98f15a4957fb6fd78caf`.
- `unzip -t` passed before extraction.

## Changes verified
- OrbitControls disposer is registered immediately after constructor return and before configuration/update.
- Rollback test suite: existing 17 assertions plus 2 production-wiring assertions passed.
- Headless Chromium probe now runs without DISPLAY/Xvfb and reports granular capability results.

## Test results
| Area | Result |
|---|---:|
| Viewer dependency-free JavaScript scripts | 14 passed |
| Viewer Python scripts | 7 passed |
| Backend pytest | 367 passed |
| Python compileall | passed |
| TypeScript syntax/transpile | 10 source + 13 declaration files, 0 errors |
| API contract | 63/63 matched |
| Request contract | 15 checked, 0 findings |
| Response contract | 50 JSON endpoints / 52 endpoints, 0 missing routes or schemas |
| Package integrity | 0 findings |

## Explicit blockers
- `test_three_resource_integration.mjs`: blocked; Node reports `ERR_MODULE_NOT_FOUND` for `three`.
- `npm run typecheck`: blocked by absent `react` and `@types/react` declarations; this is not a successful semantic typecheck.
- npm registry probe: `EAI_AGAIN registry.npmjs.org`.
- Headless Chromium: browser starts; animationFrame and ResizeObserver observed; WebGL2 unavailable, so triangle render and context-loss/restoration checks did not run.
- React/Three E2E, actual WebGLRenderer context recovery, GPU stress, and target-device performance: not verified.

## Raw logs
See `build169_logs/` for individual test and validation outputs.
