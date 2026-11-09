# AI CREATOR STUDIO 3D 자산 API 계약 v0.1

상태: 초기 v0.1 설계 초안(역사 문서). 이후 runtime API가 확장되어 일부 route/field/권한/응답 계약은 이 초안과 다릅니다. 최신 구현 상태는 BUILD-00096 인수인계 및 backend README를 기준으로 확인하십시오.

## 목적

3D 뷰어의 `modelUrl`에 임의 외부 URL을 직접 넣지 않는다. 인증된 사용자 소유 자산을 API가 확인하고, 짧은 만료시간의 읽기 URL을 발급하는 구조로 연결한다.

## 리소스 모델

`Asset` 필드:

- `asset_id`: 서버 생성 UUID 기반 식별자
- `owner_id`: 인증 토큰에서 추출한 소유자 ID (요청 본문에서 받지 않음)
- `project_id`: 선택적 프로젝트 연결 ID
- `kind`: `character_model | garment_model | texture | reference_image`
- `original_filename`: 표시용 원본명, 경로로 사용 금지
- `media_type`: 서버가 시그니처 검사 후 확정한 MIME
- `size_bytes`: 서버가 실제 수신 바이트로 계산
- `sha256`: 서버 계산 해시
- `status`: `pending | ready | rejected | deleted`
- `created_at`, `updated_at`

## API

### `POST /v1/assets`

인증 필수, `multipart/form-data`의 `file`, `kind`, 선택적 `project_id`를 받는다.

응답 201: `asset_id`, `kind`, `media_type`, `size_bytes`, `status`만 반환한다. 로컬 디스크 경로나 저장소 내부 키를 노출하지 않는다.

### `GET /v1/assets`

인증 사용자 소유 자산만 페이지 단위로 반환한다. `project_id`, `kind`, `cursor`, `limit` 필터 지원.

### `GET /v1/assets/{asset_id}`

소유권 확인 후 메타데이터를 반환한다. 다른 사용자 자산은 존재 여부를 노출하지 않도록 404 처리.

### `POST /v1/assets/{asset_id}/access-url`

소유권 및 `ready` 상태 확인 후 60~300초 만료의 읽기 전용 서명 URL을 반환한다. 응답에는 `url`, `expires_at` 포함.

### `DELETE /v1/assets/{asset_id}`

소유권 확인 후 soft-delete 상태 전환. 진행 중인 프로젝트 참조/보존정책 확인 후 비동기 물리 삭제.

## 업로드 검증 필수 조건

1. 인증 및 사용자별 quota 확인을 저장 전에 수행.
2. 요청 크기 제한: 기본 100 MiB, 설정으로 조정.
3. 파일 확장자만 신뢰하지 않는다. GLB는 `glTF` magic (`67 6C 54 46`), GLTF JSON은 JSON 파싱 및 허용된 구조 검증을 한다.
4. GLTF 외부 buffer/image URI는 기본 거부하거나 동일 자산 패키지 내부 경로만 허용한다. 임의 HTTP(S), `file:`, data URL 정책은 별도 보안 검토 없이 허용하지 않는다.
5. 압축 해제·파싱 시 리소스 상한, 깊이/엔트리 수, 경로 순회 방지 적용.
6. MIME은 서버가 판정하고 클라이언트 `Content-Type`은 참고값으로만 취급.
7. private object storage에 저장하고 public static mount를 사용하지 않는다.
8. 업로드 완료 전 `pending`, 검증·저장 완료 후 `ready`; 실패 시 `rejected`와 내부 감사 이벤트 기록.
9. 모든 조회·URL 발급·삭제에서 tenant/owner 권한을 재검증.
10. 로그에 서명 URL, 토큰, 파일 본문을 기록하지 않는다.

## 프런트엔드 연결 규칙

- 업로드 응답의 `asset_id`만 프로젝트 데이터에 저장한다.
- 뷰어 진입 시 access-url API를 호출하고 반환 URL을 `Studio3DViewer.modelUrl`에 전달한다.
- URL 만료/403 시 한 번만 새 URL을 요청하고, 반복 실패는 사용자에게 명시한다.
- 클라이언트에 저장된 URL을 영구 식별자로 사용하지 않는다.

## 오류 코드

`ASSET_TOO_LARGE`, `ASSET_FORMAT_UNSUPPORTED`, `ASSET_SIGNATURE_INVALID`, `ASSET_PARSE_FAILED`, `ASSET_QUOTA_EXCEEDED`, `ASSET_NOT_FOUND`, `ASSET_ACCESS_DENIED`, `ASSET_NOT_READY`.

