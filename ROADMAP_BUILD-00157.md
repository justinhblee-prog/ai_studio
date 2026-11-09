# BUILD-00157 --- 실제 Three.js Renderer/Scene 통합 검증

## 목표

구조 검사만으로 끝내지 않고 실제 Three.js 객체와 가능한 브라우저
환경에서 renderer/scene 수명주기를 검증합니다.

## 우선순위

### P0 기준선

-   BUILD-00156 소스 확보 및 ZIP 무결성 검사
-   패키지 스크립트/lockfile/React/Three 버전 확인
-   기존 테스트 재실행
-   브라우저/WebGL2 환경 확인

### P1 리소스 그래프

-   geometry/material/texture/render target 식별
-   공유 리소스와 소유권/중복 dispose 정책 명시
-   scene 교체와 viewer teardown을 실제 Three 객체로 재현
-   하나의 dispose 오류 이후 후속 cleanup 실행 검증
-   cleanup 순서 및 호출 횟수 검증

### P2 Renderer

-   renderer 생성/사용/teardown 검증
-   animation loop 중단 및 RAF 취소
-   controls/observer/canvas 정리
-   context loss 및 renderer disposal 예외 검토

### P3 브라우저 E2E

-   React Viewer mount
-   인증된 GLTF fixture 로드
-   실제 화면 렌더링 확인
-   모델 교체 및 unmount
-   GPU 리소스 정리 확인
-   콘솔/네트워크 오류 수집

### P4 회귀/성능

-   반복 mount/unmount stress test
-   반복 모델 교체 후 누수 지표
-   fixture 크기별 비교
-   가능한 목표 브라우저/디바이스 결과 기록

## 수용 기준

-   테스트가 실제 소스에서 재현 가능해야 합니다.
-   cleanup 실패가 후속 cleanup을 중단시키지 않아야 합니다.
-   공유 리소스 소유권과 중복 dispose 정책이 테스트로 문서화되어야
    합니다.
-   capability smoke와 실제 E2E 결과를 별도로 보고해야 합니다.
-   실행하지 못한 테스트는 blocked/unverified로 남겨야 합니다.
-   API/DB/dependency
    lockfile/Provider/credits/publication/rights/production
    data/deployment 변경은 범위에서 제외합니다.

## 위험

공유 리소스 소유권이 불명확하면 조기 dispose 또는 누수가 발생할 수
있습니다. Headless WebGL과 실제 GPU 환경은 다를 수 있으며, 단일 E2E
통과가 장시간 메모리 안정성을 보장하지 않습니다.


## BUILD-00157 실행 결과 및 잔여 항목

완료된 변경은 `BUILD-00157_RELEASE_NOTES.md`와 `BUILD-00157_VERIFICATION.md`를 참조합니다. `Studio3DViewer`의 RAF 루프를 별도 controller로 분리하여 단일 예약 프레임 소유, 중복 start 방지, idempotent stop, render 오류 시 루프 중단 및 teardown 통합을 구현했습니다. Controller 단위 테스트 19 assertions, Viewer lifecycle 32 assertions, Backend 367 tests 및 계약/구조 검증을 통과했습니다. Chromium WebGL2 capability smoke도 Xvfb/SwiftShader에서 통과했습니다.

다음 항목은 아직 미완료입니다.

- React/Three 의존성 부재 및 npm install timeout으로 semantic TypeScript 검사 blocked
- 실제 Three.js 인스턴스 기반 geometry/material/texture/render-target dispose 통합 테스트
- 실제 React Viewer + GLTF fixture 브라우저 E2E, 모델 교체/unmount, GPU 메모리 누수 측정
- WebGL context loss/restore 검증 및 목표 디바이스 성능 측정

따라서 BUILD-00157은 lifecycle scheduling 개선 및 회귀 검증을 완료했지만, 로드맵의 P1 실제 Three 객체 통합과 P3 브라우저 E2E 수용 기준은 통과하지 않았습니다. 미실행 검증을 통과로 표기하지 않습니다.

## BUILD-00158 increment — cross-pass resource ownership

- Added module-lifetime weak ownership tracking to make disposal idempotent across separate cleanup passes.
- Added a real Three.js object integration suite and npm script; execution is currently blocked by unavailable npm registry access and missing installed package.
- Updated the cleanup structural test for the extracted animation-frame controller.
- See `BUILD-00158_RELEASE_NOTES.md`, `BUILD-00158_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00158.md`.

### Remaining acceptance gates

- Real Three.js integration suite must run (not skip) in a dependency-installed environment.
- React Viewer + authenticated GLTF browser E2E remains unverified.
- WebGL context-loss recovery and target-device GPU memory stress remain unverified.


## BUILD-00159 — test-gate integrity correction

- The real Three.js integration test now exits non-zero when `three` is missing. The previous BUILD-00158 behavior (`SKIP` + exit 0) could produce a false-green CI result.
- Added cross-pass failure-policy coverage for a throwing `dispose()` implementation.
- Backend suite: 367 passed in 31.60s. Viewer structural checks: 143 passed. Chromium WebGL2 capability smoke, including raw context loss/restore, passed under Xvfb/SwiftShader.
- Real Three.js integration remains blocked by missing dependency and unavailable npm registry; React Viewer E2E, context-loss recovery, and GPU stress remain unverified.
- See `BUILD-00159_RELEASE_NOTES.md`, `BUILD-00159_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00159.md`.


## BUILD-00160 — WebGL context lifecycle recovery

- Implemented context-lost/restored listener orchestration in `webglContextLifecycle.mjs`.
- Integrated it into `Studio3DViewer`: pause RAF/clock on loss; resize and restart on restoration; surface a recoverable status; remove listeners during teardown.
- Helper/retry/wiring tests: 25 assertions passed. Backend 367 tests and Viewer contract/lifecycle checks passed.
- Browser capability smoke passed under Xvfb/SwiftShader, including raw WebGL2 context loss/restore.
- npm install still blocked by `EAI_AGAIN registry.npmjs.org`; actual Three.js integration, semantic typecheck, React Viewer E2E, renderer-level recovery and GPU stress remain unverified.
- See `BUILD-00160_VERIFICATION.md` and `CURRENT_HANDOFF_BUILD-00160.md`.


## BUILD-00161 — WebGL lifecycle exceptional-path hardening

