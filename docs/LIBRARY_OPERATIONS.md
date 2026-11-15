# 기본 자산 라이브러리 운영 안내 (항목 추가·수정·내리기)

대상: 이미지와 표(manifest)만 준비하면 되는 비개발자 운영 담당. 명령 실행은 개발 PC에서 개발 창이 하거나, 아래 순서를 그대로 따라 할 수 있습니다.
이 안내는 **로컬/시험 환경 기준**입니다. 운영 환경(Production)에 반영하는 것은 별도 승인 절차 뒤에 합니다(이 문서의 범위 밖).

## 1. 무엇을 준비하나
1. **이미지 폴더** — 이미지 파일(PNG·JPG·WebP)을 한 폴더에 모읍니다. 파일명은 영문 소문자·숫자·하이픈(`top-03.png`). 한 장은 15 MB 이하.
2. **manifest.csv** — 항목마다 한 줄. 첫 줄은 열 이름입니다. 엑셀에서 만들 때는 "CSV UTF-8(쉼표로 분리)"로 저장하세요.

| 열 | 필수 | 설명 |
|---|---|---|
| `id` | 예 | 항목의 고정 이름(소문자·숫자·하이픈, 2~64자). **한 번 정하면 바꾸지 않습니다.** 같은 id를 다시 올리면 "수정"으로 취급됩니다. |
| `category` | 예 | `model` `top` `bottom` `dress` `outer` `bag` `hat` `eyewear` `shoes` `jewelry` `headwear` `belt_scarf` `background` 중 하나 |
| `name_ko` | 예 | 화면에 보이는 이름 |
| `file` | 예 | 이미지 파일 이름(폴더 안의 파일만. 경로 불가) |
| `source` | 예 | `ai_generated`(AI로 만듦) / `licensed`(구매·계약) / `self_made`(직접 촬영). `ai_generated`는 화면에 "AI 생성 이미지"로 표시됩니다. |
| `tool_and_date` | 예 | 만든 도구와 날짜. 예: `ChatGPT 이미지 생성, 2026-11-20` |
| `rights_ok` | 예 | 이 이미지를 다른 사용자에게 제공해도 되는 권리를 **확인했으면 `yes`**. `no`나 빈칸이면 가져오기가 거부됩니다. |
| `subcategory`, `name_en`, `tags`, `note` | 아니오 | 세부 종류, 영어 이름, 검색용 태그(쉼표로 구분), 메모(화면에는 안 보임) |
| `likeness_check` | 모델은 권장 | 실존 인물과 닮지 않았는지 사람이 눈으로 확인했으면 `yes`. 시험 환경에서는 비어 있어도 가져오기는 되지만 경고가 나오고, **운영 환경(`--production`)에서는 거부됩니다.** |
| `status` | 아니오 | 비우면 `published`(바로 공개). `draft`로 올리면 사용자에게 안 보입니다. |
| `is_placeholder` | 아니오 | 개발·시험용 SAMPLE 이미지일 때만 `yes`. **실제 서비스 항목에는 쓰지 않습니다.** |
| `skin_tone` `hair` `body_type` `age_range` `region_style` | 모델만 필수 | 허용 값: skin_tone 1~6 / hair `straight` `wavy` `curly` `short` `covered` / body_type `slim` `regular` `plus` / age_range `20s` `30s` `40s` `50s` / region_style `east_asia` `southeast_asia` `south_asia` `middle_east` `africa` `europe` `latin_america`. 화면에서 고르기 쉽게 거르는 용도이며 실제 사람의 민족·정체성을 단정하지 않습니다. 모델이 아닌 항목에서는 비웁니다. |

## 2. 점검(아무것도 바뀌지 않음) → 반영
```
python scripts/library_import.py manifest.csv 이미지폴더            # 점검만 (기본)
python scripts/library_import.py manifest.csv 이미지폴더 --apply    # 반영
```
- 점검은 항목마다 `OK` 또는 `REJECT line 줄번호: id: 이유`를 출력합니다. **거부된 줄이 하나라도 있으면 반영은 아무것도 하지 않습니다**(일부만 올라가는 일이 없습니다). 줄 번호는 manifest.csv의 줄 번호입니다(첫 줄 = 열 이름이므로 첫 항목은 2번).
- 거부 사유 예: 권리 확인이 `yes`가 아님, 이미지 파일이 없음/깨짐/형식 불일치/너무 큼, 알 수 없는 종류·출처, 모델 속성 값이 허용 목록에 없음, 같은 id가 두 번 나옴, 필수 열 누락.
- 한꺼번에 다 만들 필요 없습니다. 종류별로 나눠서 여러 번 반영해도 됩니다.

