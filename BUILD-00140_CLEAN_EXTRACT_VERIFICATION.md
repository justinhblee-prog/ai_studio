# BUILD-00140 Clean Extraction Verification

The release ZIP was extracted into a new directory with no dependency installation or reuse of the working source tree.

## Results from extracted package

- Lookbook preview recovery structural checks: 15/15 PASS.
- Lookbook signed-link and stale-preview helper tests: 12 assertions PASS.
- TypeScript syntax/transpilation: 10 `.ts`/`.tsx` sources + 4 `.d.mts` declarations; 0 errors.
- Package integrity: 0 findings.
- Viewer API contract: 63/63 matched.
- Request body contract: 15 checked; 0 findings.
- Response schema contract: 51 JSON endpoints across 52 endpoints; 28 models; 0 missing routes/schemas.
- Viewer request contract tests: 2 passed.
- Backend full pytest: 359 passed in 15.17s.

The final ZIP was re-tested with `zip -T`; its SHA-256 sidecar was generated after final packaging.

## Limitation

Clean extraction verifies package completeness and repeatability of the listed automated checks. It does not substitute for semantic TypeScript typechecking or real browser-driven React/Three.js preview and ZIP download E2E.
