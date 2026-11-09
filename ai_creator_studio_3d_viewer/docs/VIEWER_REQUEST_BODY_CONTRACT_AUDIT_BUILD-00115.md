# Viewer Request Body Contract Audit — BUILD-00115

## Summary

Compared all literal JSON request bodies found in the seven Viewer TSX source files with the FastAPI runtime OpenAPI snapshot committed in BUILD-00113.

## Findings

| Check | Result |
|---|---:|
| JSON body call sites | 10 checked |
| Unresolved call sites | 0 |
| Unknown fields | 0 |
| Missing required fields | 0 |
| Enum mismatches | 0 |
| Regression tests | 2 passed |

The validator recognizes JavaScript/TypeScript shorthand properties (for example `operation` and `option_values`) and nested object/array values. It resolves dynamic review actions only where their request schema is compatible, and records equivalent operation candidates in the machine-readable report.

## Enum parity

- `PhotoOperation` = `ENHANCE`, `BACKGROUND`, `LIGHTING`, `RETOUCH`, `COMPOSE`; exact match with `PhotoDraftInput.operation`.
- `OutputFormat` = `PNG`, `JPEG`, `WEBP`; exact match with `PhotoDraftInput.output_format`.

## Scope limits

This is a static structural audit, not a TypeScript compiler. It does not prove every state expression's runtime scalar value meets Pydantic constraints, nor does it cover multipart FormData requests. TypeScript typecheck and real browser integration remain separate verification gates.
