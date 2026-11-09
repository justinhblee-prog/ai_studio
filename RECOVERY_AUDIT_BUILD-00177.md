# BUILD-00177 Library Recovery Audit

## Finding

The earlier audit checked `/AI_CREATOR_STUDIO` as a folder and found BUILD-00166 there. A subsequent Library-root listing showed additional archives uploaded at the Library root, including BUILD-00167 through BUILD-00176. The prior conclusion that BUILD-00167–00174 were unavailable was therefore incomplete.

## Recovered archives

The following Library-root archives were materialized and extracted for source comparison:

- `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00167.zip`
- `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00168.zip`
- `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00169.zip`
- `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00170.zip`
- `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00171.zip`
- `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00172.zip`
- `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00173.zip`
- `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00174.zip`

BUILD-00175 and BUILD-00176 were also materialized. The Library BUILD-00176 ZIP SHA-256 exactly matched the previously staged BUILD-00176 archive. Each BUILD-00167–00174 ZIP passed `unzip -t` before extraction.

## Integration decision

BUILD-00174 was selected as the latest recovered source baseline. The BUILD-00176 archive did not contain several source files and tests present in BUILD-00174, including:

- `src/resourceRollback.mjs`
- `src/finalizeGltfLoad.mjs` and its declaration
- `src/reportGltfParseError.mjs`
- `scripts/test_resource_rollback.mjs`
- `scripts/test_finalize_gltf_load.mjs`
- `scripts/test_report_gltf_parse_error.mjs`
- `scripts/test_viewer_model_request_ownership.mjs`

Its `Studio3DViewer.tsx`, `webglContextLifecycle.mjs`, related structural tests, browser probe, and authenticated GLTF source-contract tests also differed. BUILD-00177 restores the complete BUILD-00174 source and test set, then overlays only the later BUILD-00175/00176 animation-frame implementation and tests. The recovered BUILD-00174 package scripts and declarations are retained.

## Historical note correction

BUILD-00175 and BUILD-00176 release notes remain unchanged as historical records of the information available during those runs. Their statement that BUILD-00167–00174 were unavailable is superseded by this BUILD-00177 audit and integrated package.

## Archive SHA-256 evidence

See `BUILD-00177_RECOVERED_ARCHIVE_SHA256.txt` for the exact SHA-256 hashes of the materialized BUILD-00167–00174, BUILD-00175, and BUILD-00176 ZIP files. The BUILD-00176 Library copy and staged copy had the same SHA-256.
