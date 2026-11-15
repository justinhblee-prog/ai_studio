"""R-034: the library import tool and the SAMPLE data generator, end to end against the real API."""
import csv
import hashlib
import shutil
import sqlite3
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import library
from app.main import app
from scripts import library_import as tool
from scripts import library_make_samples as samples

client = TestClient(app)


def auth(t="a"):
    return {"Authorization": f"Bearer token-{t}"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "LIBRARY_STORAGE_DIR", tmp_path / "library")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    monkeypatch.delenv("ACS_ENVIRONMENT", raising=False)
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "wa"}).status_code == 201
    return tmp_path


@pytest.fixture
def made(env):
    out = env / "samples"
    samples.build(out, per_category=2)
    return out


def run(made, *extra, manifest=None):
    return tool.main([str(manifest or made / "manifest.csv"), str(made / "images"), *extra])


def listing(**params):
    out, cursor = [], None
    while True:
        page = client.get("/v1/library/items", headers=auth(), params={**params, "limit": 100, **({"cursor": cursor} if cursor else {})}).json()
        out += page["items"]
        cursor = page["next_cursor"]
        if not cursor:
            return out


def counts(env):
    db = sqlite3.connect(env / "a.sqlite3")
    n = db.execute("SELECT COUNT(*) FROM library_items").fetchone()[0], db.execute("SELECT COUNT(*) FROM library_item_versions").fetchone()[0]
    return n + (len(list((env / "library").glob("*"))) if (env / "library").exists() else 0,)


def edit_manifest(made, mutate, name="edited.csv"):
    with (made / "manifest.csv").open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns, rows = reader.fieldnames, list(reader)
    columns, rows = mutate(columns, rows)
    path = made / name
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


# ------------------------------------------------------------------------------------------- the sample generator
def test_samples_cover_every_category_and_every_model_attribute_value(made):
    with (made / "manifest.csv").open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert {r["category"] for r in rows} == set(library.CATEGORIES)
    assert len(rows) == 12 * 2 + 14 and all(r["is_placeholder"] == "yes" and r["rights_ok"] == "yes" for r in rows)
    models = [r for r in rows if r["category"] == "model"]
    for name, allowed in library.MODEL_ATTRIBUTES.items():
        assert {r[name] for r in models} == set(allowed), name
    for r in rows:
        with Image.open(made / "images" / r["file"]) as image:
            assert image.format == "PNG"


# ------------------------------------------------------------------------------------------- checking and applying
def test_the_default_is_a_dry_run_that_changes_nothing(env, made, capsys):
    assert run(made) == 0
    assert "dry run: 38 row(s) fine, nothing changed" in capsys.readouterr().out
    assert not (env / "library").exists()
    assert listing() == []


def test_apply_imports_everything_and_the_api_shows_it_with_labels_and_filters(env, made, capsys):
    assert run(made, "--apply") == 0
    assert "applied: created 38" in capsys.readouterr().out
    items = listing()
    assert len(items) == 38 and {i["category"] for i in items} == set(library.CATEGORIES)
    models = [i for i in items if i["category"] == "model"]
    assert len(models) == 14 and all(m["is_ai_generated"] and m["is_placeholder"] for m in models)
    assert all(set(m["attributes"]) == set(library.MODEL_ATTRIBUTES) for m in models)
    assert 0 < len(listing(category="model", hair="curly")) < 14


def test_running_it_again_changes_nothing(env, made, capsys):
    assert run(made, "--apply") == 0
    before = counts(env)
    capsys.readouterr()
    assert run(made, "--apply") == 0
    assert "applied: unchanged 38" in capsys.readouterr().out
    assert counts(env) == before


def test_a_changed_image_becomes_a_new_version_and_the_old_file_is_kept(env, made, capsys):
    assert run(made, "--apply") == 0
    old = hashlib_of(made / "images" / "sample-top-01.png")
    Image.new("RGB", (300, 400), (1, 2, 3)).save(made / "images" / "sample-top-01.png")
    capsys.readouterr()
    assert run(made, "--apply") == 0
    out = capsys.readouterr().out
    assert "new_version 1" in out and "unchanged 37" in out, out
    item = client.get("/v1/library/items/sample-top-01", headers=auth()).json()
    assert item["version"] == 2
    files = sorted(p.name for p in (env / "library").glob("sample-top-01.*"))
    assert files == ["sample-top-01.v1.png", "sample-top-01.v2.png"]
    assert hashlib_of(env / "library" / "sample-top-01.v1.png") == old, "the first version's file is untouched"


def hashlib_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------- rejections (each names its line; nothing is written)
def first_row(fn):
    def mutate(columns, rows):
        fn(rows[0])  # data line 2
        return columns, rows
    return mutate


def broken_image(made, name, data):
    (made / "images" / name).write_bytes(data)


