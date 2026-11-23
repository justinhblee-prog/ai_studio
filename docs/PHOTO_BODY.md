# 사진 → 몸 치수 추정 → 3D 인물 (D-2, 경로 C: 자체 코드) — `app/photo_body.py`

전신 사진 1장에서 own3d 마네킹의 치수(`height_cm, chest_cm, waist_cm, hips_cm`)를 **추정**한다. Pillow만 사용(새 의존성·토큰·모델 없음). `POST /v1/workspaces/{id}/photo-body {asset_id, sex, height_cm?}`(편집자 이상, own3d 플래그 `RENDER3D_ENABLED` 뒤, 저장 없음) → `{estimated:true, label, measurements, silhouette_px, warnings, chest_from_prior, assumptions}`. 화면: `AIS_API.studio3d.bodyFromPhoto({assetId, sex|modelId, heightCm?})` → 결과 `measurements`를 `render({measurements})`에 그대로 넘긴다. 피부색·머리 길이는 읽지 않고 화면이 넘기는 `sk`/`hs`를 쓴다.

## 방법
1. 고전 배경 제거로 사람 분리 → 경계 상자 → 키(픽셀). 가장자리에 닿으면 `PHOTO_BODY_CLIPPED`, 사람이 없으면 `PHOTO_BODY_NOT_FOUND`, 폭/키 비가 0.12~0.6 밖이면 `PHOTO_BODY_POSE`.
2. 몸 축(몸통 높이 구간 실루엣 중심)을 지나는 **가운데 구간**의 폭을 가슴·허리·엉덩이 행(키의 0.70·0.60·0.52, own3d 몸이 이 높이로 만들어짐)에서 읽는다.
3. 사진에는 축척이 없으므로 **키(`height_cm`, 없으면 성별 기본 166/178)** 로 환산: 반폭 = (폭/키)×키cm÷2, **깊이는 프리셋의 깊이/폭 비**로 가정(앞 사진은 깊이를 모름) → 타원 둘레.
4. **A자세에서 팔이 가슴에 붙으면** 가슴 행 폭이 몸통보다 넓다(허리 폭의 1.22배 초과로 판정) → 가슴 폭은 읽을 수 없어 **허리 + 프리셋 가슴/허리 비율(사전 가정)** 로 대체하고 경고·`chest_from_prior:true`. 

## 결과 (합성 사진 10장, `scripts/photo_body_sheet.py`, 단위 cm, |추정 − 정답| 평균/최대)
| 부위 | 평균 | 최대 |
|---|---|---|
| 허리 | 0.6 | 1.4 |
| 엉덩이 | 0.8 | 1.3 |
| **가슴(사전 가정으로 추정)** | **5.6** | **11.0** |
전체 표와 앞/옆 렌더 시트(`photo_body_sheet.png`, 재구성한 몸 10명): 스크립트로 재생성. 사진 10장의 행은 키 158~190 cm, 가슴 80~112, 허리 64~96, 엉덩이 90~108.

## 한계 (정직하게)
- **합성 사진만 시험(닫힌 고리)**: 정답이 사진에 이미 들어 있는 마네킹 렌더라서 추정기 자체의 오차만 잰 것이다. **실제 사람 사진(옷·머리카락·원근·자세·신발·그림자)은 미실행.** 라이브러리 사진 모델(mf/mm/mc/mh/cw)은 이 환경에 사본이 없어(`site/img/cat`에 없음) 쓰지 못했다 → **정확도는 미확인**.
- 옷을 입은 실루엣의 치수다(헐렁한 옷은 크게 나옴). 깊이는 가정, 키는 사용자가 주거나 기본값. 가슴은 팔이 붙으면 사전 가정이라 최대 11 cm 어긋났다. 옆 사진이 있으면 깊이를 읽을 수 있으나 만들지 않았다.
- (A) SAM 3D Body는 HF 신청 전이라 손대지 않았다(요청 그대로).
