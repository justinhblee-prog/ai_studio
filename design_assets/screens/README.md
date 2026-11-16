# 홈페이지용 화면 캡처 (R-036)

| 파일 | 화면 | 샘플 데이터 출처 |
|---|---|---|
| `screen-01-jobs.png` | 생성 작업 목록(실패·진행·완료·완료) | 시험(mock) 엔진 작업 4건, 완료 2건은 시드된 결과물 |
| `screen-02-library.png` | 라이브러리 · 모델 탭 · 머리=웨이브 필터 | `scripts/library_make_samples.py` 표시용 이미지(AI 생성 이미지·표시용 샘플 표기 그대로) |
| `screen-03-compare.png` | 사진 단계 편집 · 전/후 슬라이더(화이트 밸런스) | 코드로 그린 샘플 가방 이미지(노란 색 기울기 포함) |
| `screen-04-approval.png` | 결과물 검수 · 승인 이력 | 승인자 `approver-a`(수정 요청), `approver-b`(승인) 샘플 계정 |

규격: 1440×900, 배율 100%, 밝은 테마(앱에 어두운 테마 없음). 실제 사용자 이름·이메일·토큰 없음(작업공간 `sample-team`, 계정 `approver-a/b@example.com`).
다시 촬영: 임시 스택에서 `node e2e/capture_screens.mjs <출력 폴더>` (백엔드가 Linux에서 돌아야 하므로 CI 러너에서 실행하고 산출물을 받아 온다).
