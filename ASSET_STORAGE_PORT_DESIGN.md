# ASSET_STORAGE_PORT_DESIGN — Assets 라우트 어댑터 설계 (2026-11-08)

## 1. 범위 분리
Assets 라우트는 **(A) 메타데이터**와 **(B) 파일 바이트**가 한 함수 안에 섞여 있다. 한 번에 포트화하지 않고 둘로 나눈다.

| 단위 | 내용 | 상태 |
|---|---|---|
| A. AssetMetadataPort | get/list(공개 형태), 버전 목록, 출처(provenance) 목록, 관계 생성/조회, 삭제 보호, 권한 | 이번 단위 |
| B. AssetBytesPort | `save_asset`, `create_asset_version`, `restore_asset_version`, `audit_workspace_assets`, 서명 미리보기, `storage_path`, 파생 이미지 저장 | 다음 단위(설계만 확정) |

## 2. SQLite(레거시 계약) ↔ PG 차이표 (코드로 확인한 것)
| # | 항목 | SQLite(계약) | PG(수정 전) | 처리 |
|---|---|---|---|---|
| 1 | 삭제 보호 | 생성 출력물·활성 상품·활성 변형·활성 Photo/Lookbook 초안이 참조하면 거부(422 ValueError) | **보호 없음 — 활성 상품이 쓰는 이미지도 삭제 가능(결함)** | A에서 수정 |
| 2 | 삭제 출처 이벤트 | `asset.deleted` `{"source":"user_delete"}` version=NULL | `asset.soft_deleted` `{"soft_delete":true}` | A에서 맞춤 |
| 3 | 업로드 출처 이벤트 | `asset.uploaded` `{"source":"upload"}` | `asset.registered` `{"source":"metadata_adapter"}` | A에서 맞춤 |
| 4 | 공개 형태 | `storage_key` 제거, `asset_kind`, `embedded_binary` bool, 이미지는 `gltf_version=None` | 원본 행 그대로 | 포트에서 변환 |
| 5 | kind=model 필터 | `model/%` | `model/%` 또는 octet-stream/gltf-buffer | 계약(SQLite)에 맞춤 |
| 6 | 버전 목록 | 컬럼 부분집합 + `is_current`, 번호 내림차순 | 원본 행(`storage_key` 노출) | 포트에서 변환 |
| 7 | 출처 목록 | `details`(dict) | `details_json` 컬럼명 | 포트에서 변환 |
| 8 | 관계 생성 | `derived_from` 순환 검사, 양쪽에 `relation_created/received` 이벤트, 자산 없음→404 | 순환 검사 없음, 이벤트 없음, 자산 없음→422, 중복은 기존 행 반환 | A에서 수정 |
| 9 | 관계 목록 정렬 | `created_at DESC` | `created_at ASC` | A에서 맞춤 |
| 10 | 권한 오류 | 비멤버 404 / 낮은 역할 403 | 일반 PermissionError | 타입 오류로 교체 |
| 11 | 버전 생성 | 파일 쓰기+행 삽입 한 트랜잭션, `original_filename/gltf_version/embedded_binary` 갱신, `previous_version` 기록 | 메타데이터만, 위 3개 컬럼 미갱신 | B에서 처리 |
| 12 | 없는 메서드 | `workspace_for_asset`, `get_asset_version_record`, `restore_asset_version`, `audit_workspace_assets`, `storage_path`, `save_derived_image_asset` | 없음 | `workspace_for_asset`·`get_asset_version_record`는 A, 나머지는 B |

## 3. 파일↔행 원자성 규칙 (B 단위의 전제)
1. 행 삽입이 **실패하면 방금 쓴 파일을 지운다**(SQLite 구현이 이미 그렇게 함).
2. 삭제는 **행 커밋 후** 파일을 지운다. 지우기에 실패하면 행은 삭제된 채 파일이 남는 고아가 되므로 정리 작업이 가능해야 한다.
3. 버전 파일은 불변: 키는 `{asset_id}_{version_id}{suffix}`, `open("xb")`로 덮어쓰기 금지.
4. 무결성(크기·SHA-256)은 읽을 때마다 재계산(`_verified_version_path`)하며 경로 탈출(`path.parent != root`)을 거부.
5. PG 런타임에서는 같은 규칙을 Supabase Storage 객체에 적용해야 하며, 이는 TEST 환경 없이는 검증 불가 → **로컬 디스크 구현으로만 검증하고 Supabase 구현은 미검증으로 표기**.

## 4. 순서
A(메타데이터 포트+PG 보강+동등성/변이 시험) → B(바이트 포트, 로컬 디스크 구현으로 동등성 시험) → 라우트 전환 → Photo/Lookbook.

## 5. 진행 상태 (2026-11-09)
- A(메타데이터 포트): 완료, SQLite↔PG 동등성 + 변이 12종 적발.
- B(바이트 포트): 완료 범위 = 업로드(`save`), 새 버전(`save_version`), 복원(`restore`), 무결성 감사(`audit`), 삭제 시 파일 제거, 현재 파일 조회. 로컬 디스크(`LocalBlobStore`)만 구현·검증. 변이 12종 적발(실패 시 고아 파일 없음, 덮어쓰기 거부, 경로 탈출 거부, 크기/체크섬 검증, 삭제 시 파일 제거 포함).
- 남음: `save_derived_image_asset`(Photo 엔진 단계에서), 라우트 내 `_verified_version_path` 로컬 경로 코드의 BlobStore 이관, Supabase Storage 구현(검증 불가).
