# BUILD-00136 — Photo Review & Output Decision State Integrity

## Implemented
- Added a dependency-free `KeyedRequestGate` for latest-request-wins behavior per stable key.
- Photo Draft immutable AssetVersion preview hydration now ignores superseded responses for the same AssetVersion; workspace/API/token scope reset invalidates all pending preview keys.
- Serialized Photo Draft review, archive and manifest-export mutations with a synchronous in-flight gate, preventing rapid duplicate/conflicting actions and stale manifest restoration.
- Photo Draft archive immediately clears review comment and manifest state before the archive request; successful archive reload remains scope-guarded.
- Serialized Output Review decision and manifest-export mutations; scope changes release the gate and clear prior-job state.
- TypeScript syntax validation now parses every `.d.mts` declaration, not only the original request-scope declaration.
- Added seven behavioral assertions for keyed request supersession, independent keys and invalidation.

## Compatibility and safety
- No backend routes, schemas, database migrations, public component props, dependency versions, Provider behavior, credit charging, publication or rights behavior changed.
- Existing immutable AssetVersion history and archived records remain non-destructive.
- Mutation gates are UI-level duplicate/conflict guards, not backend distributed locks or guarantees against multiple clients.

## Verification
See `BUILD-00136_VERIFICATION.md` and the accompanying logs. Structural checks: 122 passed; KeyedRequestGate: 7 assertions; RequestScopeGate: 7 assertions; TypeScript syntax: 10 source files + 2 declaration parses, 0 errors; API contract 63/63; request contract 15 checked / 0 findings; response contract 51 JSON endpoints / 52 total / 28 models / 0 missing; Viewer script tests 2 passed; package integrity 0 findings; backend pytest 359 passed; Python compileall passed; clean ZIP extraction verification passed.

## Known limitations
Semantic `tsc --noEmit` and actual React/Three.js browser component E2E remain unverified because trusted React/Three.js packages and typings are not installed. PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider/credit operations, publication, rights grants and deployment remain unverified.
