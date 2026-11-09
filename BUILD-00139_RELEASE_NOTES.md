# BUILD-00139 — Immutable AssetVersion Preview Recovery

- Photo Draft now tracks preview request loading/error/expiry per exact `asset_id:version_id` key. It stores the signed preview `expires_at`, clears stale URLs before reissue, shows retryable errors, and exposes explicit refresh/retry actions for source and processed output previews.
- Failed image loads invalidate only the matching current URL/request, clear the failed URL, and present a retry action to obtain a fresh signed URL. A delayed `onError` from an older URL cannot invalidate a newer preview URL.
- Output Review now tracks preview error/loading/expiry per output, reports missing immutable AssetVersion links, and offers explicit preview reissue/retry for the exact `review.output.asset_id` + `asset_version_id`.
- Output Review uses `KeyedRequestGate` to prevent a slower automatic preview hydration from overwriting a newer manual retry. Refreshing the output list clears old preview state before rehydrating current review metadata.
- No backend routes/schemas, database migrations, dependencies, Provider calls, credit behavior, publication or rights behavior changed.
