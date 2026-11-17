"""Writes the two static base human models (default clothes colours and styles) to a folder.   python scripts/export_base_models.py [out_dir]   (default: ../design_assets/base_models)
The files are fully determined by app/base_models.py; tests/test_base_models_static.py fails if the committed files drift from this generator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.base_models import SEXES, build_base_model  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "design_assets" / "base_models"


def main(argv=None) -> int:
    out = Path((argv or sys.argv[1:] or [str(DEFAULT_OUT)])[0])
    out.mkdir(parents=True, exist_ok=True)
    for sex in SEXES:
        (out / f"base_{sex}.glb").write_bytes(build_base_model(sex))
        print(out / f"base_{sex}.glb")
    (out / "README.md").write_text(
        "# 기본 인체 모델 (정적 GLB)\n\n- `base_male.glb`, `base_female.glb`: 코드(`ai_creator_studio_backend_starter/app/base_models.py`)로 직접 만든 양식화 저폴리 인체(각 912 삼각형, 약 13.6 KB). 얼굴·스캔·사진·제3자 에셋 없음 — 출처·라이선스 문제가 되는 외부 자료가 없다.\n"
        "- 재질 이름 `skin` / `top` / `bottom`의 `baseColorFactor`를 바꾸면 피부·상의·하의 색이 바뀐다.\n- 기본 옷: 티셔츠 + 긴바지(상의 파랑, 하의 짙은 회색). 다른 스타일·색·몸 치수는 API(`GET /v1/base-models/{sex}/glb?…`) 또는 이 스크립트로 만든다.\n"
        "- 다시 만들기: `python ai_creator_studio_backend_starter/scripts/export_base_models.py`\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
