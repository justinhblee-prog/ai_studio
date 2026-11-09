# NEXT_SESSION_START — 새 세션 인수인계 (2026-11-09 기준, 동시성 4차 반영) — 주의: 이 변경들은 아직 GitHub main에 없음. 저장소 main은 a1fc935 기준이므로 변경 묶음(`ai_studio_changes_20261109.zip`)을 적용해야 함

저장소: justinhblee-prog/ai_studio, 기준선 = main (머지 커밋 a1fc935). 소스는 모두 main에 있다.

## 새 세션 첫 메시지 (그대로 붙여 넣기)

```
저장소의 CURRENT_HANDOFF_WORK-E.md, tasks.json, docs를 읽고 자율 개발 책임자로 이어서 진행해. 아래 "현재 상태"가 핸드오프 §6·§7보다 최신이니 우선해. 방식은 분석→구현→시험→수정→검증→문서→다음 작업 순환이고, 멈추거나 "계속할까요?"라고 묻지 마. 실행하지 않은 시험을 통과했다고 보고하지 말고, 구현하지 않은 기능을 완료라고 하지 마. 작업은 새 브랜치에서 하고 main에는 직접 푸시하지 마. 푸시와 PR은 내가 허락한 범위에서만 해.
```

## 현재 상태 (핸드오프 §6·§7 대체)

완료 (직접 실행해 확인, 로컬):
- 라우트 어댑터 1단계: Workspace 권한, Character, Project, Products, Workspaces, Assets(메타·바이트), Photo 14개 라우트, Lookbook 25개 라우트 전부 포트 경유. SQLite와 PG 동등성 시험 + 변이 시험.
- 경합 시험 완료: Lookbook 조립·패키지, 자산·부모 삭제 경합(FOR SHARE), Job 취소·완료 교착(락 순서 수정), poll 재예약 타입 오류 수정, Outbox·알림 전달, Project 보관 vs Lookbook 생성(FOR SHARE 누락 수정), Character 생성·수정 vs 자산 삭제(자산 삭제 보호에 Character 추가 — SQLite·PG 공통, 동작 변경).
- 로컬 결과: pytest 626 passed / 59 skipped, 실DB(PG) 시험 59 passed.
- GitHub CI: run #3(source-import)과 run #4(main) 모두 success (CI 점검 창 보고, 개발 창은 직접 조회하지 못함). backend의 passed/skipped 개수는 미확인.

아직 하지 않음 (완료로 보고 금지):
- API 런타임은 SQLite. PG 포트는 런타임에서 닿지 않음. `DATABASE_BACKEND=postgresql` 활성화 금지.
- 경합 시험 미작성: Job 목록·페이지. `output_asset_link`는 PG 구현 자체가 없음(SQLite 전용) — 구현 여부는 설계 결정 필요.
- Job·Outbox·알림 시험은 변이 증거 없음 (취소 교착과 reschedule만 수정 되돌려 확인).
- Supabase Storage, 파일시스템 장애 주입, `_verified_version_path` 로컬 디스크 코드, 고아 파일 정리 작업.
- 랜딩 재구현(시안 ①), 브라우저 E2E, 3D·가상 피팅, 레지스트리 aggregate `workspace_and_asset_metadata`(PARTIAL).
- 11-08 이전 작업 A~D 일부는 유실되어 재구현한 것 (핸드오프 §2).

## 다음 작업 순서
1. CI backend 잡의 pytest 요약 줄 확인 (실DB 시험 56개가 skipped가 아닌지).
2. Job 목록·페이지 경합 시험 + Job·Outbox·알림 변이 증거.
3. T56 Asset 버전 생성 메타데이터 보강.
4. 랜딩 재구현(시안 ①), 브라우저 E2E.
5. (승인 후) TEST Supabase에 0011–0013 적용.

## 승인 경계 (불변)
- Production Supabase/Vercel 변경 금지, 유료 Provider 호출 금지, `DATABASE_BACKEND=postgresql` 활성화 금지.
- 사용자에게 묻는 것은 실제 외부 비용, API 키·비밀, 권한 승인, 되돌릴 수 없는 삭제, 계약·법률·개인정보 결정, 명백한 외부 차단뿐.
- GitHub: main 직접 푸시 금지. 푸시·PR은 사용자 허락 범위에서만.

## 재현
- 전체 시험: `python -m pytest -q -W ignore`
- 실DB 시험: `ACS_TEST_DATABASE_URL`을 로컬 일회용 PG로 지정, `bash scripts/run_live_pg_tests.sh -q -W ignore`
- 보고 형식: 실행한 명령과 결과 숫자를 그대로, 실행하지 않은 것은 "미실행"으로 표시.
