# AI CREATOR STUDIO Web App — BUILD-00227

## Public entry
The Vite/React entry now renders a responsive Korean public portal homepage with Platform, Workflow, and Business sections. Login and Workspace creation CTAs open the Supabase Auth sign-in/sign-up flow. After authentication, the app verifies the user identity with FastAPI, loads or creates a Workspace, and renders the authenticated studio modules.

## Frontend environment
Create `.env.local` from `.env.example` and set:

```dotenv
VITE_API_BASE_URL=https://your-api.example.com
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_ANON_KEY=your-publishable-or-anon-key
```

The Supabase publishable/anon key is a browser key. Never put a service-role key in any `VITE_` variable.

## Local development

```bash
npm install
npm run dev
```

Backend must be running separately. Local development may use `http://localhost:8000`; non-local API endpoints must use HTTPS.

## Backend authentication configuration
Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and the exact frontend origin in `APP_CORS_ORIGINS`. When Supabase Auth is configured, the legacy `ASSET_API_TOKENS` map is not used.

## Verification boundary
BUILD-00227 adds a public portal entry and authentication/API identity bridge. It does not complete PostgreSQL persistence, live Supabase Storage transfer, Vite production build, browser E2E, AI generation, or a public deployment. See `../CURRENT_HANDOFF_BUILD-00227.md`.
