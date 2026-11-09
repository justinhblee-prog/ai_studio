# LAUNCH STATUS

> 이 파일은 2026-11-09 세션에서 **새로 만들었다**. 이전에는 저장소의 어느 브랜치와 로컬 파일시스템에도 `docs/LAUNCH_STATUS.md`가 없었다(검색으로 확인). 따라서 이전 내용을 기준으로 정리한 것이 아니라, 이 세션에서 직접 확인한 사실만 적는다. 이전 버전이 따로 있다면 그 내용은 반영되지 않았다.

## 변경 로그 (최신이 위, PR이 머지될 때마다 추가)

### 2026-11-09 · PR #5 (머지 294b6dd) — L-13, T56, CI 실패 은폐 수정
- **CI (head bf6ed25, run 42548956699)**: backend success — pytest `692 passed, 1 warning`, 실DB 단계 `66 passed, 1 warning`(failed 없음); frontend success — `tsc --noEmit` 통과, `test:source` node 시험 8 pass/0 fail + 4 pass/0 fail, `vite build` 통과.
- **완료**: L-13(출시 빌드는 `VITE_API_BASE_URL`만 사용, 주소 입력란·저장 값·localhost 대체 제거, 개발 빌드는 유지); T56(SQLite↔PG 새 버전 생성 메타데이터 비교 시험, 변이 7/7 적발); CI "Live tests must not be silently skipped" 단계가 실패를 가리던 문제 수정(4가지 경우 시뮬레이션); 간헐 실패 시험(Lookbook 조립 경합) 설계 결함 수정(기존 시험 40회 중 1회·순서 뒤집으면 10회 중 6회 실패 → 수정 후 두 순서 모두 40회 중 0회).
- **미검증**: L-13은 브라우저 설정만 제거한 것이며 서버가 주소를 강제하지 않음; 헤드리스 Chromium 검증은 로컬 1회(CI에는 브라우저 시험 없음). work-20261109 핸드오프의 "원인 불명 1회 실패"가 위 시험인지는 시험 이름 미기록으로 확인 못 함.
- **차단**: 아래 "차단" 섹션 참조.

## 차단 (입력·승인이 없어 하지 못한 것; 다른 작업은 계속 진행)
| 항목 | 이유 | 필요한 것 |
|---|---|---|
| `ai_studio_legal_patch_20261109.zip` 적용(큐 2) | 세션에 파일 없음(업로드 폴더 `.saved-uploads`에 `NEXT_SESSION_START.md`뿐, 파일시스템 검색에도 없음). 2회 확인 | zip을 저장소에 커밋하거나 세션에 업로드 |
| L-02 서버 API(`/v1/legal/documents`, `/v1/me/legal-status`, `/v1/me/legal-acceptances`) | 저장소에 해당 라우트 없음(패치 zip에 들어 있을 것으로 추정 — 미확인). 법률 문서 본문·버전은 빈칸을 임의로 채우지 않음 | 패치 zip 또는 문서 본문 |
| `claude/LEGAL_IMPLEMENTATION_GAPS.md`(L-항목 정의) | 저장소에 없음 | 문서 |
| 배포 환경(영속 디스크 유무) | 파일럿은 SQLite 단일 인스턴스를 전제. 서버리스뿐이면 결론이 바뀜 | 배포 대상 정보 |
| TEST Supabase에 0011–0013 적용 | 금지 항목(접속 정보·승인 필요) | — |
| Production Supabase/Vercel, 유료 Provider, Production `DATABASE_BACKEND=postgresql`, 실데이터 영구 삭제, 비밀·키 | 금지 항목 | — |

## 1. PR #5 머지 전 확인 (head 436792c, CI run 42547697665)

