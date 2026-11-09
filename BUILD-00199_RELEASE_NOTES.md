# BUILD-00199 Release Notes — OpenAPI drift audit completeness

Date: 2026-11-05

## Changes

- Extended `scripts/audit_openapi_contract.py` to report runtime-only operations, design/runtime operation totals, and normalized runtime-path collisions.
- Preserved disjoint HTTP methods when multiple runtime paths normalize to the same path; collisions remain explicit findings instead of silently losing one route.
- Kept the product-design OpenAPI draft unchanged. Runtime-generated OpenAPI remains the authority for implemented behavior; no unapproved API semantics or compatibility changes were introduced.
- Added regression tests for runtime-only route reporting/counts and prefix-normalization collisions.

## Current structural reconciliation

- Design draft: 15 operations.
- Runtime: 101 operations.
- Matched operations with structural drift: 12.
- Design operations absent from runtime: 3.
- Runtime-only operations absent from the design draft: 89.
- Normalized path collisions: 0.

These are structural inventory results, not semantic equivalence or live request/response conformance. Runtime-only routes may include internal/operations APIs and must not be interpreted as public API commitments.