## 3. 수정하기
- **이름·태그·속성만 바꾸기**: manifest의 그 줄을 고치고 같은 방법으로 다시 반영합니다(이미지는 그대로).
- **이미지를 바꾸기**: 같은 id로 새 이미지 파일을 넣고 반영하면 **새 버전**이 만들어집니다. 이전 버전 파일은 보관됩니다. 이미 사용자가 가져간 복사본은 바뀌지 않습니다(복사해 간 시점의 이미지를 계속 씁니다).
- 같은 내용을 다시 반영해도 아무 일도 일어나지 않습니다.

## 4. 내리기(공개 중단)
```
python scripts/library_import.py --retire top-03 top-04            # 점검
python scripts/library_import.py --retire top-03 top-04 --apply    # 내림
```
내린 항목은 사용자에게 즉시 보이지 않습니다. 파일과 기록은 지워지지 않으며, 이미 사용자가 가져간 복사본은 계속 사용할 수 있습니다. 다시 공개하려면 manifest에서 같은 id를 `status` 비움(published)으로 다시 반영합니다.

## 5. 개발·시험용 SAMPLE 이미지
```
python scripts/library_make_samples.py 출력폴더          # "SAMPLE" 글자가 큰 단색 이미지 80여 장과 manifest 생성
python scripts/library_import.py 출력폴더/manifest.csv 출력폴더/images --apply
```
SAMPLE 항목은 `is_placeholder=yes`이며, `--production` 옵션을 주거나 환경 변수 `ACS_ENVIRONMENT=production`이 있으면 **가져오기가 거부**됩니다(실서비스에 섞이지 않게).

## 6. 저장 위치와 백업
- 항목 정보: 자산 데이터베이스(`ASSET_DATABASE_PATH`)의 `library_items`, `library_item_versions` 표.
- 이미지 파일: `LIBRARY_STORAGE_DIR` 폴더(기본 `./library_assets`). 백업 스크립트(`scripts/backup_restore.py`)가 이 폴더도 함께 백업합니다.
- 사용자의 계정·작업공간 삭제(purge)는 이 라이브러리를 건드리지 않습니다.

## 7. 운영 설정값
- `DOWNLOAD_MONTHLY_LIMIT`: 룩북 패키지 내려받기 월 한도(작업공간당, UTC 달력월). 파일럿 값 **100**(설계 창 결정 2026-11-15). 코드 기본값은 0(무제한)이므로 **운영 환경 변수에 100을 설정해야 적용됩니다.**
- `PREVIEW_REQUIRE_ORIGIN`(기본 켜짐)과 `APP_CORS_ORIGINS`: 서명 이미지 주소는 허용 출처의 페이지에서만 열립니다. 운영에 앱 주소가 `APP_CORS_ORIGINS`에 있어야 합니다.
- 알려진 한계(파일럿에서 수용): 로그인한 구성원은 화면용 보기 경로(`preview-content`, 작업 결과 이미지)로 이미지를 직접 받을 수 있고 이 경로는 감사·한도 대상이 아닙니다. 사용자 자산은 원본 해상도로 보입니다. 화면 캡처는 막을 수 없습니다.

## 8. 반드시 지킬 것
- 이미지 제작 도구의 이용약관상 **상업적 사용 가능 여부**와 **다른 사용자에게 제공해도 되는지**를 확인한 뒤에만 `rights_ok=yes`로 적습니다(법률 검토 대상).
- 실존 인물·유명인을 닮은 얼굴, 상표·로고·글자·워터마크가 있는 이미지는 올리지 않습니다. 미성년 모델은 만들지 않습니다.
- 이 도구는 운영 환경에 직접 연결하지 않습니다. 운영 반영은 사용자 승인 뒤 별도 절차로 진행합니다.
