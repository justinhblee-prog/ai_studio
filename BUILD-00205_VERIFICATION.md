# BUILD-00205 Verification Report

## Fresh verification

| Check | Result |
|---|---:|
| Focused API/security/assets/operations pytest | 144 passed / 0 failed |
| Full backend pytest | **468 passed / 0 failed** |
| Python compileall (`app scripts tests`) | PASS |
| Runtime OpenAPI export and `--check` | PASS |
| BUILD-00204 source ZIP SHA-256 | PASS |
| BUILD-00204 source ZIP CRC | PASS |
| BUILD-00205 ZIP CRC / SHA-256 | Verified after packaging |

## Scope

- Public health response minimized to liveness + version only.
- Added route-level auth dependency inventory test and internal-ops auth assertion.
- Added security/compatibility matrix covering workspace roles, public capability routes, signed preview semantics, platform ops, and API design/runtime drift policy.
- No PostgreSQL live test, React/Three.js E2E, or live AI provider call was attempted, per project decision.

## Important boundary

Signed asset preview URLs are short-lived bearer capabilities, not live-session authorization. An already-issued URL can remain usable until its bounded expiry (maximum 15 minutes), even if workspace membership is revoked. The authenticated preview-content endpoint is available where immediate membership re-check is required.

## Logs

- `build205_logs/backend_full_pytest.log`
- `build205_logs/compileall.log`
- `build205_logs/openapi_snapshot_check.log`
