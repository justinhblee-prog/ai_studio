"""The committed static base models (design_assets/base_models) are exactly what the generator produces, so they cannot silently drift."""
from pathlib import Path

import pytest

from app.assets.validation import validate_gltf_upload
from app.base_models import SEXES, build_base_model

FOLDER = Path(__file__).resolve().parents[2] / "design_assets" / "base_models"


@pytest.mark.parametrize("sex", SEXES)
def test_the_committed_file_is_the_generator_output_and_a_valid_glb(sex):
    data = (FOLDER / f"base_{sex}.glb").read_bytes()
    assert data == build_base_model(sex), "run scripts/export_base_models.py and commit the result"
    assert validate_gltf_upload(f"base_{sex}.glb", data).media_type == "model/gltf-binary"
    assert 10_000 < len(data) < 20_000


def test_the_readme_states_the_origin_and_how_to_regenerate():
    text = (FOLDER / "README.md").read_text(encoding="utf-8")
    assert "제3자 에셋 없음" in text and "export_base_models.py" in text and "skin" in text and "top" in text and "bottom" in text
