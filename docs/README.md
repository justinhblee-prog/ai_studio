# 문서 인덱스

문서는 문서의 목적과 수명에 따라 관리합니다. 매 작업마다 README, 개발기록, 인수인계 파일을 각각 새 버전으로 복제하지 않습니다.

| 문서 | 역할 | 변경 방식 |
|---|---|---|
| `../README.md` | 프로젝트 첫 화면 및 진입점 | 프로젝트 구조/현재 기준이 바뀔 때 수정 |
| `VERSIONING.md` | 제품 버전·빌드 ID·문서 버전 규칙 | 규칙 변경 시 ADR로 근거 기록 |
| `CHANGELOG.md` | 사용자/개발자 관점의 변경 요약 | 의미 있는 변경마다 append |
| `development/DEVELOPMENT_LOG.md` | 개발 작업의 상세 이력과 검증 증거 | 작업 단위로 append |
| `handoff/CURRENT_HANDOFF.md` | 다음 작업자가 읽을 단일 최신 상태 | 매 인수인계 때 갱신, 과거 사본은 만들지 않음 |
| `releases/` | 릴리스/빌드별 고정 스냅샷 노트 | 릴리스 또는 감사 가능한 빌드 기준점에서만 생성 |
| `operations/` | 운영 절차 및 안전한 유지보수 Runbook | 운영 동작/절차가 추가될 때 버전별 갱신 |
| `decisions/` | 중요한 아키텍처/제품 결정(ADR) | 결정마다 새 ADR 생성, 기존 ADR은 수정하지 않음 |
| `archive/legacy_snapshots/` | 과거의 버전별 문서 원본 | 보존 전용, 새 문서 작성 위치로 사용 금지 |

## 읽는 순서

1. 프로젝트 개요: `../README.md`
2. 현재 상태와 다음 작업: `handoff/CURRENT_HANDOFF.md`
3. 변경 내역: `CHANGELOG.md`
4. 세부 구현 및 테스트 이력: `development/DEVELOPMENT_LOG.md`
5. 과거 문서 확인이 필요할 때만 `archive/legacy_snapshots/` 검색

## Product baseline and scope audit

- Request/response contract drift: `reports/BUILD-00090_openapi-contract-drift.json`
- Generated runtime OpenAPI snapshot: `reports/BUILD-00090_runtime-openapi.json`

- Imported product/design references: `product-baseline/`
- Runtime implementation coverage and OpenAPI drift: `reports/BUILD-00088_PRODUCT_SCOPE_IMPLEMENTATION_AUDIT.md`

## 운영 Runbook

- Output artifact 유지보수 및 crash residue 복구: `operations/OUTPUT_ARTIFACT_MAINTENANCE_RUNBOOK_v0_1.md`
- Live FASHN sandbox smoke: `../ai_creator_studio_backend_starter/README.md#opt-in-live-fashn-sandbox-smoke`
- OpenAPI/runtime route drift audit: `../ai_creator_studio_backend_starter/scripts/audit_openapi_runtime.py`

## 모듈 문서

Backend와 Viewer 내부의 `docs/`는 해당 모듈의 운영/구현 문서로 유지합니다. 프로젝트 공통 버전·인수인계 문서는 이 디렉터리에서만 관리합니다.

## Latest engineering evidence (BUILD-00149)

- Release: `releases/BUILD-00149.md`
- Verification: `reports/BUILD-00149_VERIFICATION.md`
- Current handoff: `handoff/CURRENT_HANDOFF.md`

## Latest engineering evidence (BUILD-00113)

- Release: `releases/BUILD-00113.md`
- Verification: `reports/BUILD-00113_VERIFICATION.md`
- Runtime OpenAPI snapshot: `api/openapi.runtime.v1.json`
- Reconciliation decisions: `api/OPENAPI_CONTRACT_RECONCILIATION_BUILD-00113.md`
- Contract drift report: `reports/BUILD-00113_openapi-contract-drift.json`
- Runtime inventory: `reports/BUILD-00113_runtime-openapi.json`

