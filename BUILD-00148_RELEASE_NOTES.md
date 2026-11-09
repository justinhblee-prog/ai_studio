# BUILD-00148 Release Notes

## Lower peak memory for known-length GLB/GLTF downloads
- The bounded authenticated model reader now validates `Content-Length` as a non-negative decimal integer. Invalid, negative, fractional, and empty values fail closed rather than being treated as unknown length.
- A declared size above 256 MiB cancels the response body before reading, rather than merely rejecting the response and leaving the stream unconsumed.
- For valid known-length responses, the reader allocates the exact final `Uint8Array` once and copies incoming chunks directly into it. This avoids retaining a second full set of chunks plus a second full-size final buffer.
- The reader rejects and cancels a stream that exceeds its declared length, as well as the global 256 MiB cap. Truncated responses remain typed network failures.
- Unknown-length streams remain supported with bounded chunk accumulation and a final contiguous buffer, because `GLTFLoader.parse` still requires an `ArrayBuffer`.
- Added runtime coverage for exact-size allocation behavior, zero-length responses, invalid lengths, preflight cancellation, and declared-length overflow.
- No dependencies, API/schema, database, Provider, credit, publication, rights, production data, or deployment changes.

## Verification
- Backend full pytest: 367 passed.
- Bounded download structural: 15/15; executable runtime: 12/12; authenticated GLTF: 9/9.
- RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle: 4; Lookbook signed-link: 12; Lookbook recovery: 19/19.
- Viewer API contract: 63/63; request-body contract: 15 checked / 0 findings; response contract: 50 JSON / 52 total / 28 models / 0 missing.
- TypeScript syntax: 10 source + 6 declaration files, 0 syntax errors; package integrity: 0 findings; Python compileall passed.
- Clean ZIP extraction verification reruns core backend, viewer runtime, contracts, syntax, and package checks.

## Limitations
- React/Three.js browser E2E, visible model rendering, semantic TypeScript, device memory profiling, PostgreSQL runtime/multi-host, Android, production storage/security, live Provider/credit, publication, rights and deployment remain unverified.
- Unknown-length streams still require chunk accumulation plus a contiguous final buffer. All GLTF parsing still requires a complete contiguous `ArrayBuffer`; 256 MiB is not a device compatibility guarantee.