| 확인 | 결과 |
|---|---|
| frontend `npx tsc --noEmit` | success |
| frontend `npm run test:source` | success — node 시험 8건 pass / 0 fail, 4건 pass / 0 fail(`apiBaseUrl.test.mjs`), Public landing contract PASS |
| frontend `npm run build` | success (`tsc -b && vite build`, built in 2.66s) |
| backend 전체 pytest (실DB 포함) | 692 passed, 1 warning (skipped 0) |
| backend "Live tests must not be silently skipped" 단계 | **단계는 success로 표시됐지만 로그는 `1 failed, 65 passed`** (아래 §2) |
| T56 시험의 변이 검증 | 변이 7종 모두 적발(재실행). 이 시험만 잡는 것: `previous_version` 오프바이원, 255자 절단 제거, 포트의 경로 제거 제거 |
| PR #4(merge-20261109) | main에 merged — merge commit `c5baffa`. main push CI run #8: backend 691 passed(skipped 0)·실DB 65 passed, frontend success |
| PR #3(work-20261109) | merged (포함된 커밋이 main에 들어가 GitHub이 merged 처리) |
| 법률 패치 PR | **없음** — `ai_studio_legal_patch_20261109.zip`이 세션에 없어 적용·PR 생성을 하지 못함 |
| PR #1(Add Python CI workflow) | 열린 채로 남아 있음(이번 작업과 무관, 손대지 않음) |

T56은 수정이 아니라 비교 시험 추가였다. "수정을 되돌리면 실패하는가"는 코드 변이로 확인했다: `postgres_assets.create_asset_version`과 `asset_bytes` 포트의 해당 줄을 바꾸면 7/7 실패, 원상복구 후 통과.

## 2. CI에서 발견한 문제 (PR #5 CI에서 드러남)
1. **CI 단계가 실패를 가렸다**: `pytest ... | tee live.txt && ! grep -q skipped live.txt`는 파이프 종료 코드가 `tee`의 것이라 시험이 실패해도 단계가 통과했다. → `set -o pipefail`과 `grep -qE "[0-9]+ (skipped|failed)"`로 수정. 4가지 경우(통과·실패·건너뜀·pytest 비정상 종료)를 로컬에서 시뮬레이션해 확인.
2. **간헐 실패 시험의 원인 확정**: `test_lookbook_assembly_concurrent_attach_and_decide_are_serialised`의 두 번째 경합이 항상 `runs[5]`를 썼는데, 첫 경합에서 6개 중 아무 run이나 이기므로 `runs[5]`가 승자면 두 번째 경합이 전부 "이미 첨부됨" 충돌이 되어 승자가 0이 된다(제품 결함이 아니라 시험 설계 결함). 증거: 기존 시험 로컬 40회 중 1회 실패, 첫 경합에서 `runs[5]`가 먼저 시도되게 순서를 뒤집으면 10회 중 6회 실패. 수정(승자가 아닌 run을 사용): 뒤집은 순서 40회 중 0회, 일반 순서 40회 중 0회 실패.
3. work-20261109 핸드오프의 "전체 실DB 실행 중 1회 실패, 시험 이름 확인 못 함(원인 불명)"이 이 시험인지는 **확인하지 못함**. 같은 증상(드문 1회 실패)이지만 그 실패의 시험 이름이 기록되지 않았다. 앞서 15회 반복에서 15/15 통과한 것도 이 시험이 약 1/40 확률로만 실패하기 때문에 설명된다(15회 반복은 이 결함을 잡기에 충분하지 않았다).

## 3. 큐 (이 파일이 없었으므로 `NEXT_SESSION_START.md`의 큐 기준)
| 항목 | 상태 |
|---|---|
| CI backend pytest 요약 확인 | 완료 |
| 경합 시험 4종·Job/Outbox/알림 변이 증거 | 완료(`output_asset_link` PG 구현 없음 — 미구현으로 확인) |
| T56 | 완료(시험 보강) |
| L-13 출시 빌드 API 주소 고정 | 완료 (PR #5) |
| L-04 인물 사진 업로드 권리·동의 확인 | **막힘** — `claude/LEGAL_IMPLEMENTATION_GAPS.md`가 저장소에 없음, 문구·기록 항목은 법률 결정 |
| L-02 프런트 동의 화면 | **막힘** — 위와 같음 |
| 법률 패치 zip 적용 | **막힘** — 파일 없음 |
| 랜딩 재구현(시안 ①) | 시안 파일이 저장소에 없음 — 확인 필요 |
| 브라우저 E2E | 가능한 범위에서 진행 (Supabase는 호출하지 않고 요청 가로채기 사용) |
| TEST Supabase에 0011–0013 적용 | 승인·접속 정보 필요 — 하지 않음 |

## 4. 승인 경계 (불변)
Production Supabase/Vercel 변경 금지, 유료 Provider 호출 금지, `DATABASE_BACKEND=postgresql` 활성화 금지, 영구 삭제 실행 금지, 비밀·키 사용 금지.
