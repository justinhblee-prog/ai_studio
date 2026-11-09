# BUILD-00227 Release Notes

## Added
- Responsive public portal homepage with platform, workflow, and B2B sections.
- Login and sign-up calls to the existing Supabase Auth entry flow.
- Six product capability cards and a four-step production journey.
- Mobile/tablet layout and SEO/Open Graph metadata.

## Retained from BUILD-00226
- Supabase Auth REST login/signup/session refresh/logout.
- FastAPI token validation against Supabase Auth.
- Authenticated identity endpoint and Workspace bootstrap/selection.
- Existing API-backed workspace modules.

## Verification
- Backend pytest: 555 passed.
- Supabase Auth backend tests: 7 passed.
- Frontend Auth/API tests: 8 passed.
- Public landing contract: PASS.
- Structural checks: 143 passed.
- TypeScript syntax: 12 source + 16 declaration parses, 0 syntax errors.
- Package integrity: 0 findings.

## Not verified / not claimed
- No npm install/Vite build/browser E2E/live Supabase sign-in.
- No complete PostgreSQL persistence or live Supabase Storage transfer.
- No source-backed Vercel Preview deployment.
- No live AI generation, virtual try-on, 3D garment creation, billing, or marketplace publication.
- No Production deployment or production data mutation.
