# AI CREATOR STUDIO Web App — BUILD-00224

This package adds a real React/Vite application shell around the existing BUILD-00223 React modules. It does not replace the underlying workspaces.

## Run locally

Requirements: Node.js 20+, npm.

```bash
npm install
npm run dev
```

Open the Vite URL printed in the terminal.

## Connect the real backend

Use **연결 설정** in the top-right corner and enter:
- Backend API origin (default `http://localhost:8000`)
- A valid short-lived Bearer access token
- A real workspace UUID
- A job UUID for Output Review

The token is kept only in React memory and is not persisted to localStorage. The app does not fabricate API data. Without valid backend credentials, backend-powered modules will show their own empty/error states. The 3D viewer can be explored independently and uses the existing Three.js/WebGL component.

Optional API origin at build time: `VITE_API_BASE_URL`.

## Integrated existing modules

- ProjectWorkspace
- AssetWorkspace
- Studio3DViewer (real Three.js WebGL)
- ProductCatalogWorkspace
- ProjectProductAssignmentWorkspace
- PhotoDraftWorkspace
- LookbookDraftWorkspace
- OutputReviewWorkspace

## Validation status

The application shell and routing are implemented. A production bundle and browser E2E run have **not** been verified in this environment because npm dependency installation did not complete before the execution timeout. Do not treat this as a deployed or live-backend-verified application. Run `npm install`, `npm run build`, then test with a running backend and valid credentials.

No Production deployment, Supabase data mutation, or external AI provider call was performed.
