# BUILD-00143 — Descriptor-Pinned Private File Delivery

## Highlights
- Added a shared private-file response helper that opens each file once, uses `O_NOFOLLOW` where available, verifies the opened descriptor is a regular file, and streams from that same descriptor.
- Optional expected size and SHA-256 are checked against the opened descriptor before any bytes are streamed.
- Migrated private AssetVersion previews, private asset previews, authenticated generation output downloads, and Lookbook ZIP downloads away from path-based `FileResponse`.
- Added race regression coverage proving that replacing the pathname after response construction cannot replace the bytes streamed to the client.
- Added symlink, non-regular-file, and checksum mismatch tests.
- Updated an existing Viewer structural assertion to match the actual authenticated no-store ZIP fetch contract (`headers` + `cache: no-store`).

## Compatibility and safety
- No new routes, schemas, database migrations, dependencies, Provider calls, credit behavior, publication or rights behavior.
- Existing workspace authorization and signed URL rules remain unchanged. The generation output route continues to require current Bearer authentication and current workspace membership.
- On platforms without `O_NOFOLLOW`, the helper still pins the opened descriptor and verifies it is regular, but cannot provide the same final-component symlink-open guarantee; Linux test environment supports `O_NOFOLLOW`.

## Verification
See `BUILD-00143_VERIFICATION.md` and `CURRENT_HANDOFF_BUILD-00143.md`.
