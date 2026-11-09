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
