# BUILD-00134 Release Notes

## Dependency-Free Request Scope Lifecycle Gate

- Extracted request-scope token lifecycle into a small dependency-free module shared by the Viewer React hook.
- Scope identity changes invalidate previously captured async callbacks; unmount invalidates all outstanding tokens; remount activation permits only newly captured work.
- Added `.d.mts` type declaration for correct TypeScript resolution of the `.mjs` runtime module.
- Added a Node built-in behavioral test with 7 assertions and an npm script (`test:scope-gate`).
- Expanded structural validation to 113 checks.

## Compatibility and safety

- No backend/API/database contract changes.
- No new third-party dependencies or dependency version changes.
- No live Provider, paid API, credit, publication, rights-grant, or deployment operation.
- Existing `useRequestScope` public hook shape remains `{ capture, isCurrent }`.

## Verification

- 113 structural checks passed.
- 7 RequestScopeGate behavioral assertions passed.
- TypeScript syntax/transpilation: 10 source files + declaration parse, 0 errors.
- API 63/63; request body 15 checked / 0 findings; response schema 51 JSON endpoints / 52 total endpoints.
- Viewer Python script tests 8 passed; package integrity 0 findings.
- Backend pytest 359 passed; Python compileall passed.
- Clean ZIP extraction verification completed separately.

Semantic TypeScript type checking and actual React/Three.js component E2E remain unverified due unavailable trusted dependencies/typings.