- Hardened loss handling so a throwing animation-loop stop cannot suppress clock stop or the loss notification.
- Added safe error reporting, transactional listener registration rollback, and best-effort two-listener teardown.
- WebGL lifecycle helper/wiring/exceptional-path suite: 37 assertions passed. All 12 dependency-free Viewer JS suites and 7 Viewer Python scripts passed; backend 367 passed.
- Chromium raw WebGL2 capability smoke passed under Xvfb/SwiftShader.
- Actual Three.js integration and semantic TypeScript checking remain blocked by absent packages and npm cache/network access. React Viewer E2E, renderer-level recovery, and GPU stress remain unverified.
- See `BUILD-00161_RELEASE_NOTES.md`, `BUILD-00161_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00161.md`.

### Next acceptance work

1. Obtain declared dependencies in a network-enabled or approved cached environment without changing versions/lockfiles.
2. Run actual Three.js resource integration and semantic TypeScript checks.
3. Mount the React Viewer in Chromium and load the authenticated GLTF fixture.
4. Exercise context loss/restoration through the actual Three.js WebGLRenderer.
5. Stress repeated model replacement and unmount; measure GPU/resource cleanup and target-device performance.


## BUILD-00162 — retryable WebGL listener teardown

- WebGL lifecycle disposal now marks callbacks inert immediately and independently tracks each registered listener. A listener removal that throws remains pending and can be retried; successfully removed listeners are not removed again.
- WebGL lifecycle suite: 45 assertions passed, including transient failure/retry. All 12 dependency-free Viewer `.mjs` suites and all 7 Viewer Python test scripts passed. Backend: 367 passed in 21.92s.
- Actual Three.js integration, semantic TypeScript checking, React Viewer E2E, renderer-level context recovery, GPU stress, and target-device performance remain blocked/unverified.
- See `BUILD-00162_RELEASE_NOTES.md`, `BUILD-00162_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00162.md`.

### Next acceptance work

1. Obtain the exact declared React/Three.js dependencies in a network-enabled or approved cached environment; do not modify versions or lockfiles.
2. Run actual Three.js resource integration and semantic TypeScript checks.
3. Mount React Viewer in Chromium and load authenticated GLTF fixtures.
4. Exercise context loss/restoration through actual Three.js WebGLRenderer.
5. Stress repeated model replacement/unmount and measure GPU/resource cleanup.


## BUILD-00163 — bounded retry integrated into React teardown

- Added a finite retry wrapper for WebGL context listener teardown and wired it into the actual `Studio3DViewer` React effect cleanup. Production attempts are capped at two; persistent failures are reported through the existing cleanup diagnostic path.
- WebGL lifecycle suite: 53 assertions passed. All 12 dependency-free Viewer `.mjs` suites and all 7 Viewer Python test scripts passed. Fresh contract checks: API 63/63, response 0 missing routes/schemas, request 0 findings, package integrity 0 findings. TypeScript syntax validation: 10 TS/TSX files + 12 declaration files passed.
- Backend: 367 passed in 22.75s.
- Dependency audit: global TypeScript 5.8.3 exists, but React, React DOM, Three.js and their type packages are absent from installed packages/cache. Bounded npm registry probe failed with `EAI_AGAIN`. Actual Three.js integration and semantic typecheck remain blocked; React E2E, renderer-level context recovery, GPU stress and target-device performance remain unverified.
- See `BUILD-00163_RELEASE_NOTES.md`, `BUILD-00163_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00163.md`.

### Next acceptance work

1. Obtain the declared React/Three.js packages in a network-enabled or approved cached environment without changing dependency versions.
2. Run `npm run typecheck` and `npm run test:three-resource-integration`.
3. Mount React Viewer in Chromium and load authenticated GLTF fixtures.
4. Exercise context loss/restoration through actual Three.js WebGLRenderer.
5. Stress repeated model replacement/unmount and measure GPU/resource cleanup and target-device performance.


## BUILD-00164 — cleanup diagnostic visibility

- Fixed the diagnostic gap where `runViewerCleanupSteps` returned structured errors but production cleanup callers discarded the result. Both Viewer unmount and previous-model replacement now report failures through a best-effort diagnostic callback.
- Diagnostic callback exceptions are isolated and cannot interrupt the remaining teardown. Added regression checks for payload delivery, callback timing, and diagnostic-sink failure isolation.
- Viewer cleanup runtime: 14 assertions; cleanup lifecycle structural 13/13 plus disposal diagnostic integration 4/4. All 12 dependency-free Viewer JS suites and 7 Viewer Python scripts passed; WebGL lifecycle suite 53 assertions. Backend 367 passed in 20.01s. API 63/63; response/request/package validators clean; TS syntax 10 source + 12 declaration files clean.
- Actual Three.js integration and semantic TypeScript remain blocked by missing dependencies; bounded registry request failed with `EAI_AGAIN`. React E2E, actual renderer context recovery, GPU stress, and target-device performance remain unverified.
- See `BUILD-00164_RELEASE_NOTES.md`, `BUILD-00164_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00164.md`.

### Next acceptance work

1. Obtain exact declared React/Three.js packages in a network-enabled or approved cached environment; do not change dependency versions.
2. Run semantic TypeScript and actual Three.js resource integration tests.
3. Mount the React Viewer in Chromium and load authenticated GLTF fixtures.
4. Exercise context loss/restoration through actual Three.js WebGLRenderer.
5. Stress repeated model replacement/unmount and measure GPU/resource cleanup and target-device performance.


## BUILD-00165 — WebGL renderer initialization fallback

- Guarded `THREE.WebGLRenderer` construction in `Studio3DViewer`. WebGL/GPU initialization failure now clears scene/camera refs, shows an actionable Korean error state, and safely invokes the optional error callback instead of throwing out of the React effect.
- Added five structural regression assertions. All 12 dependency-free Viewer JS suites and all 7 Viewer Python scripts passed; cleanup structural 18/18, disposal diagnostic integration 4/4, WebGL lifecycle 53 assertions. Backend 367 passed in 19.49s.
- TypeScript syntax/transpile 10 source + 12 declarations passed. API 63/63; response 0 missing routes/schemas; request 0 findings; package integrity 0 findings.
- Semantic TypeScript and actual Three.js integration remain blocked by missing React/Three.js packages (`ERR_MODULE_NOT_FOUND`); React E2E, actual renderer context recovery, GPU stress, and target-device performance remain unverified.
- See `BUILD-00165_RELEASE_NOTES.md`, `BUILD-00165_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00165.md`.

### Next acceptance work

