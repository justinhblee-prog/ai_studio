# BUILD-00107 Verification Report

## Scope

Signed exact-AssetVersion preview, Photo Draft source version pinning, source checksum integrity, deterministic local run/idempotency lineage, and exact-version preview UI.

## Commands and results

| Check | Result | Notes |
|---|---|---|
| `PYTHONPATH=. pytest -q` | PASS — 339 passed | Full backend suite |
| `PYTHONPATH=. python -m compileall -q app scripts tests` | PASS | Backend/scripts/tests compilation |
| `python scripts/validate_source.py` | PASS — 56/56 | Offline UI/source structural checks only |
| `python scripts/audit_openapi_runtime.py` | Completed; exact match false | 13 design paths vs 71 runtime paths |
| `python scripts/audit_openapi_contract.py` | Completed with known drift | 15 design operations, 12 structural drifts, 3 unmatched (credit account, ledger, quote) |
| `npm run typecheck` | NOT VERIFIED | React/Three.js modules and declarations unavailable (`TS2307`) |
| Browser/WebGL/Android E2E | NOT RUN | Browser/device runtime not provisioned |

## New verification

- Version preview URL signs `(asset_id, version_id, expires)` and denies tampered/expired signatures.
- Version preview serves v1 bytes after v2 becomes current; ordinary Asset preview serves v2.
- Version preview verifies storage path containment, file existence, size and SHA-256 before serving.
- Photo Draft stores source AssetVersion ID/checksum at create/update.
- A local Photo run created from a draft pinned to v1 continues to read v1 after v2 upload; run fingerprint and derived provenance include v1 ID/checksum.
- Same idempotency key replays the same output after current source version changes.
- PhotoDraftWorkspace and OutputReviewWorkspace request exact-version signed previews.

## API additions

- `POST /v1/assets/{asset_id}/versions/{version_id}/preview-url`
- `GET /v1/assets/{asset_id}/versions/{version_id}/preview`

## Security and product boundaries

- Preview URLs are short-lived, signed, private read URLs with `private, no-store` and `nosniff` response headers.
- Preview does not publish assets or grant distribution/commercial rights.
- Photo ENHANCE/LIGHTING remains deterministic Pillow adjustment, not generative AI. No Provider call or credit charge is made.

## Remaining limitations

- SQLite/local filesystem only; PostgreSQL, object storage, multi-host fencing and production deployment remain unverified.
- Credit Quote/Ledger policy and persistence remain unresolved; live FASHN generation not run.
- TypeScript/browser/WebGL/Android E2E not verified; G0-G5 remain unpassed.
