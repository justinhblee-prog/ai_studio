# BUILD-00121 Release Notes

- Adds `scripts/validate_package_integrity.py` to audit npm script targets, relative TypeScript/TSX imports and stylesheets, declared external dependencies, public entrypoint exports, and tsconfig source inclusion.
- Adds `npm run validate:package-integrity`.
- Adds four regression tests covering valid package structure, missing relative imports, undeclared external dependencies, and broken npm script targets.
- Makes the TypeScript syntax/transpilation checker recursively scan nested `src/` directories.
- No application runtime behavior, external package versions, or lockfiles changed.
- Verification: backend 359 passed; Viewer scripts 8 passed; package-integrity regression tests 4 passed; runtime Viewer JSON coverage 47/47; Viewer API contract 58/58; request contract 10/10; structural checks 65/65.
- Full semantic TypeScript checking and actual React/Three.js browser/WebGL execution remain unverified because dependencies are unavailable and headless Chromium cannot create WebGL contexts in this environment.
