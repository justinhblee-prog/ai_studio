# Photo PSD 주고받기 서버 (R-PSD-01) — `app/psd_io.py`, `app/photo_psd.py`

도구에 묶이지 않고 **PSD 표준 파일**로 주고받는다(포토샵·PhotoCraft·Photopea 등). 새 의존성 없이 순수 파이썬 + Pillow로 PSD/PSB를 직접 쓰고 읽는다.

## API
- `POST /v1/workspaces/{id}/photo-psd` `{asset_id, final_asset_id?, cutout?=true, depth?=8|16}` → **PSD 파일**(`image/vnd.adobe.photoshop`, `X-Content-SHA256`·`ETag`). 편집자 이상. **원본 해상도**(최대 6천만 화소). 레이어(아래→위): 원본(참고·숨김) / 배경(피사체 자리 비움) / 피사체(누끼) / 최종 결과(평면·참고·숨김); `cutout:false`면 원본(숨김) / 보정 결과. 병합 이미지 = 현재 결과, sRGB ICC 포함. 파일은 저장하지 않고 바로 돌려주며 내보냄을 `asset.psd_exported`(레이어 수·바이트·SHA-256)에 기록. PSD는 작업 파일이라 검수 전에도 받을 수 있다(최종 PNG/JPEG 내려받기의 승인 규칙은 그대로).
- `POST /v1/workspaces/{id}/photo-psd/import` (multipart `file`, `rights_confirmed`·`depicts_person`·`likeness_consent`) → 201 `{asset, psd:{width,height,depth,format,layers,layer_names,sha256,…}, source:"merged"|"layers", work_size, reduced}`. .psd/.psb 300MB 이하. 병합 이미지를 쓰고, **없거나 빈(흰) 병합이면 보이는 레이어를 합성**. 긴 변을 3000px로 줄여 **새 원본 자산**으로 추가(버전 1개), PSD 원본 파일은 SHA-256 이름으로 비공개 보관, 출처 기록 `asset.psd_import`(올린 사람·시각·레이어 수·크기·"PSD 수정본" 표시). 권리 확인은 이미지 업로드와 같은 규칙.
- 오류(`error_catalog` ko/en): `PSD_NOT_PSD` · `PSD_CORRUPT`(손상·잘림) · `PSD_TOO_LARGE`(413/422) · `PSD_UNSUPPORTED`(CMYK·Lab·32비트 등) · `IMAGE_UNREADABLE`.

## 형식 (psd_io)
쓰기: RGB 8·16비트, 레이어 이름(ASCII + 유니코드 `luni` 블록 → 한글 유지), 숨김 표시, 위치, 불투명도, ICC. 레이어 채널은 ZIP(작음; `compat=True`면 RLE), **병합 이미지는 항상 RLE**(가장 널리 읽히는 형태). PSB(8바이트 길이)도 쓰기·읽기. 읽기: 원시/RLE/ZIP/ZIP+예측 채널, 8·16비트, RGB(회색은 회색으로). 텍스트 레이어·스마트 오브젝트·마스크·조정 레이어는 **해석하지 않고** 저장된 픽셀만 일반 레이어로 읽는다(보존만, 요청대로).

## 시험 (24개)
왕복(PSD/PSB × 8/16비트 × ZIP/RLE)에서 이름·순서·숨김·위치·픽셀·투명도·ICC 유지, **Pillow의 PSD 읽기로 병합 이미지 독립 확인**, 병합 없는/흰 병합 PSD의 레이어 합성 읽기, 끝이 잘린/손상/글자뿐인 파일·300MB 초과·CMYK·32비트 거부, 작업 해상도 축소 표시, 내보내기의 원본 해상도·레이어 구성·감사 기록·권한·작업공간 격리, 가져오기의 새 자산·출처 기록·PSD 보관·실패 시 아무것도 저장 안 함.

## 한계 (정직하게)
- **포토샵·Photopea 등 실제 프로그램에서 열어 보는 시험은 미실행(미확인)**: 자체 쓰기·읽기, Pillow 독립 읽기, 손으로 만든 파일만 시험했다. 레이어 이름·순서·숨김이 실제 프로그램에서도 유지되는지가 요청의 시험 항목이었으나 이 환경에 해당 프로그램이 없어 못 했다.
- 시간: 12MP·레이어 3장 최악(압축이 안 되는 잡음 사진) 쓰기 5초, 130MB, 읽기 1초. 큰 사진은 요청 시간이 길어질 수 있다(작업(job)으로 바꾸지 않았다).
- 배경 레이어는 피사체 자리를 **투명하게 비울 뿐 채워 넣지 않는다**(인페인팅 없음). 피사체 분리는 고전 배경 제거(`bg_removal`)라 복잡한 배경에서는 틀릴 수 있다.
- ZIP+예측 채널은 2천만 화소까지만 읽는다(파이썬 처리). 16비트 파일은 읽을 때 상위 바이트만 써 8비트 작업본이 된다. 내보내는 16비트는 8비트 원본을 늘린 값이다(화질 이득 없음, 프로그램 호환용).
- 가져온 PSD는 병합/합성 한 장만 새 원본이 된다(레이어를 서버가 계속 들고 편집하지 않음). PSD 원본은 보관하지만 다시 내려받는 경로는 아직 없다.
