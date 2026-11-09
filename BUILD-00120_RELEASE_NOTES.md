# BUILD-00120 Release Notes

- Adds an offline TypeScript/TSX syntax and transpilation checker for all eight Viewer source files.
- Adds `npm run validate:syntax`.
- Syntax/transpilation result: 8 files, 0 errors using TypeScript 5.8.3.
- Does not claim full semantic TypeScript type checking; React/Three.js dependencies and typings remain unavailable.
- No application behavior or dependency versions changed.
