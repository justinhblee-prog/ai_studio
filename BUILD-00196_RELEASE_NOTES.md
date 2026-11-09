# BUILD-00196 Release Notes — SQLite/PostgreSQL Migration Bundle Reliability

Date: 2026-11-05
Baseline: BUILD-00195 full handoff archive (SHA-256 and ZIP CRC verified before extraction)

## Changes

1. JSONL preflight now splits records only on literal LF (`\\n`). Python `str.splitlines()` treated valid Unicode characters U+2028, U+2029, NEL and vertical tab as line boundaries, incorrectly rejecting valid JSON strings containing those characters.
2. Export refuses a pre-existing non-empty destination directory. This prevents stale files from earlier exports from silently contaminating a newly written migration bundle.
3. Bundle version must be an actual integer and not a boolean or float. This closes Python's numeric equality loophole (`2.0 == 2`).
4. Export uses `json.dumps(..., allow_nan=False)` so Infinity/NaN cannot be emitted as non-standard JSON numeric tokens that the strict importer later rejects.
5. Added four regression tests covering Unicode separators, stale destination rejection, floating-point bundle version rejection, and non-finite REAL values.
6. Updated PostgreSQL migration guide with the new behavior and an explicit warning that the internal SHA-256 digest is not signed provenance/authentication.

## Validation

- Migration-focused suite: **35 passed, 0 failed**.
- Backend Python compileall: passed.
- Viewer source structural validation: **143 passed**.
- Viewer package integrity: **0 findings**.
- Full backend regression suite was attempted in this execution environment but did not finish within the execution window; it is not claimed as a BUILD-00196 full-suite pass. BUILD-00195 baseline was 394 passed / 0 failed.
- PostgreSQL server, `psql`, Docker/Podman and psycopg 3 remain unavailable; live import/rollback/trigger/sequence tests remain blocked.
- React/ReactDOM/Three.js dependencies remain unavailable; actual React/Three.js E2E remains blocked.
- No live AI provider call was made; no credentials, authorized inputs or cost approval were available.

## Scope

No application API, runtime database behavior, dependency manifest, lockfile, or provider configuration changed. SQLite remains the supported runtime database.
