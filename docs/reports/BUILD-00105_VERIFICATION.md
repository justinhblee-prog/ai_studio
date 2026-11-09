# BUILD-00105 Verification Report

## Scope

Bounded deterministic local Photo processing for ENHANCE/LIGHTING; idempotent run lifecycle; append-only run audit; private derived image Asset, immutable AssetVersion, checksum, relation and provenance; PhotoDraftWorkspace controls.

## Commands and results

| Check | Result | Notes |
|---|---|---|
| `PYTHONPATH=. pytest -q` | PASS — 336 passed | Full backend suite |
| `PYTHONPATH=. python -m compileall -q app scripts tests` | PASS | Backend/scripts/tests compilation |
| `python scripts/validate_source.py` | PASS — 51/51 | Offline UI/source structural checks only |
| `python scripts/audit_openapi_runtime.py` | Completed; exact match false | 13 design paths vs 64 runtime paths |
| `python scripts/audit_openapi_contract.py` | Completed with known drift | 15 design operations, 12 structural drifts, 3 unmatched (credit account, ledger, quote) |
| `npm run typecheck` | NOT VERIFIED | React/Three.js modules and declarations unavailable (`TS2307`) |
| Browser/WebGL/Android E2E | NOT RUN | Browser/device runtime not provisioned |

## New local Photo tests

- ENHANCE and LIGHTING produce a new private image Asset with unchanged dimensions.
- Output has immutable AssetVersion v1, SHA-256, `derived_from` relation and `asset.photo_processed` provenance.
- Derived output is protected from ordinary deletion pending retention workflow.
- Same idempotency key/payload replays the same run and Asset; key reuse with another draft conflicts.
- BACKGROUND, RETOUCH and COMPOSE are rejected by the local processor; they require an actual AI engine.
- Multiple outputs, masks/references and prompt/style inputs are rejected rather than ignored.
- Source checksum corruption fails closed; after source repair, same key retries successfully.
- Append-only processing events reject UPDATE/DELETE.
- Viewer can read run history but cannot execute a local processing operation.

## API additions

- `POST /v1/photo-drafts/{draft_id}/process-local?workspace_id=...` (required `Idempotency-Key` header)
- `GET /v1/photo-drafts/{draft_id}/runs?workspace_id=...`
- `GET /v1/photo-drafts/{draft_id}/runs/{run_id}/events?workspace_id=...`

## Truth and product boundaries

- `is_ai_generated=false`, `provider_dispatched=false`, `credit_charged=false`.
- ENHANCE/LIGHTING are deterministic Pillow adjustments, not generative AI.
- Dimensions remain unchanged; semantic identity, text and logo preservation are not verified. Human review is required.
- BACKGROUND/RETOUCH/COMPOSE remain unavailable without an actual AI Photo Engine.
- Outputs are private derived Assets with immutable versions and provenance. No public URL, commercial-use clearance or publication permission is created.

## Remaining limitations

- Filesystem and SQLite are not one atomic transaction. Deterministic Asset IDs/checksum verification enable retry recovery; process crashes may still leave temporary/orphan files for maintenance.
- SQLite/local filesystem only; PostgreSQL, object storage, multi-host fencing and production deployment remain unverified.
- Credit Quote/Ledger policy and persistence remain unresolved. Live FASHN generation not run.
- G0-G5 remain unpassed.
