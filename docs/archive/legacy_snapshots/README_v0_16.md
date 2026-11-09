# AI CREATOR STUDIO v0.16

Provider Capability / Policy Registry PoC layered on v0.15.

## Validation
- Backend pytest: 75 passed
- Python compileall: passed
- OpenAPI: 18 paths
- 3D Viewer structural validation: 19/19 passed

## Important
FASHN remains `DOCUMENTED` / `PENDING_CONTRACT_TEST` and is not production eligible. Mock is flow-test-only. AUTO routing is disabled pending PO approval. See `AI_CREATOR_STUDIO_P1_provider_registry_policy_notes_v0_1.md` and handoff v2.9.

## Backend
```bash
cd ai_creator_studio_backend_starter
python -m pytest -q
python -m compileall -q app tests
```

## Viewer
```bash
cd ai_creator_studio_3d_viewer
python scripts/validate_source.py
```