## 완료 기준

백엔드 구현, 소유권 테스트, 악성 GLB/GLTF fixture, 저장소 비공개 확인, 브라우저에서 업로드→목록→서명 URL→실제 뷰어 로딩→삭제까지 통합 테스트를 통과해야 완료로 표시한다.

## Implementation status update (2026-11-01, backend v0.5)

Implemented in the companion FastAPI backend: authenticated upload, owner-scoped list/detail/delete, SQLite metadata, private local filesystem storage, server-side GLB/GLTF validation, and short-lived HMAC preview URLs. The local adapter is PoC-only. Workspace IDs are owner-scoped namespaces, not yet backed by workspace membership/role authorization. The React application integration and browser-rendered GLB verification remain pending.

## Workspace RBAC update (backend v0.6)

Workspace creation and membership management are now implemented. Roles: owner/admin/editor/viewer. Owner/admin can add members; owner/admin/editor can upload and delete; all workspace members can list, inspect, and request preview URLs. Existing v0.5 asset records are bootstrapped into workspace membership on initialization (original uploader becomes owner/editor as appropriate). Membership revocation, invitations, external identity provider integration, and production RBAC audit logs remain pending.

## Backend implementation status update (BUILD-00090)

The following companion backend APIs are implemented and workspace-RBAC protected:

- `POST /v1/assets/{asset_id}/versions` — validate and store a new GLB/GLTF version, then promote it as current; previous version bytes remain immutable until asset deletion.
- `GET /v1/assets/{asset_id}/versions` — list version metadata without private storage keys.
- `GET /v1/assets/{asset_id}/provenance` — paginated upload/version/relation/delete history.
- `POST /v1/assets/{asset_id}/relations` and `GET .../relations` — typed same-workspace asset relationships.

This does not complete the browser integration acceptance criteria above. The existing React AssetWorkspace does not yet expose version history, restore, relation editing, or provenance UI. The backend is still SQLite/local-filesystem PoC scope; production object storage and distributed atomicity are not claimed.

## Image source assets and version restore (BUILD-00092)

The companion backend additionally supports `POST /v1/assets/images` for PNG/JPEG/WebP source photographs. The backend decodes the image and enforces format/extension agreement, single-frame input, maximum byte size, maximum dimension, and maximum pixel count. `GET /v1/assets?kind=model|image|all` separates model assets from source images; the 3D AssetWorkspace explicitly requests `kind=model`.

Asset versions and restore support both image and 3D model media types. A version update must keep the original asset kind. Restore verifies stored bytes and media decode, then creates a new immutable version; it never overwrites the historical version.

Photo Engine preparation endpoints are documented in the backend README. They create workspace-scoped, non-billable Photo Draft records only. No provider dispatch or image generation occurs. Active Photo Draft references prevent source-image deletion until the draft is archived.

## Product Catalog / Lookbook integration (BUILD-00096)

- `POST /v1/products` and `GET /v1/products` provide a workspace-local Product/SKU catalog with 1..12 image Asset references. SKU is unique case-insensitively within a Workspace.
- `PUT /v1/products/{product_id}`, `POST /{product_id}/archive`, and `GET /{product_id}/events` support non-destructive catalog management and append-only events.
- `LookbookDraftWorkspace` can select multiple catalog Products and/or direct product images. Active Lookbook Drafts protect referenced Products and image Assets until archive.
- Product variants, price/inventory, barcode, marketplace sync, generated outputs, review/approval and export are not implemented.


## Current implementation status correction (BUILD-00122)

The Product/Lookbook status bullets above describe the earlier BUILD-00096/00093 scope and are historical; the current cross-module feature matrix is maintained in the project-level `docs/FEATURE_SCOPE_STATUS.md`. The current implementation has since added:

- Product Variants with independently unique workspace SKUs, option-value metadata, variant-specific image selection/editing, update/archive APIs, and Lookbook Variant references.
- Lookbook planning review/approval; attachment of individually approved Photo-run outputs as exact immutable AssetVersions; optional Product/Variant association and ordered captions.
- A separate snapshot-based output-assembly review (submit/approve/reject), integrity verification, internal-only ZIP package export, expiring signed download links, and metadata manifest export.

Still not implemented: new AI-generated campaign images, live Provider execution from the Lookbook workflow, Quote/Credit charging, publication, and commercial-rights grants. The package export is explicitly internal-use-only and does not grant publication or commercial rights.