1. Obtain exact declared React/Three.js packages in a network-enabled or approved cached environment without changing versions/lockfiles.
2. Run semantic TypeScript and actual Three.js resource integration.
3. Mount React Viewer in Chromium and load authenticated GLTF fixtures.
4. Exercise context loss/restoration through actual Three.js WebGLRenderer.
5. Stress repeated model replacement/unmount and measure GPU/resource cleanup and target-device performance.


## BUILD-00166 — isolate Viewer consumer error callbacks

- Added a shared failure-isolated `notifyViewerError` helper and routed all five production error callback sites through it. A consumer callback throwing no longer escapes into the viewer's error-state, renderer/context lifecycle, GLTF parse, or download error paths.
- Added 7 unit assertions; updated cleanup structural checks to 20/20 plus disposal diagnostic integration 4/4. All 13 dependency-free Viewer JS scripts and 7 Viewer Python scripts passed. Backend 367 passed in 18.77s. API 63/63; response/request/package validators clean; TS syntax 10 source + 13 declarations clean.
- Semantic TypeScript and actual Three.js resource integration remain blocked by absent declared React/Three.js packages. Browser E2E, actual renderer context recovery, GPU stress and target-device performance remain unverified.
- See `BUILD-00166_RELEASE_NOTES.md`, `BUILD-00166_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00166.md`.

### Next acceptance work

1. Obtain the exact declared React/Three.js packages in an approved network-enabled or cached environment; do not change versions/lockfiles.
2. Run semantic TypeScript and actual Three.js resource integration.
3. Run Chromium React Viewer E2E with authenticated GLTF fixtures.
4. Exercise context loss/restoration through an actual Three.js WebGLRenderer.
5. Stress repeated model replacement/unmount and measure GPU/resource cleanup and target-device performance.

## BUILD-00167 update
- Lifecycle audit/verification package created; 13 Viewer JS scripts, 7 Viewer Python scripts, and 367 backend tests passed.
- Three.js integration remains blocked by missing `three` package.
- Identified an unresolved partial-initialization cleanup risk before React effect cleanup registration.
- Next priority: transactional Viewer setup rollback with failure-injection tests (BUILD-00168).


## BUILD-00168 — transactional Viewer setup rollback

- Added a reverse-order, failure-isolated rollback stack and integrated it into the React 3D Viewer setup effect. Successful setup commits the stack; synchronous setup failure rolls back acquired resources and transitions to an actionable error state.
- Registered rollback for scene resources, renderer, canvas insertion, key-light shadow, OrbitControls, ResizeObserver, WebGL context listeners, animation loop, and Viewer refs. Existing normal unmount teardown remains in place.
- Added rollback unit tests for reverse order, disposer failure isolation, idempotency, commit behavior, and seven injected setup failure positions.
- Fresh verification: 14 dependency-free Viewer JS scripts, 7 Viewer Python scripts, and 367 backend tests passed. TypeScript syntax/transpile 10 source + 13 declarations passed. API 63/63; request/response/package validators clean.
- Actual Three.js integration remains blocked by missing `three` (`ERR_MODULE_NOT_FOUND`); semantic typecheck, React/browser E2E, real WebGL context recovery, GPU stress and target-device performance remain unverified.
- See `BUILD-00168_RELEASE_NOTES.md`, `BUILD-00168_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00168.md`.

### Next acceptance work

1. Obtain exact declared React/Three.js packages in an approved network-enabled or cached environment without modifying versions or lockfiles.
2. Run semantic TypeScript and actual Three.js resource integration.
3. Run Chromium React Viewer E2E with authenticated GLTF fixtures, including partial setup failures and repeated unmount.
4. Exercise context loss/restoration through a real Three.js WebGLRenderer.
5. Stress GPU resource disposal and measure target-device performance.


## BUILD-00169 — immediate OrbitControls ownership registration and headless browser probe

- Moved the OrbitControls disposer registration directly after its constructor returns, before configuration and update calls. This ensures constructor-installed DOM listeners are owned by the rollback transaction even if later setup throws.
- Added two structural assertions for immediate disposer registration. Updated the optional Chromium capability probe to launch headless and report partial capability diagnostics.
- Fresh verification: 14 dependency-free Viewer JS scripts, 7 Viewer Python scripts, 367 backend tests, Python compileall, TypeScript syntax/transpile (10 source + 13 declarations), API 63/63, request 15 checked/0 findings, response 50 JSON endpoints across 52/0 missing, package integrity 0 findings.
- Actual Three.js integration and semantic typecheck remain blocked by missing `three` / `react` packages; npm registry `EAI_AGAIN`. Headless Chromium starts but WebGL2 is unavailable, so React E2E and real renderer recovery remain unverified.
- See `BUILD-00169_RELEASE_NOTES.md`, `BUILD-00169_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00169.md`.

### Next acceptance work

1. Obtain exact declared React/Three.js dependencies in a network-enabled or approved cached environment without changing versions/lockfiles.
2. Run semantic typecheck and actual Three.js resource integration.
3. Run React Viewer E2E in a WebGL2-capable Chromium environment.
4. Exercise real renderer context loss/restoration and repeated model replacement/unmount.
5. Run GPU stress and target-device performance acceptance.


## BUILD-00170 — transactional WebGL listener registration rollback

- Hardened the WebGL context lifecycle helper's partial registration failure path: if the restoration listener cannot be attached, removal of the already-attached loss listener is retried once (strict maximum two attempts).
- Persistent rollback failure now surfaces as an `AggregateError` containing the registration failure and cleanup failures; it is not silently treated as successful cleanup.
- Added transient and persistent rollback regression tests. WebGL lifecycle suite now passes 57 assertions; resource rollback suite passes 19 assertions.
- Fresh verification: 14 dependency-free Viewer JS scripts, 7 Viewer Python scripts, and 367 backend tests passed. TypeScript syntax/transpile 10 source + 13 declarations passed. API 63/63; request/response/package validators clean; Python compileall passed.
- Three.js integration and semantic typecheck remain blocked by absent declared dependencies; npm registry probe returned `EAI_AGAIN`. Headless Chromium starts but WebGL2 remains unavailable. React E2E, actual WebGLRenderer recovery, GPU stress, and target-device performance remain unverified.
- See `BUILD-00170_RELEASE_NOTES.md`, `BUILD-00170_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00170.md`.

### Next acceptance work

1. Obtain exact declared React/Three.js dependencies in an approved network-enabled or cached environment without changing versions or lockfiles.
2. Run semantic typecheck and actual Three.js resource integration.
3. Run React Viewer E2E in a WebGL2-capable Chromium runtime with authenticated GLTF fixtures.
4. Exercise actual renderer context loss/restoration and repeated model replacement/unmount.
5. Run GPU stress and target-device performance acceptance.


