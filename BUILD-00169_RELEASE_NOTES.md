# BUILD-00169 Release Notes

## Scope
Continued the 3D Viewer resource-ownership audit and improved the browser capability probe so it can run in headless Chromium environments.

## Production changes
- Moved `OrbitControls` rollback registration to immediately after construction. `OrbitControls` installs DOM event listeners in its constructor, so registration now precedes all configuration and `update()` calls that could throw.
- Added a structural regression test asserting immediate ownership registration before configuration.
- Updated the optional Chromium WebGL capability probe to launch headless, removing the unnecessary X-server dependency. The probe now preserves partial browser diagnostics when a capability wait times out.

## Fresh verification
- 14 dependency-free Viewer JavaScript test scripts passed (excluding the actual Three.js integration script, which is blocked by the absent `three` package).
- 7 Viewer Python test scripts passed.
- Backend pytest: 367 passed.
- Python compileall: passed.
- TypeScript syntax/transpile: 10 TS/TSX source files + 13 declaration files, 0 errors.
- API contract: 63/63 calls matched.
- Request contract: 15 JSON body calls checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 endpoints; 0 missing routes/schemas or unresolved dynamic segments.
- Package integrity: 0 findings.

## Blocked / not verified
- Actual Three.js integration test remains blocked by `ERR_MODULE_NOT_FOUND` for declared dependency `three`.
- Semantic `npm run typecheck` remains blocked by missing `react` and React type declarations; no dependency versions or lockfiles were changed.
- Headless Chromium starts and executes animation-frame/ResizeObserver checks, but WebGL2 context creation is unavailable in this runtime. Actual WebGL/Three renderer behavior and React Viewer E2E remain unverified.
- GPU stress, actual renderer context loss/restoration, and target-device performance remain unverified.
- A bounded npm registry probe again failed with `EAI_AGAIN` for `registry.npmjs.org`.

## Change boundaries
No API, database, provider, credits, publication, rights, deployment, dependency-version, or lockfile changes.
