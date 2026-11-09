# BUILD-00133 Release Notes

## Nested async read race protection

- Photo Draft reload hydration now rejects older concurrent list/run reads using a monotonically increasing request sequence.
- Project Product Assignment now independently sequences catalog and assignment reads and verifies the selected project identity before applying assignment/history data.
- Output Review now sequences the entire outputs → review history → immutable AssetVersion preview hydration chain.
- Product Catalog's existing sequence and workspace identity guards were reviewed and retained.

## Compatibility and scope

- No backend/API/schema/database changes.
- No dependency or lockfile changes.
- No public component prop changes.
- No provider, credit, publication, or rights behavior changes.

## Verification

See `BUILD-00133_VERIFICATION.md` and `BUILD-00133_CLEAN_EXTRACT_VERIFICATION.md` for the exact commands and results. Structural validation is not a substitute for runtime React component tests or semantic TypeScript typechecking.