## Latest engineering evidence (BUILD-00093)

- Release summary: `releases/BUILD-00093.md`
- Verification and command evidence: `reports/BUILD-00093_VERIFICATION.md`
- Product scope classification: `reports/BUILD-00093_PRODUCT_SCOPE_STATUS.md`
- OpenAPI route inventory: `reports/BUILD-00093_openapi-runtime-drift.json`
- OpenAPI schema contract drift: `reports/BUILD-00093_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00093_runtime-openapi.json`
- TypeScript dependency failure evidence: `reports/BUILD-00093_typescript-typecheck.log`

## Latest pagination milestone (BUILD-00094)

- Release: `releases/BUILD-00094.md`
- Verification: `reports/BUILD-00094_VERIFICATION.md`
- OpenAPI route inventory: `reports/BUILD-00094_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00094_openapi-contract-drift.json`
- TypeScript attempt: `reports/BUILD-00094_typescript-typecheck.log`

## Latest relation integrity milestone (BUILD-00095)

- Release: `releases/BUILD-00095.md`
- Verification: `reports/BUILD-00095_VERIFICATION.md`
- OpenAPI route inventory: `reports/BUILD-00095_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00095_openapi-contract-drift.json`
- TypeScript attempt: `reports/BUILD-00095_typescript-typecheck.log`
- Clean extracted-package test logs: `reports/BUILD-00095_package-verification.log`, `reports/BUILD-00095_package-viewer-validation.log`

## Latest Product / SKU milestone (BUILD-00096)

- Release: `releases/BUILD-00096.md`
- Verification: `reports/BUILD-00096_VERIFICATION.md`
- Product scope: `reports/BUILD-00096_PRODUCT_SCOPE_STATUS.md`
- OpenAPI route inventory: `reports/BUILD-00096_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00096_openapi-contract-drift.json`
- TypeScript attempt: `reports/BUILD-00096_typescript-typecheck.log`
- Clean extracted-package test logs: `reports/BUILD-00096_package-verification.log`, `reports/BUILD-00096_package-viewer-validation.log`


## Latest engineering milestone (BUILD-00104)

- Release: `releases/BUILD-00104.md`
- Verification: `reports/BUILD-00104_VERIFICATION.md`
- Backend test log: `reports/BUILD-00104_verification.log`
- Viewer structural validation: `reports/BUILD-00104_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00104_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00104_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00104_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00104_typescript-typecheck.log`
- Clean ZIP extraction tests: `reports/BUILD-00104_package-verification.log`, `reports/BUILD-00104_package-viewer-validation.log`


## Latest engineering milestone (BUILD-00105)

- Release: `releases/BUILD-00105.md`
- Verification: `reports/BUILD-00105_VERIFICATION.md`
- Backend test log: `reports/BUILD-00105_verification.log`
- Viewer structural validation: `reports/BUILD-00105_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00105_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00105_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00105_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00105_typescript-typecheck.log`
- Clean ZIP extraction tests: `reports/BUILD-00105_package-verification.log`, `reports/BUILD-00105_package-viewer-validation.log`


## Latest engineering milestone (BUILD-00106)

- Release: `releases/BUILD-00106.md`
- Verification: `reports/BUILD-00106_VERIFICATION.md`
- Backend test log: `reports/BUILD-00106_verification.log`
- Viewer structural validation: `reports/BUILD-00106_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00106_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00106_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00106_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00106_typescript-typecheck.log`


## Latest engineering milestone (BUILD-00107)

- Release: `releases/BUILD-00107.md`
- Verification: `reports/BUILD-00107_VERIFICATION.md`
- Backend test log: `reports/BUILD-00107_verification.log`
- Viewer structural validation: `reports/BUILD-00107_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00107_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00107_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00107_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00107_typescript-typecheck.log`


## Latest engineering milestone (BUILD-00108)

