# BUILD-00205 Release Notes

## Security and API compatibility

- Reduced public `GET /health` to `{ok, version}`. Worker health, queue counts, and operational topology remain available only through platform-operations endpoints.
- Added route-registration security regression tests: all API routes must depend on the bearer identity resolver unless their exact method/path is in the deliberate public allowlist.
- Added a separate assertion that every `/internal/**` operation requires authentication.
- Documented workspace role matrix, public signed-preview capability semantics, platform-ops boundary, OpenAPI design/runtime compatibility policy, and production follow-up risks in `docs/security/API_SECURITY_AND_COMPATIBILITY_MATRIX_BUILD-00205.md`.
- Refreshed the generated runtime OpenAPI snapshot after the health response contract change.

## Compatibility

- Health response intentionally removes `provider_mode`, Worker counts, Outbox counts, and Poll Task counts. Operational consumers must use authenticated `/internal/ops/workers` or `/internal/ops/metrics` instead.
- No other public route contract or product design draft was changed.
