# AI CREATOR STUDIO Web App — BUILD-00225

BUILD-00225 repairs the React/Vite app package introduced in BUILD-00224.

## Changes
- Vite entrypoint moved to `src/app/main.tsx` to keep the eight existing Viewer modules isolated for the backend API/OpenAPI contract audit.
- Relative imports corrected.
- React/ReactDOM restored as peer dependencies (and dev dependencies for the runnable app); Three.js remains a runtime dependency; TypeScript is a development dependency.
- Vite React config added with `dist` output.
- Invalid CSS font shorthand declarations corrected.

## Run locally

```bash
npm install
npm run dev
```

## Backend connection

The app shell's existing backend modules still require a reachable FastAPI API, a valid short-lived bearer token, and a workspace ID. Output Review also requires a job ID. The token remains in React memory only. The app does not fabricate backend data.

## Validation status

- Package integrity: PASS.
- TypeScript syntax/transpile: PASS (not a full typecheck).
- Dependency-free frontend unit/structural tests: PASS.
- `npm install` and `npm run build`: NOT VERIFIED because the current runner cannot resolve `registry.npmjs.org` (`EAI_AGAIN`).
- Browser E2E and live backend connection: NOT VERIFIED.
- No Vercel Preview URL has been created for this source. See `../CURRENT_HANDOFF_BUILD-00225.md` and `../BUILD-00225_VALIDATION.md`.