- Release: `releases/BUILD-00108.md`
- Verification: `reports/BUILD-00108_VERIFICATION.md`
- Backend test log: `reports/BUILD-00108_verification.log`
- Viewer structural validation: `reports/BUILD-00108_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00108_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00108_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00108_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00108_typescript-typecheck.log`


## Latest engineering milestone (BUILD-00108)

- Release: `releases/BUILD-00108.md`
- Verification: `reports/BUILD-00108_VERIFICATION.md`
- Backend test log: `reports/BUILD-00108_verification.log`
- Viewer structural validation: `reports/BUILD-00108_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00108_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00108_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00108_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00108_typescript-typecheck.log`
- Clean ZIP extraction tests: `reports/BUILD-00108_package-verification.log`, `reports/BUILD-00108_package-viewer-validation.log`


## Latest engineering milestone (BUILD-00109)

- Release: `releases/BUILD-00109.md`
- Verification: `reports/BUILD-00109_VERIFICATION.md`
- Backend test log: `reports/BUILD-00109_verification.log`
- Viewer structural validation: `reports/BUILD-00109_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00109_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00109_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00109_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00109_typescript-typecheck.log`


## Latest engineering milestone (BUILD-00109)

- Release: `releases/BUILD-00109.md`
- Verification: `reports/BUILD-00109_VERIFICATION.md`
- Backend test log: `reports/BUILD-00109_verification.log`
- Viewer structural validation: `reports/BUILD-00109_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00109_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00109_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00109_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00109_typescript-typecheck.log`
- Clean ZIP extraction tests: `reports/BUILD-00109_package-verification.log`, `reports/BUILD-00109_package-viewer-validation.log`


## Latest engineering milestone (BUILD-00110)

- Release: `releases/BUILD-00110.md`
- Verification: `reports/BUILD-00110_VERIFICATION.md`
- Backend test log: `reports/BUILD-00110_verification.log`
- Viewer structural validation: `reports/BUILD-00110_viewer-structural-validation.log`
- TypeScript attempt: `reports/BUILD-00110_typescript-typecheck.log`


## Latest engineering milestone (BUILD-00110)

- Release: `releases/BUILD-00110.md`
- Verification: `reports/BUILD-00110_VERIFICATION.md`
- Backend test log: `reports/BUILD-00110_verification.log`
- Viewer structural validation: `reports/BUILD-00110_viewer-structural-validation.log`
- TypeScript attempt: `reports/BUILD-00110_typescript-typecheck.log`
- Clean ZIP extraction tests: `reports/BUILD-00110_package-verification.log`, `reports/BUILD-00110_package-viewer-validation.log`


## Latest engineering milestone (BUILD-00111)

- Release: `releases/BUILD-00111.md`
- Verification: `reports/BUILD-00111_VERIFICATION.md`
- Backend test log: `reports/BUILD-00111_verification.log`
- Viewer structural validation: `reports/BUILD-00111_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00111_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00111_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00111_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00111_typescript-typecheck.log`
- Expired export cleanup dry-run: `reports/BUILD-00111_export-cleanup-dry-run.log`


## Latest engineering milestone (BUILD-00111)

- Release: `releases/BUILD-00111.md`
- Verification: `reports/BUILD-00111_VERIFICATION.md`
- Backend test log: `reports/BUILD-00111_verification.log`
- Viewer structural validation: `reports/BUILD-00111_viewer-structural-validation.log`
- OpenAPI route inventory: `reports/BUILD-00111_openapi-runtime-drift.json`
- OpenAPI contract drift: `reports/BUILD-00111_openapi-contract-drift.json`
- Runtime OpenAPI snapshot: `reports/BUILD-00111_runtime-openapi.json`
- TypeScript attempt: `reports/BUILD-00111_typescript-typecheck.log`
- Cleanup dry-run: `reports/BUILD-00111_export-cleanup-dry-run.log`
- Clean ZIP extraction tests: `reports/BUILD-00111_package-verification.log`, `reports/BUILD-00111_package-viewer-validation.log`, `reports/BUILD-00111_package-cleanup-dry-run.log`


## Latest engineering build

