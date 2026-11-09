# BUILD-00149 — Unknown-Length GLTF Buffer Growth Hardening

## Summary
- Replaced unknown-length response chunk retention plus final full-size copy with a capped geometric-growth `Uint8Array` accumulator.
- The accumulator starts at 64 KiB, doubles as required, and never allocates beyond the shared 256 MiB download ceiling.
- If the final payload exactly fills the capacity, the existing backing store is returned without another copy; otherwise only the exact final range is copied.
- Known-length allocation failure cancels the response body before the stream is locked; unknown-length growth failure cancels the active reader. Both surface a typed `memory` error with actionable Korean UI guidance.
- Added runtime coverage for multi-growth byte integrity, empty unknown-length responses, and known- and unknown-length allocation-failure cancellation.

## Compatibility / boundaries
- Known-length exact-size streaming behavior is unchanged.
- Unknown-length streams remain supported; `GLTFLoader.parse` still requires a contiguous `ArrayBuffer`.
- Geometric growth can briefly retain the previous and next backing stores during a resize. This reduces chunk-array retention and duplicate final assembly but is not a device-memory guarantee.
- No dependency, API/schema, database, Provider, credit, publication, rights, production data or deployment changes.
