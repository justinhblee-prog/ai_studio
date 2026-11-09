# Browser E2E

Drives the **release web build** in headless Chromium against a **local SQLite backend** started by the harness
(`PROVIDER_MODE=mock`; no external image provider, no credits).

What is real and what is mocked:
- Real: the web app bundle, the FastAPI backend, SQLite, the file storage, the deterministic local image processing,
  the Lookbook ZIP export.
- **Mocked: Supabase Auth.** The harness intercepts the browser's calls to `e2e-mock.supabase.test`; the backend validates
  the bearer tokens through `ASSET_API_TOKENS`. Real Supabase login is not exercised.
- Not exercised: any AI provider, 3D viewer, payments.

Run locally:

```bash
cd ai_creator_studio_3d_viewer
npm ci && npm install --no-save playwright@1.63.0 && npx playwright install chromium   # skip the last two if Playwright is already installed
VITE_API_BASE_URL=http://127.0.0.1:8765 VITE_SUPABASE_URL=https://e2e-mock.supabase.test VITE_SUPABASE_ANON_KEY=e2e-anon-not-a-secret npm run build
node e2e/pilot_flow.mjs
```

`rights_flow.mjs` runs the same stack with `ASSET_REQUIRE_RIGHTS_CONFIRMATION=true` and checks the image-upload rights / likeness
declaration (refusal messages, recorded provenance). Run it after the build, the same way as `pilot_flow.mjs`.

`roles_flow.mjs` seeds one shared workspace through the API (owner, editor, viewer; one image, one processed photo run) and checks six
scenarios in the browser: viewer cannot upload or approve, editor can upload but cannot approve, owner approves in the UI, an outsider is
refused on every read and write (API) and sees none of the shared data (UI), and a 390 px wide screen has no horizontal overflow.
Supabase Auth is mocked as in the other flows.

`disclosure_flow.mjs` (L-07) checks the AI-generated label of provider job outputs in the review screen and in the internal manifest.
**The mock provider never produces an image, so the finished job output is seeded** (`seed_job_output.py`, the same method the backend unit
tests use) and the real provider path is not exercised.

`legal_flow.mjs` (L-02 / L-01 screens) drives the legal acceptance gate (the studio is not rendered behind it; every required box is needed; the optional AI-training consent is off by default and is recorded only when ticked), withdrawing that consent in settings, re-acceptance after a document version changes (simulated by editing the stored acceptance, not by restarting the server with a new version), and an account deletion request (recorded only, nothing deleted; cancellable). The other flows pass through the same gate via `loginThroughUi`. The legal documents are drafts and their text is not in the app; the gate says so.

`account_flow.mjs` runs four API-level flows against the real backend over HTTP (no browser page, because none of these has a screen yet): legal acceptance (current vs stale version), deletion requests (create, replay, list, cancel, privacy between users, owner-only workspace scope), and the Character reference guard on asset deletion. It does not prove any screen exists.

`layout_flow.mjs` visits seven screens at ten viewport widths (360-1280 px) and fails if any page is wider than the viewport. The 3D studio
(WebGL) and the job review screen (needs a job) are not covered; the bottom navigation bar of phone widths scrolls sideways on purpose and is
not counted (only the page's own scroll width is).
