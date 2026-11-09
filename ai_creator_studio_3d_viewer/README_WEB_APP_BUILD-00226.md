# AI CREATOR STUDIO Web App — BUILD-00226

## Application entry
The Vite/React entry now presents a responsive public portal homepage, Supabase email/password authentication, and the authenticated studio workspace. After authentication it verifies the user identity with the FastAPI backend, loads or creates a Workspace, and passes the access token and Workspace ID into the existing workspace modules.

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
Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `APP_CORS_ORIGINS` in the backend environment. When Supabase Auth is configured, the legacy `ASSET_API_TOKENS` map is not used.

## Verification boundary
BUILD-00226 adds the public portal entry, authentication and API identity bridge. It does not complete PostgreSQL persistence, live Supabase Storage transfer, the Vite production build, browser E2E, or a public deployment. See `../CURRENT_HANDOFF_BUILD-00226.md`.
