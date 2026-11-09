# BUILD-00130 — Workspace Read Lifecycle Hardening

## Summary
Extended stale-read protection across the remaining data-heavy Viewer workspaces.

## Changes
- Asset Workspace: aborts workspace-scoped list requests on unmount or API/token/workspace scope change; ignores stale asset-preview/version selection responses when users switch assets quickly.
- Photo Draft Workspace: aborts initial image/draft/run-list reads when the component scope changes or unmounts.
- Lookbook Draft Workspace: aborts initial workspace catalog/reference reads on scope change or unmount.
- Project Product Assignment Workspace: independently aborts catalog and selected-project assignment/history reads when their effect dependencies change.
- Output Review Workspace: aborts output, review-history, and nested AssetVersion preview reads on job/API/token scope change or unmount.
- Structural validation now explicitly checks these lifecycle protections.

## Compatibility
- No backend routes, schemas, database migrations, provider behavior, dependency versions, or public component props changed.
- No external Provider calls, paid APIs, publication, rights grants, or production operations were performed.