## BUILD-00171 — transactional GLTF parse-result commit

- Added `finalizeGltfLoad.mjs` to guard the synchronous commit of asynchronously parsed GLTF results. Cancelled/late results are disposed without scene attachment.
- Commit failures now roll back partial scene attachment, an already-published animation mixer, matching component refs, and GLTF resources. Mixer ownership is published before clip-action configuration.
- Isolated consumer `onLoad` callback exceptions after a successful commit.
- Added 18 lifecycle assertions. Fresh verification: 15 dependency-free Viewer JS scripts, 7 Viewer Python scripts, and 367 backend tests passed. TypeScript syntax/transpile 10 source + 14 declarations passed; API 63/63; request/response/package validators clean; Python compileall passed.
- Actual Three.js integration and semantic typecheck remain blocked by missing declared dependencies. React/browser E2E, real WebGLRenderer recovery, GPU stress, and target-device performance remain unverified.
- See `BUILD-00171_RELEASE_NOTES.md`, `BUILD-00171_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00171.md`.

### Next acceptance work

1. Obtain exact declared React/Three.js dependencies in an approved network-enabled or cached environment without changing versions/lockfiles.
2. Run semantic typecheck and actual Three.js resource integration.
3. Run React Viewer E2E in a WebGL2-capable runtime using authenticated GLTF fixtures.
4. Exercise stale parse completion, partial scene/animation commit failure, repeated model replacement/unmount, and actual context loss/restoration.
5. Run GPU stress and target-device performance acceptance.

## BUILD-00172 — stale GLTF parse error isolation
- Added cancellation guard to the non-abortable GLTFLoader parse error callback.
- Added two regression assertions proving stale parse failures cannot overwrite current UI state or notify consumers.
- Verification: 15 dependency-free Viewer JS scripts, 8 Viewer Python tests, 367 backend tests, TypeScript syntax/transpile 0 errors, API contract 63/63, request contract 15/15, response contract 50 JSON endpoints across 52 routes, package integrity 0 findings, Python compileall passed.
- Actual Three.js/React integration, WebGL2/GPU, and target-device checks remain blocked/unverified due to absent dependencies/runtime capability.

## BUILD-00173 — testable GLTF parse-error ownership
- Extracted stale-parse-error cancellation guard into `reportGltfParseError.mjs` and wired the GLTFLoader error callback through it.
- Added 8 dependency-free regression assertions and npm test script.
- Fresh verification: 16 Viewer JS scripts passed, 1 actual Three.js integration test blocked by missing dependency, 7 Viewer Python tests passed, 367 backend tests passed; syntax and contract validators clean.
- Corrected BUILD-00172 Viewer Python test count from 8 to 7 based on fresh enumeration; all 7 pass.
- See `BUILD-00173_RELEASE_NOTES.md`, `BUILD-00173_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00173.md`.

## BUILD-00174 — model request ownership across replacement and unmount
- Added a monotonic `KeyedRequestGate` token to the 3D viewer model-loading effect. Authenticated fetch completion/failure and GLTF parse success/failure all validate the same active owner token.
- Effect cleanup invalidates the token before aborting fetch, ensuring non-abortable parser callbacks from an old model cannot commit, set error state, or notify the consumer.
- Added 13 dependency-free request-ownership assertions and an npm test script; updated the authenticated GLTF source-contract test.
- Fresh verification: 17 Viewer JS tests passed, 1 actual Three.js integration test blocked by missing dependency, 7 Viewer Python tests passed, 367 backend tests passed; TypeScript syntax/transpile 0 errors; source structural checks 143 passed; API 63/63; request/response/package validators clean; compileall passed.
- Real Three.js integration, React semantic typecheck/E2E, WebGL2/GPU and target-device acceptance remain unverified due to missing dependencies/runtime capability.
- See `BUILD-00174_RELEASE_NOTES.md`, `BUILD-00174_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00174.md`.

## BUILD-00177 — recover and integrate missing Library-root deltas

- Library-root audit located BUILD-00167–00174 archives that were missed by the earlier `/AI_CREATOR_STUDIO` folder-only lookup. BUILD-00174 was selected as the latest recovered application source baseline.
- Restored BUILD-00168 transactional React Viewer setup rollback; BUILD-00169 immediate OrbitControls rollback ownership; BUILD-00170 WebGL listener registration rollback; BUILD-00171 transactional GLTF parse commit/rollback; BUILD-00172/00173 stale parse-error handling; and BUILD-00174 keyed model-request ownership.
- Reapplied BUILD-00175 scheduler exception handling and BUILD-00176 generation-token animation loop changes.
- Animation controller suite: 46 assertions. Viewer JS 17 scripts, Viewer Python 7 scripts, backend 367 passed, TypeScript syntax 10 source + 14 declarations, API 63/63, request/response validators clean, package integrity 0 findings.
- Actual Three.js integration and semantic React typecheck remain dependency-blocked; browser E2E, actual renderer recovery, GPU stress, and target-device performance remain unverified.
- See `BUILD-00177_RELEASE_NOTES.md`, `BUILD-00177_VERIFICATION.md`, and `RECOVERY_AUDIT_BUILD-00177.md`.


## BUILD-00178 — WebGL restoration reentrancy hardening
- Added lifecycle generation ownership for WebGL context recovery and revalidation after host-controlled clock, resize, and animation-loop operations.
- A context-loss event during restoration invalidates the stale restore transaction; nested restore events are suppressed; disposal invalidates pending recovery.
- Added 8 regression assertions covering reentrant loss during resize/start and nested duplicate restoration.
- Fresh verification: 17 dependency-free Viewer JS scripts, 7 Viewer Python scripts, 367 backend tests, TypeScript syntax/transpile 0 errors, API 63/63, request/response/package validators clean, compileall passed.
- Actual Three.js integration and semantic React/Three.js typecheck remain blocked by absent dependencies. Browser E2E, real renderer recovery, GPU stress, and target-device performance remain unverified.
- See `BUILD-00178_RELEASE_NOTES.md`, `BUILD-00178_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00178.md`.

