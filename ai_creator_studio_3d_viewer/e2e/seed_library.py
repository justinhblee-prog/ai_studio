"""Seed a few default-library items for E2E (run with the backend's environment, from the backend directory).
Uses the same entry point as the import tool (app.library.upsert_item). The images are plain colour blocks (SAMPLE data)."""
import io

from PIL import Image

from app import library


def png(color, size=(120, 160)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def add(item_id, category, name, color, attrs=None, status="published", source="ai_generated", tags=None):
    fields = {"item_id": item_id, "category": category, "name_ko": name, "tags": tags or [], "source": source, "status": status,
              "tool_and_date": "E2E seed, 2026-11-15", "rights_confirmed": True, "is_placeholder": True}
    if attrs:
        fields["attributes"] = attrs
    return library.upsert_item(fields, png(color), f"{item_id}.png")


M = {"skin_tone": "3", "hair": "wavy", "body_type": "regular", "age_range": "30s", "region_style": "europe"}
add("model-01", "model", "샘플 모델 1", (200, 150, 120), M, tags=["여성"])
add("model-02", "model", "샘플 모델 2", (120, 90, 70), {**M, "hair": "curly", "skin_tone": "5", "region_style": "africa"}, tags=["남성"])
add("top-01", "top", "샘플 셔츠", (230, 220, 200))
add("top-02", "top", "샘플 니트", (200, 60, 60), source="licensed")
add("bag-01", "bag", "샘플 토트백", (30, 30, 30))
add("background-01", "background", "샘플 스튜디오", (240, 240, 240))
add("top-draft", "top", "초안 셔츠(보이면 안 됨)", (1, 2, 3), status="draft")
add("top-retired", "top", "내린 셔츠(보이면 안 됨)", (4, 5, 6), status="retired")
print("seeded library")