- `BUILD-00112`: hardened Lookbook export retention cleanup. See `handoff/CURRENT_HANDOFF.md` and `releases/BUILD-00112.md`.


## Latest engineering evidence (BUILD-00121)

- Release: `../BUILD-00121_RELEASE_NOTES.md`
- Verification: `../BUILD-00121_VERIFICATION.md`
- Verification log: `../BUILD-00121_VERIFICATION.log`
- Runtime endpoint coverage: `../BUILD-00121_RUNTIME_COVERAGE.log`
- Current handoff: `handoff/CURRENT_HANDOFF.md`


## Current product scope

- Feature implementation and verification boundaries: `FEATURE_SCOPE_STATUS.md`
- Latest engineering evidence: BUILD-00123 (browser WebGL2 capability probe)


## Latest browser capability evidence (BUILD-00123)

- Optional WebGL2 probe: `../ai_creator_studio_3d_viewer/scripts/probe_browser_runtime.py`
- Optional dependency: `../ai_creator_studio_3d_viewer/requirements-browser-audit.txt`
- Scope and limitations: `FEATURE_SCOPE_STATUS.md`


## Latest engineering evidence (BUILD-00123)

- Release: `../BUILD-00123_RELEASE_NOTES.md`
- Verification: `../BUILD-00123_VERIFICATION.md`
- Browser probe: `../ai_creator_studio_3d_viewer/scripts/probe_browser_runtime.py`
- Current handoff: `handoff/CURRENT_HANDOFF.md`


## Latest feature implementation evidence (BUILD-00124)

- Product Variant image selection/editing in `../ai_creator_studio_3d_viewer/src/ProductCatalogWorkspace.tsx`
- Updated API/request/response contract audits in `../ai_creator_studio_3d_viewer/docs/`
- Verification: `../BUILD-00124_VERIFICATION.md`


## Latest Product Catalog workflow evidence (BUILD-00125)

- Product create/edit UI: `../ai_creator_studio_3d_viewer/src/ProductCatalogWorkspace.tsx`
- Updated Viewer API/request/response contract audits: `../ai_creator_studio_3d_viewer/docs/`
- Verification: `../BUILD-00125_VERIFICATION.md`


## Latest Project Workspace evidence (BUILD-00126)

- Component: `../ai_creator_studio_3d_viewer/src/ProjectWorkspace.tsx`
- Export: `../ai_creator_studio_3d_viewer/src/index.ts`
- Verification: `../BUILD-00126_VERIFICATION.md`


## Latest Project Workspace implementation (BUILD-00126)

- ProjectWorkspace component: `../ai_creator_studio_3d_viewer/src/ProjectWorkspace.tsx`
- Release notes: `../BUILD-00126_RELEASE_NOTES.md`
- Verification: `../BUILD-00126_VERIFICATION.md`
- Current handoff: `handoff/CURRENT_HANDOFF.md`


## Latest engineering milestone (BUILD-00131)

- Release: `releases/BUILD-00131.md`
- Verification: `reports/BUILD-00131_VERIFICATION.md`
- Current handoff: `handoff/CURRENT_HANDOFF.md`


## Latest engineering evidence (BUILD-00142)

- Release: `releases/BUILD-00142.md`
- Verification: `../BUILD-00142_VERIFICATION.md`
- Handoff: `handoff/CURRENT_HANDOFF.md`
- Runtime OpenAPI snapshot: `api/openapi.runtime.v1.json`


## Current project handoff — BUILD-00156 (2026-11-04)

- Full project status and transfer guide: `../PROJECT_STATUS_AND_HANDOFF_BUILD-00156.md`
- Current handoff: `../CURRENT_HANDOFF.md`
- Detailed build handoff: `../AI_CREATOR_STUDIO_HANDOFF_BUILD-00156.md`
- Integrated design: `../PROJECT_DESIGN.md`
- Next roadmap: `../ROADMAP_BUILD-00157.md`
- Full scope warning: designed product breadth exceeds the verified implementation scope; consult the current status matrix.