## BUILD-00179 — additional WebGL restoration reentrancy coverage
- Added six regression assertions for context loss dispatched synchronously from `onRestored` and `clock.start()`; both newer loss generations remain authoritative.
- No production source change was needed after tests confirmed existing generation guards.
- Fresh dependency-free Viewer JavaScript scripts and 7 Viewer Python scripts passed; JS assertion summaries total 295. TypeScript syntax/transpile 10 source + 14 declarations passed; API 63/63; request/response/package validators clean; compileall passed.
- Backend full-suite rerun timed out without a reported test failure. Previous BUILD-00178 evidence records 367 passed on unchanged backend source but is not a fresh run.
- `npm install` timed out; actual Three.js integration and semantic typecheck remain blocked. Browser E2E/WebGL2/GPU/device acceptance remain open.
- See `BUILD-00179_RELEASE_NOTES.md`, `BUILD-00179_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00179.md`.

## BUILD-00180 — verification refresh and dependency-gated acceptance
- Verified BUILD-00179 archive SHA-256 and ZIP CRC before extraction.
- No production source changes were required; current WebGL reentrancy guard passed its existing regression coverage.
- Fresh checks: 17 dependency-free Viewer JS scripts (295 assertion-summary counts), 7 Viewer Python scripts, TypeScript syntax/transpile 10 source + 14 declarations, API 63/63, request contract 15 checked/0 findings, response contract 50 JSON endpoints across 52 routes/0 missing, package integrity 0 findings, Viewer/backend compileall passed.
- Backend pytest was terminated by the execution time limit at 39%, without a reported failure; it is explicitly incomplete, not a pass.
- Exact React/Three.js/TypeScript dependencies remain unavailable locally; actual Three.js integration and semantic typecheck remain blocked. Browser E2E, real WebGL2/GPU, and target-device acceptance remain open.
- See `BUILD-00180_RELEASE_NOTES.md`, `BUILD-00180_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00180.md`.

## BUILD-00181 — backend pytest sharding and complete grouped verification
- Added `scripts/run_backend_test_shards.py` to isolate pytest test files into fresh subprocesses with per-file logs, selectable shards, timeout controls, and aggregate summary.
- Backend test collection confirmed 367 tests. Fresh grouped runs passed `test_api.py` 70, `test_assets_api.py` 69, and remaining files 228: 367/367 total.
- New runner smoke: 3 selected files / 17 tests passed. The wrapper's complete 52-file run was not executed as one command in this build.
- Viewer verification: 17 dependency-free JS scripts, 295 assertion-summary counts, 7 Python scripts, TypeScript syntax/transpile 10 source + 14 declarations, API 63/63, request/response validators clean, package integrity 0 findings, Python compileall passed.
- Actual Three.js integration and semantic TypeScript remain blocked by missing dependencies; browser E2E, real renderer recovery, GPU stress, and target-device acceptance remain unverified.
- See `BUILD-00181_RELEASE_NOTES.md`, `BUILD-00181_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00181.md`.


## BUILD-00182 — streaming pytest shard logs and dependency/runtime diagnostics
- Updated backend shard runner to stream pytest output into per-file logs so timed-out runs retain progress.
- Fresh isolated backend files passed: alert repository 2, API 70, asset validation 9, assets API 69 (150 passed). Full 52-file combined shard execution remains incomplete; sequential execution stalled on the fourth shard although the same file passes alone.
- Viewer: 16 dependency-free JS scripts and 7 Python scripts passed; TypeScript syntax 10 source + 14 declarations; API 63/63; request/response/package validators clean; compileall passed.
- npm registry DNS `EAI_AGAIN` prevents installing declared Three.js/React dependencies; Chromium probe reports WebGL2 unavailable. Actual Three.js integration, semantic typecheck, browser E2E, GPU/device acceptance remain open.
- See `BUILD-00182_RELEASE_NOTES.md`, `BUILD-00182_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00182.md`.

## BUILD-00182 — backend grouped test verification and streaming shard logs
- Updated the per-file pytest shard runner to stream subprocess output directly to disk, preserving partial logs on timeout.
- Fresh backend grouped verification: 367/367 tests passed across 13 groups (four test files per invocation).
- Viewer dependency-free tests and contract validators passed; actual Three.js integration and browser WebGL2 remain blocked by missing dependencies/runtime support.
- No application runtime source or dependency manifest changes.
- See `BUILD-00182_RELEASE_NOTES.md`, `BUILD-00182_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00182.md`.

## BUILD-00183 — fresh complete backend verification and dependency gate
- Verified BUILD-00182 archive SHA-256 and ZIP CRC before a clean extraction.
- All 52 backend test files passed: 367/367. Seven four-file groups (282 tests) passed together; one subsequent combined group stalled, so the affected and remaining files were run individually. Every test file passed; the stalled combined invocation is not claimed as a pass.
- Viewer: 17 dependency-free JS scripts and 7 Python scripts passed; TypeScript syntax/transpile 10 source + 14 declarations; API 63/63; request contract 15 checked/0 findings; response contract 50 JSON endpoints across 52 routes/0 missing; package integrity 0 findings; compileall passed.
- Actual Three.js integration remains blocked by missing local `three` dependency; semantic TypeScript, browser E2E, WebGL2/GPU and target-device acceptance remain open.
- No application runtime or dependency manifest changes.
- See `BUILD-00183_RELEASE_NOTES.md`, `BUILD-00183_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00183.md`.

## BUILD-00184 — grouped backend verification and dependency/runtime gate refresh
- Restored BUILD-00183 from Library and verified its SHA-256 sidecar and ZIP CRC before clean extraction.
- Fresh backend verification: 52 test files passed in 13 direct four-file groups, 367/367 total. An 8-file isolated shard-runner diagnostic also passed 24/24 tests; the full wrapper was not run as one invocation.
- Viewer: 17 dependency-free JS scripts, 7 Python scripts, TypeScript syntax/transpile 10 source + 14 declarations, API 63/63, request contract 15 checked/0 findings, response contract 50 JSON endpoints across 52 routes/0 missing, package integrity 0 findings, Viewer/backend compileall passed.
- Exact npm probe for `three@0.180.0` again failed with DNS `EAI_AGAIN`; no dependency or lockfile changes. Chromium is present but WebGL2 context creation remains unavailable.
- Actual Three.js integration, semantic typecheck, React browser E2E, real WebGL2 renderer recovery, GPU stress, and target-device performance remain blocked/unverified.
- No application runtime source changes.
- See `BUILD-00184_RELEASE_NOTES.md`, `BUILD-00184_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00184.md`.

