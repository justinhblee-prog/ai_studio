# 개발자 온보딩 — 10분 안에 로컬 API 띄우기 (B-21)

목표: 저장소를 받은 사람이 **명령 몇 개로** 무료 mock 모드의 API를 띄우고 응답을 확인한다. 외부 AI 서비스·유료 호출·Supabase/Vercel·공유 DB는 **쓰지 않는다**(전부 로컬, mock).

## 준비물
| 항목 | 필요 | 비고 |
|---|---|---|
| Python | 3.11 이상(CI는 3.13) | |
| 운영체제 | **Linux / macOS / Windows의 WSL** | API 코드가 `fcntl`을 써서 **순수 Windows에서는 `app.main`이 열리지 않는다**(시험 중 API 시험이 Windows에서 실패하는 이유). Windows는 WSL을 쓰거나 CI에서 확인 |
| Node | 20 이상 | 화면(뷰어)을 만질 때만 |
| ffmpeg | 선택 | MP4 영상 시험·기능에만 필요(없으면 해당 시험은 건너뜀, CI는 설치함) |

## 1) 서버 띄우기 (약 2~5분, 대부분 `pip install` 시간)
```bash
cd ai_creator_studio_backend_starter
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python scripts/dev_up.py            # 127.0.0.1:8000 에서 mock 모드 서버. Ctrl+C로 멈춤
```
출력의 `UP in N s: http://127.0.0.1:8000 …` 이 나오면 성공. `http://127.0.0.1:8000/docs`에서 API를 눌러 볼 수 있다. 로그인 헤더는 `Authorization: Bearer local-dev-token`(**공개된 로컬 전용 값**, 이 mock 서버에서만 통한다).
- 데이터는 `ai_creator_studio_backend_starter/.dev_data/`(git 무시)에 쌓인다. 지우면 처음 상태.
- 서명 비밀값은 실행마다 무작위로 메모리에만 만든다. `DATABASE_URL`/`DATABASE_BACKEND`는 지우고 시작해 **실수로 실제 DB에 붙지 않는다**.
- 준비물만 점검: `python scripts/dev_up.py --check` · 띄웠다 확인하고 끄기: `python scripts/dev_up.py --selftest`(CI가 매 PR마다 실행해 이 문서가 거짓이 되지 않게 지킨다).

## 2) 시험 돌리기
```bash
python -m pytest -q tests/test_garments.py tests/test_render_qc.py     # 빠른 확인(몇십 초)
python -m pytest -q                                                    # 전체(약 4~5분, CI와 같은 범위; PostgreSQL 시험은 ACS_TEST_DATABASE_URL이 없으면 건너뜀)
```
PostgreSQL 라이브 시험은 **버려도 되는 DB**에만(`ACS_TEST_DATABASE_URL`). 공유·TEST Supabase·운영 DB에는 절대 연결하지 않는다.

## 3) 화면(뷰어)
```bash
cd ai_creator_studio_3d_viewer && npm ci && npm run build && npm run test:source
```
브라우저 e2e(`e2e/*.mjs`)는 Playwright(Chromium)가 필요하며 CI에서 돈다.

## 4) 어디를 읽나
`docs/INDEX.md`(전체 문서 색인) → `docs/README.md`(문서 구조) → 하고 싶은 일의 문서: 3D·의류 `GARMENT_DEFORM.md`, 화면 연결 `AIS_API_CONTRACT.md`, 오류 코드 `ERROR_CODES.md`, 운영 `RUNBOOK.md`, PostgreSQL 전환 `POSTGRES_RACE_PRIMITIVES.md`.

## 5) 하지 않는 것(저장소 규칙)
운영 Supabase/Vercel 변경, 유료 공급자 호출, 비밀·키를 파일·로그·PR에 쓰기, 법무 빈칸 채우기, `main` 강제 푸시·CI 실패 상태 머지. 자세한 것은 저장소 `CLAUDE.md`.

## 6) 막혔을 때
| 증상 | 원인·해결 |
|---|---|
| `No module named 'fcntl'` | 순수 Windows. WSL/Linux/macOS를 쓴다 |
| `missing Python package …` | `pip install -r requirements.txt` |
| 포트 8000 사용 중 | `python scripts/dev_up.py --port 8010` |
| `/health`가 안 뜸 | 서버 로그의 첫 오류를 본다. `.dev_data/`를 지우고 다시 |
