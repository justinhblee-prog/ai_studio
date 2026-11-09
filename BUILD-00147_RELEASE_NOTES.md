# BUILD-00147 Release Notes

## Executable bounded model download reader
- `Studio3DViewer` now imports a shared bounded reader from `src/boundedModelDownload.mjs` instead of owning inline stream logic.
- Added `src/boundedModelDownload.d.mts` so TypeScript consumers receive explicit response/error types.
- Added Node built-in Fetch/ReadableStream tests; no runtime or development dependencies added.
- Detects declared-vs-received length mismatch before parsing, preventing incomplete payloads from being handed to GLTFLoader.

## Verification
- Backend: 367 passed.
- Bounded download structural: 15/15; runtime: 9/9.
- Authenticated GLTF: 9/9.
- Viewer API: 63/63; request body 15/0 findings; response 50 JSON / 52 total / 28 models.
- TypeScript syntax: 10 sources + 6 declarations, 0 errors.
- Package integrity: 0 findings.

## Limitations
Browser React/Three E2E, semantic TypeScript, production-size memory profiling, PostgreSQL multi-host, Android, production storage/security, live provider/credit, publication, rights and deployment remain unverified.
