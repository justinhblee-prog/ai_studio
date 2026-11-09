# AI CREATOR STUDIO v0.59

## Legacy Job Repository Facade Reduction
- Updated `job_repository.py` documentation and removed obsolete Job/Event SQL helper implementations/imports.
- The module now exposes compatibility functions that delegate to aggregate repositories.
- Kept narrow `_connect`, `_db_path`, `_now`, and `get_storage` compatibility seams used by existing test/tool code.
- Updated Storage Port documentation to reflect the extracted SQL ownership.
- Added static tests asserting no embedded SQL statements remain in the legacy facade.

## Verification
- Backend pytest: 186 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
