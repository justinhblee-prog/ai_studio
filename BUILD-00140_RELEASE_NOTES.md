# BUILD-00140 Release Notes

## Lookbook preview and download recovery

- Added per-output immutable AssetVersion preview loading, expiry and error state to Lookbook assembly.
- Added exact-version preview URL refresh/retry and stale image-error protection with keyed request sequencing.
- Corrected package expiry presentation: the 15-minute signed download URL expiry is distinct from the 24-hour private package retention expiry.
- Added download expiry preflight, no-store ZIP fetch, Blob-based browser download, visible download errors and explicit new-package/new-link reissue.
- Added 12 helper assertions and 15 source structural assertions. Strengthened the backend integration test to verify preview refresh is presentation-only and exact AssetVersion identity persists into the approved package manifest and ZIP filename.

## Scope and safety

- No backend/API/schema/database changes or dependency version changes.
- No Provider dispatch, credit charge, publication, public distribution, or commercial-rights grant.
- Internal ZIP export remains gated by planning and assembly approval and is internal-use-only.

## Verification boundary

- Backend: 359 tests passed; Python compileall passed.
- Viewer: API contract 63/63; request contract 15 checked/0 findings; response schema 51 JSON endpoints across 52 total/28 models; syntax 10 sources + 4 declarations/0 errors; package integrity 0 findings.
- Browser-driven React component E2E, real signed URL expiry and actual Blob download remain unverified.