## BUILD-00185 — clean verification refresh and shard isolation diagnosis
- Recovered BUILD-00184 archive and verified ZIP CRC before fresh extraction.
- All 52 backend test files passed: 367/367. Groups 1–7 and 9–13 passed grouped execution; group 8's four files passed individually (8/8), and a separate isolated shard-runner run passed all 4 files / 8 tests. Combined group-8 invocation hit the command execution limit; no constituent test failure was observed.
- Viewer: 17 dependency-free JavaScript scripts and 7 Python scripts passed; TypeScript syntax 10 source + 14 declarations; API 63/63; request/response/package validators clean; compileall passed.
- npm cache audit found no registry entries and no local Three.js/React/type packages. Actual Three.js integration and semantic typecheck remain dependency-blocked; browser E2E/WebGL2/GPU/device acceptance remain open.
- No application runtime or dependency manifest changes.
- See `BUILD-00185_RELEASE_NOTES.md`, `BUILD-00185_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00185.md`.

## BUILD-00186 — fresh full backend and viewer verification; WebGL2 gate refresh
- Verified BUILD-00185 ZIP SHA-256 and CRC before clean extraction.
- Fresh backend verification: all 52 test files passed, 367/367. The sequential shard runner exceeded the outer command window after eight files; the affected shard and all remaining groups were independently rerun successfully. No test failure was observed.
- Viewer: 17 dependency-free JS scripts and 7 Python scripts passed; TypeScript syntax 10 source + 14 declarations; API 63/63; request contract 15 checked/0 findings; response contract 50 JSON endpoints across 52 routes and 28 models/0 missing; package integrity 0 findings; compileall passed.
- Fresh Chromium capability probe still cannot create WebGL2 context. npm cache is empty; exact dependencies remain unavailable locally. Actual Three.js integration, semantic typecheck, authenticated browser E2E, renderer recovery, GPU/device acceptance remain open.
- No application runtime or dependency manifest changes.
- See `BUILD-00186_RELEASE_NOTES.md`, `BUILD-00186_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00186.md`.


## BUILD-00187 — dependency/runtime investigation and verification refresh
- Verified BUILD-00186 ZIP SHA-256 and ZIP CRC before clean extraction.
- Fresh backend verification: 52 test files, 367/367 tests passed. The first grouped command exceeded the outer execution window after eight files; all remaining files were independently rerun in smaller groups.
- Viewer: 17 dependency-free JS scripts and 7 Python scripts passed; TypeScript syntax 10 source + 14 declarations; API 63/63; request contract 15 checked/0 findings; response contract 50 JSON endpoints across 52 routes and 28 models/0 missing; package integrity 0 findings; compileall passed.
- No usable local `three`, React/ReactDOM dependency tree, or React/Three type packages found. Two extra Chromium SwiftShader/ANGLE variants also failed to create WebGL2 contexts.
- No production source or dependency manifest changes. Actual Three.js integration, semantic typecheck, authenticated browser E2E, renderer recovery, GPU/device and real AI generation acceptance remain unverified.
- See `BUILD-00187_RELEASE_NOTES.md`, `BUILD-00187_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00187.md`.


## BUILD-00188 — Xvfb WebGL2 capability recovery and full verification
- Verified BUILD-00187 archive SHA-256 and ZIP CRC before clean extraction.
- Fresh backend verification: all 52 test files passed, 367/367.
- Viewer: 17 dependency-free JS scripts and 7 Python scripts passed; WebGL lifecycle regression 71 assertions; TypeScript syntax 10 source + 14 declarations; API 63/63; request contract 15 checked / 0 findings; response contract 50 JSON endpoints across 52 routes and 28 models / 0 missing; package integrity 0 findings; Viewer/backend compileall passed.
- Corrected the prior Chromium WebGL2 diagnosis: `xvfb-run -a python3 scripts/probe_browser_runtime.py` passes WebGL2 context creation, triangle rendering, ResizeObserver, requestAnimationFrame, context loss and restoration. This is browser capability smoke only, not React/Three.js Viewer E2E.
- Semantic TypeScript and actual Three.js integration remain blocked by unavailable React/Three.js packages. No production source or dependency manifest changes.
- See `BUILD-00188_RELEASE_NOTES.md`, `BUILD-00188_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00188.md`.

## BUILD-00189 — dependency/network blocker refresh and source review
- Verified BUILD-00188 archive SHA-256 and ZIP CRC before clean extraction.
- Fresh backend verification: all 52 test files passed, 367/367. Two orchestration invocations exceeded the outer execution window; partial files were rerun in bounded groups, and all 52 files have passing per-file evidence.
- Viewer: 17 dependency-free JS scripts and 7 Python scripts passed; TypeScript syntax 10 source + 14 declarations; API 63/63; request contract 15 checked/0 findings; response contract 50 JSON endpoints across 52 routes and 28 models/0 missing; package integrity 0 findings; compileall passed.
- Xvfb + Chromium WebGL2 browser capability probe repeated successfully (triangle, resize, animation frame, context loss/restoration). This remains capability smoke only, not React/Three.js E2E.
- Fresh npm registry DNS probe failed (`Could not resolve host: registry.npmjs.org`); no matching packages in npm cache or usable local React/Three dependencies. Actual Three.js integration and semantic typecheck remain blocked.
- Reviewed viewer setup, GLTF ownership/rollback, context lifecycle and cleanup; no reproducible production defect found. No runtime source or dependency manifest changes.
- See `BUILD-00189_RELEASE_NOTES.md`, `BUILD-00189_VERIFICATION.md`, and `CURRENT_HANDOFF_BUILD-00189.md`.
- Library delivery attempt: `/AI_CREATOR_STUDIO/BUILD-00189` folder created, but all six uploads throttled with a 4-hour cooldown; no files uploaded. Retry only after cooldown.

## BUILD-00190 — 3D dependency/runtime diagnosis and verification refresh
- Verified BUILD-00189 ZIP SHA-256 and CRC before clean extraction.
- Fresh backend verification: 52 test files, 367/367 passed, 0 failures. All affected test files were rerun individually or in bounded groups; logs retained.
- Viewer: 17 dependency-free JS scripts / 322 assertions; 7 Python scripts / 87 checks; TypeScript syntax 10 source + 14 declaration parses; API 63/63; request contract 15 checked/0 findings; response contract 50 JSON endpoints across 52 routes and 28 models/0 missing; source structural validation 143 checks; package integrity and Python compileall passed.
- Xvfb + Chromium WebGL2 probe passed context creation, shader/triangle pixel readback, resize observation, animation frame, context loss and restoration. It remains browser capability smoke only, not React/Three.js Viewer E2E.
- No local React/Three dependencies or cached packages found. DNS resolution failed for npm registry and public JS CDNs. Actual Three.js integration and semantic TypeScript remain blocked; no dependency manifest or lockfile changes.
- Live FASHN smoke preflight stopped at explicit cost-confirmation gate; no credentials/test URLs were configured and no provider request or charge occurred.
- Reviewed viewer/GLTF/context lifecycle code; no reproducible source defect found. No application runtime changes.
- See `BUILD-00190_RELEASE_NOTES.md`, `BUILD-00190_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00190.md`, and `build190_logs/`.