@pytest.mark.parametrize("label, prepare, expected", [
    ("rights_ok no", lambda m, r: r.update(rights_ok="no"), "rights_ok is not 'yes'"),
    ("rights_ok blank", lambda m, r: r.update(rights_ok=""), "rights_ok"),
    ("file missing", lambda m, r: r.update(file="not-there.png"), "image file not found"),
    ("path traversal", lambda m, r: r.update(file="../manifest.csv"), "plain file name"),
    ("not an image", lambda m, r: (broken_image(m, "bad.png", b"just text"), r.update(file="bad.png")), "IMAGE_DECODE_FAILED"),
    ("wrong extension", lambda m, r: (shutil.copy(m / "images" / r["file"], m / "images" / "x.gif"), r.update(file="x.gif")), "IMAGE_EXTENSION_MISMATCH"),
    ("unknown category", lambda m, r: r.update(category="pants"), "LIBRARY_CATEGORY_INVALID"),
    ("unknown source", lambda m, r: r.update(source="found_online"), "LIBRARY_SOURCE_INVALID"),
    ("tool and date blank", lambda m, r: r.update(tool_and_date=""), "tool_and_date"),
])
def test_a_bad_row_is_refused_with_its_line_number_and_nothing_at_all_is_written(env, made, capsys, label, prepare, expected):
    path = edit_manifest(made, first_row(lambda row: prepare(made, row)))
    assert run(made, "--apply", manifest=path) == 1, label
    out = capsys.readouterr().out
    assert "REJECT line 2:" in out and expected in out, out
    assert "OK     line 3" in out, "the good rows are reported as fine, but still not written"
    assert "nothing was written" in out
    assert not (env / "library").exists() and listing() == []


def test_a_model_attribute_outside_the_allowed_list_is_refused(env, made, capsys):
    def mutate(columns, rows):
        model = next(r for r in rows if r["category"] == "model")
        model["hair"] = "bald"
        return columns, rows
    assert run(made, manifest=edit_manifest(made, mutate)) == 1
    assert "LIBRARY_ATTRIBUTE_INVALID" in capsys.readouterr().out


def test_a_missing_required_column_refuses_the_whole_file(env, made, capsys):
    assert run(made, manifest=edit_manifest(made, lambda c, r: ([x for x in c if x != "rights_ok"], [{k: v for k, v in row.items() if k != "rights_ok"} for row in r]))) == 1
    assert "line 1: the manifest has no column(s): rights_ok" in capsys.readouterr().out


def test_the_same_id_twice_is_refused(env, made, capsys):
    assert run(made, manifest=edit_manifest(made, lambda c, r: (c, r + [dict(r[0])]))) == 1
    assert "duplicate id (first used on line 2)" in capsys.readouterr().out


def test_an_oversized_image_is_refused(env, made, capsys, monkeypatch):
    monkeypatch.setattr(tool, "MAX_IMAGE_BYTES", 100)
    assert run(made) == 1
    assert "image is larger than" in capsys.readouterr().out


def test_sample_items_are_refused_in_a_production_environment(env, made, capsys, monkeypatch):
    assert run(made, "--production", "--apply") == 1
    out = capsys.readouterr().out
    assert out.count("SAMPLE (placeholder) item cannot be imported into a production environment") == 38
    assert listing() == []
    monkeypatch.setenv("ACS_ENVIRONMENT", "production")
    assert run(made, "--apply") == 1 and listing() == []
    monkeypatch.delenv("ACS_ENVIRONMENT")
    assert run(made, "--apply") == 0 and len(listing()) == 38


def test_a_real_item_without_the_placeholder_mark_is_allowed_in_production(env, made, capsys):
    path = edit_manifest(made, lambda c, r: (c, [dict(r[0], is_placeholder="no")]))
    assert run(made, "--production", "--apply", manifest=path) == 0
    assert [i["item_id"] for i in listing()] == ["sample-model-01"]
    assert listing()[0]["is_placeholder"] is False


def test_a_model_without_the_likeness_check_is_imported_but_flagged(env, made, capsys):
    path = edit_manifest(made, lambda c, r: (c, [dict(r[0], likeness_check="")]))
    assert run(made, manifest=path) == 0
    assert "WARNING: likeness_check is not 'yes'" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------- taking items down
def test_retire_hides_an_item_for_users_and_unknown_ids_are_refused(env, made, capsys):
    assert run(made, "--apply") == 0
    assert tool.main(["--retire", "sample-top-01"]) == 0
    assert client.get("/v1/library/items/sample-top-01", headers=auth()).status_code == 200, "dry run changes nothing"
    assert tool.main(["--retire", "sample-top-01", "--apply"]) == 0
    assert client.get("/v1/library/items/sample-top-01", headers=auth()).status_code == 404
    assert "sample-top-01" not in [i["item_id"] for i in listing()] and len(listing()) == 37
    assert (env / "library" / "sample-top-01.v1.png").is_file(), "taking an item down never deletes its file"
    assert tool.main(["--retire", "no-such-item", "--apply"]) == 1
    assert "(no such item)" in capsys.readouterr().out
