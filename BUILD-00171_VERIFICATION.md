# BUILD-00171 Verification Report

## Baseline
- Source baseline: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00170.zip`.
- Baseline SHA-256 verified: `2e055e54c6409a3b76d27aac6754bd0507687da2ccbe935bd6501e5e6437db29`.
- `unzip -t` passed before extraction.

## Implementation verified
- GLTF parse results that arrive after cancellation are rolled back and disposed without scene commit.
- A synchronous failure during scene/model preparation invokes rollback.
- Rollback removes a partially attached model, stops and uncaches a mixer already published to the component refs, clears only matching refs, and disposes the complete GLTF resource graph.
- AnimationMixer is published immediately after construction and before clip-action setup, closing a partial setup ownership gap.
- A consumer `onLoad` callback exception is isolated after commit; it does not unwind a valid scene or leave the Viewer in the loading state.
- Rollback cleanup failures are surfaced separately from the original commit failure.

## Fresh verification
| Area | Result |
|---|---:|
| Viewer dependency-free JavaScript scripts | 15 passed |
| Three.js resource integration script | Blocked: `three` package unavailable (`ERR_MODULE_NOT_FOUND`) |
| New GLTF commit lifecycle tests | 18 assertions passed |
| Viewer Python scripts | 7 passed |
| Backend pytest | 367 passed in 18.65s |
| TypeScript syntax/transpile | 10 source + 14 declaration files, 0 errors |
| API contract | 63/63 matched, 0 missing |
| Request contract | 15 checked, 0 findings |
| Response contract | 50 JSON endpoints across 52 endpoints, 0 missing routes/schemas |
| Package integrity | 0 findings |
| Backend and Viewer Python compileall | Passed |

## Explicit blockers / not verified
- Actual Three.js integration is not verified because the declared `three` dependency is absent in this environment.
- Semantic TypeScript typecheck is not verified because React and `@types/react` packages are absent.
- Actual React/Three.js browser E2E, authenticated GLTF rendering, WebGLRenderer context loss/recovery, GPU stress, and target-device performance remain unverified.
- Previous bounded dependency/browser probes documented in BUILD-00170 remain relevant: npm registry access failed with `EAI_AGAIN`, and headless Chromium in this runtime did not provide WebGL2. BUILD-00171 did not alter dependency versions or lockfiles.

## Logs
Raw fresh logs are stored in `build171_logs/`.