## BUILD-00193 — migration bundle v2 import preflight hardening
- Verified BUILD-00192 ZIP SHA-256 and CRC before extraction.
- Added bundle v2 schema digest and complete preflight of manifest, identifiers, exact data paths, symlinks, schema/data checksums, JSONL column shape, binary payloads and row counts before driver import or DB connection.
- Pin validated schema/data bytes in memory to prevent file replacement between validation and import; PostgreSQL target emptiness now includes views and sequences.
- Backend: all 52 test files passed, 380 tests; migration focused suite 17 passed. Viewer: 17 JS and 7 Python scripts passed; structural 143; API 63/63; request/response contracts clean; TypeScript syntax 10+14; package integrity 0 findings; compileall passed.
- Chromium/Xvfb WebGL2 capability smoke passed; actual React/Three.js E2E remains blocked by missing dependencies. Live PostgreSQL import remains blocked by absent server/psycopg/Docker/psql.
- See `BUILD-00193_RELEASE_NOTES.md`, `BUILD-00193_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00193.md`, and `build193_logs/`.

## BUILD-00194 — Migration bundle manifest integrity hardening (2026-11-05)

- Strengthened bundle v2 manifest metadata validation: boolean-safe row/table counts, non-empty source DB label, trigger inventory schema/count/uniqueness, schema-to-manifest trigger-name equality, and duplicate/invalid serial-column rejection.
- Added four adversarial regression tests; migration suite now 21 passing.
- Full backend suite: 52 files / 384 passed / 0 failed.
- Viewer offline verification: 17 JS scripts / 322 assertions; 7 Python scripts / 87 checks/tests; structural 143 passed; API 63/63; request 15/0 findings; response 50 contracts / 52 endpoints / 28 models / 0 missing.
- PostgreSQL live integration and React/Three.js E2E remain blocked by missing runtime/dependencies; no live AI provider request was made.

## BUILD-00195 — migration bundle closed-layout and strict JSON validation
- Verified BUILD-00194 ZIP SHA-256 and CRC before clean extraction.
- Hardened bundle v2 preflight: duplicate JSON keys and non-standard numeric constants rejected; malformed base64 rejected; trigger declarations recognized only at SQL statement boundaries; trigger-like text in comments/literals/function bodies ignored; duplicate trigger declarations rejected; unexpected files/directories and symlinked data directories rejected.
- Added 10 adversarial regression tests. Full backend: 52 test files / 394 passed / 0 failed; migration suite 31 passed.
- Viewer: 17 dependency-free JS scripts / 322 assertions; 12 Python scripts; structural 143; TypeScript syntax 10 source + 14 declarations; API 63/63; request 15/0 findings; response 50 contracts / 52 endpoints / 28 models / 0 missing; package integrity 0 findings; compileall passed.
- Xvfb + Chromium WebGL2 capability smoke passed (triangle, resize, animation frame, context loss/restoration); actual React/Three.js E2E remains blocked by missing dependencies. Optional Three.js integration script explicitly blocked, not counted as pass.
- Live PostgreSQL remains blocked by missing server/driver/container runtime. No live AI provider request made. SHA-256 manifest digests are not signed provenance.
- See `BUILD-00195_RELEASE_NOTES.md`, `BUILD-00195_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00195.md`, and `build195_logs/`.

## BUILD-00196 — Migration JSONL edge-case and export destination hardening (2026-11-05)
- Verified BUILD-00195 ZIP SHA-256 and CRC before extraction.
- Fixed JSONL preflight to split only on LF, not Unicode `str.splitlines()` boundaries; added coverage for U+2028, U+2029, NEL and vertical tab in stored text.
- Export now rejects non-empty destinations to prevent stale files from contaminating the bundle; strict JSON export rejects non-finite numbers; bundle version must be an integer and not bool/float.
- Migration-focused tests: 35 passed; backend compileall passed; Viewer source structural checks 143 passed; Viewer package integrity 0 findings.
- Full backend suite was attempted but did not finish within the execution window; no new full-suite pass is claimed (BUILD-00195 baseline: 394 passed).
- Live PostgreSQL, PostgreSQL runtime adapters, React/Three.js integration, and live AI provider generation remain blocked by unavailable runtime/dependencies/credentials/authorization.
- See `BUILD-00196_RELEASE_NOTES.md`, `BUILD-00196_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00196.md`, and `build196_logs/`.

## BUILD-00197 — Atomic migration bundle publication (2026-11-05)
- Verified BUILD-00196 archive SHA-256 and CRC before extraction.
- Export now builds in a sibling staging directory and publishes with same-filesystem atomic rename; failed exports clean up staging and never leave partial final bundles.
- Existing non-empty destinations and destination symlinks are rejected; existing empty directories are supported and replaced only after successful staging.
- Added regression coverage for failed-export cleanup, empty-destination publication and symlink destination refusal.
- Migration-focused tests: 37 passed; backend compileall passed; Viewer structural validation 143 passed; Viewer package integrity 0 findings.
- No fresh full backend-suite pass claimed; BUILD-00195 remains latest full-suite baseline (394 passed).
- PostgreSQL/React-Three.js/live AI blockers remain unchanged.


## BUILD-00198 — PostgreSQL SQL lexical splitting hardening (2026-11-05)
- Verified BUILD-00197 ZIP SHA-256 and CRC before clean extraction.
- SQL splitter now handles line comments, nested block comments, PostgreSQL E-string backslash escapes and dollar-quoted bodies; unterminated block comments fail closed.
- Added three adversarial parser regression tests. Migration suite: 40 passed. Full backend: 52 test files / 403 passed / 0 failed; compileall passed.
- Viewer offline checks: 17 JavaScript scripts passed, one actual Three.js integration script blocked by missing `three`; seven Python scripts passed; structural 143; syntax 10 source + 14 declarations; API 63/63; request 15/0 findings; response 50 contracts / 52 endpoints / 28 models / 0 missing; package integrity 0 findings.
- PostgreSQL live integration, PostgreSQL runtime adapters, React/Three.js E2E and live AI generation remain blocked by missing runtime/dependencies/credentials/authorization.
- See `BUILD-00198_RELEASE_NOTES.md`, `BUILD-00198_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00198.md`, and `build198_logs/`.


