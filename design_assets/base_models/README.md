# 기본 인체 모델 (정적 GLB)

- `base_male.glb`, `base_female.glb`: 코드(`ai_creator_studio_backend_starter/app/base_models.py`)로 직접 만든 양식화 인체(각 4,680 삼각형, 약 97 KB, 부드러운 법선·둥근 어깨·목·머리 형태·손·발 포함(R-ENGINE-08)). 얼굴·스캔·사진·제3자 에셋 없음 — 출처·라이선스 문제가 되는 외부 자료가 없다.
- 재질 이름 `skin` / `top` / `bottom`의 `baseColorFactor`를 바꾸면 피부·상의·하의 색이 바뀐다.
- 기본 옷: 티셔츠 + 긴바지(상의 파랑, 하의 짙은 회색). 다른 스타일·색·몸 치수는 API(`GET /v1/base-models/{sex}/glb?…`) 또는 이 스크립트로 만든다.
- 다시 만들기: `python ai_creator_studio_backend_starter/scripts/export_base_models.py`