## BUILD-00199 — OpenAPI contract audit completeness (2026-11-05)
- Verified BUILD-00198 archive SHA-256 and ZIP CRC before clean extraction.
- Contract audit now reports runtime-only operations, design/runtime operation totals and normalized path collisions; collision merging preserves disjoint methods while reporting ambiguity. Added two regression tests.
- Full backend: 405 passed / 0 failed; focused audit 4 passed; compileall and runtime OpenAPI snapshot check passed.
- API structural reconciliation: design 15, runtime 101, 12 matched operations with drift, 3 design operations absent, 89 runtime-only operations, 0 path collisions.
- Viewer offline checks: 17 JS scripts, 7 Python scripts, source structure 143, TS syntax 10+14, API 63/63, request 15/0 findings, response 50 JSON contracts across 52 routes and 28 models, package integrity 0 findings. Three.js integration remains excluded due to missing dependency.
- PostgreSQL live integration, PostgreSQL runtime adapters, semantic TypeScript/React-Three.js E2E and live AI generation remain blocked by missing runtime/dependencies/credentials/authorization.
- See `BUILD-00199_RELEASE_NOTES.md`, `BUILD-00199_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00199.md`, and `build199_logs/`.

## BUILD-00201 (2026-11-06)
- Extended worker lease input validation to the Output→Asset link repository.
- Fenced failure acknowledgement UPDATE by current processing status, owner and live lease.
- Added 14 invalid-input regression cases; full backend suite 442 passed.
- External integration tests remain deferred by project decision.

## BUILD-00202 (2026-11-06)
- Reviewed SQLite Job/Event Unit-of-Work transaction ownership; added injected-failure atomicity tests for Job create and metadata update.
- Closed Outbox completion/unknown-outcome lease fencing: worker identity, current owner and live lease are required; mutation repeats the fence predicates. Expired POST outcomes are quarantined, never replayed.
- Updated worker ports/facades/callers; no schema migration or runtime dependency change.
- Full backend suite 447 passed; focused transaction/Outbox/UoW/API suite 140 passed; compileall passed.
- External PostgreSQL, React/Three.js E2E, and live AI-provider testing remain deferred by project decision.
- See `BUILD-00202_RELEASE_NOTES.md`, `BUILD-00202_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00202.md`, and `build202_logs/`.

## BUILD-00203 — Operational alert delivery lease fencing (2026-11-06)
- Verified BUILD-00202 archive SHA-256 and ZIP CRC before clean extraction.
- Added schema migration 10 for alert delivery owner and lease expiry; safely migrated legacy in-flight rows.
- Alert delivery claims now persist worker identity and bounded lease. Finish mutations require the same owner and live lease and repeat fencing predicates in the UPDATE.
- Expired delivery claims are reclaimable; stale owners cannot acknowledge after expiry/reclaim. Alert upsert clears stale claim metadata.
- Updated monitor worker, worker repository ports, compatibility facade, and GenerationJobRepository protocol/adapter.
- Added regression coverage for invalid input, stale owner, expired lease, reclaim, legacy migration, and concurrent claims.
- Full backend suite: 451 passed / 0 failed; worker/alert/repository/API focus: 118 passed; compileall passed.
- Webhook delivery remains at-least-once; remote duplicate suppression is not guaranteed. PostgreSQL, React/Three.js E2E, and live AI generation remain deferred.
- See `BUILD-00203_RELEASE_NOTES.md`, `BUILD-00203_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00203.md`, and `build203_logs/`.

## BUILD-00204 — Administrative recovery safety (2026-11-06)
- Verified BUILD-00203 archive SHA-256 and ZIP CRC before clean extraction.
- Added shared validation for operator identity, bounded recovery reason, and resource IDs.
- Poll Task retry now fences task and paired Job mutations against expected states; Output Asset Link retry fences failed→pending and checks mutation row count; Outbox reconciliation fences acknowledgement by `needs_reconciliation` and clears stale claim metadata.
- Added adversarial validation/delegation tests. Full backend suite: 466 passed / 0 failed; focused operator recovery/API/Outbox/Output Asset Link suite: 111 passed; compileall passed.
- Viewer/API structural checks were not rerun in this backend-only build. PostgreSQL, React/Three.js E2E and live AI generation remain deferred by project decision.
- See `BUILD-00204_RELEASE_NOTES.md`, `BUILD-00204_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00204.md`, and `build204_logs/`.

## BUILD-00205 — API security surface audit (2026-11-06)
- Verified BUILD-00204 ZIP SHA-256 and CRC before clean extraction.
- Reduced public `/health` response to `{ok, version}`; operational Worker and queue counters remain behind platform-operations authorization.
- Added route registration auth coverage regression test with exact public allowlist; all `/internal/**` routes must require bearer identity.
- Added workspace role, signed preview, platform-ops, and API design/runtime compatibility decision matrix.
- Full backend: 468 passed / 0 failed; focused API/security/assets/operations: 144 passed; compileall and runtime OpenAPI snapshot check passed.
- Signed asset preview capability URLs remain valid until their bounded expiry (maximum 15 minutes) after membership revocation; authenticated preview-content is available for immediate membership re-check.
- PostgreSQL live, React/Three.js E2E and live AI generation remain deferred by project decision.
- See `BUILD-00205_RELEASE_NOTES.md`, `BUILD-00205_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00205.md`, `docs/security/API_SECURITY_AND_COMPATIBILITY_MATRIX_BUILD-00205.md`, and `build205_logs/`.

## BUILD-00206 — Output Asset provenance and workspace integrity (2026-11-06)
- Corrected generated Output import actor attribution to `system:output_asset_link_worker`; initiating user and worker ID are separately recorded.
- Hardened deterministic retry checks for Asset owner/workspace/content, complete immutable AssetVersion metadata, and Provenance workspace/event/source linkage.
- Added adversarial cross-workspace version and owner-mismatch tests. Focused 100 passed; full backend 470 passed; compileall and runtime OpenAPI check passed.
- Historical user-attributed provenance remains accepted for recovery compatibility. Automated orphan private-file cleanup remains a follow-up; live PostgreSQL, React/Three.js E2E, and live AI provider tests remain deferred.
