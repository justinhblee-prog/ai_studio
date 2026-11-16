"""R-076: the scale probe runs (small), every list endpoint answers with the right totals, the hot queries use indexes, and held assets stay hidden without a connection per row."""
import json

import pytest

from app import config, takedown
from scripts import scale_probe


def test_the_probe_runs_at_small_size_with_correct_totals_and_indexed_queries(tmp_path, monkeypatch, capsys):
    for name in ("ASSET_STORAGE_DIR", "OUTPUT_DIR", "ASSET_DATABASE_PATH", "GENERATION_DATABASE_PATH", "ASSET_SIGNING_SECRET", "asset_api_tokens", "RATE_LIMITS_ENABLED"):
        monkeypatch.setattr(config, name, getattr(config, name))      # the probe replaces these in this process: restore them afterwards
    assert scale_probe.main(["--items", "300", "--work", "200", "--reviews", "900", "--repeat", "1"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["sizes"] == {"assets": 300, "library_items": 300, "work_items": 200, "reviews": 900}
    ep = report["endpoints"]
    assert all(v["status"] == 200 for v in ep.values()), ep
    assert ep["library list (50)"]["total"] == 300 and ep["library list kind=garment"]["total"] == 50
    assert ep["work-items list (50)"]["total"] == 201 and ep["reviews list (50)"]["total"] == 900
    assert ep["library attr filter (2 attrs)"]["total"] == len([i for i in range(300) if i % 5 == 0 and i % 4 == 1])
    for name in ("library_by_workspace_kind", "work_items_active", "work_items_status", "reviews_latest_of_asset", "reviews_by_status"):
        assert any("USING INDEX" in step for step in report["plans"][name]), (name, report["plans"][name])


def test_hidden_ids_returns_exactly_the_assets_that_are_held_and_not_the_viewers_own(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "p")
    from app.assets import store
    store.initialize()
    with store._connect() as db:
        for aid, owner in (("a1", "user-a"), ("a2", "user-b"), ("a3", "user-b")):
            db.execute("INSERT INTO assets(asset_id, owner_id, workspace_id, original_filename, storage_key, media_type, size_bytes, checksum_sha256, gltf_version, embedded_binary, created_at) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (aid, owner, "w", aid, aid, "image/png", 1, "0" * 64, "", 0, "2026-01-01T00:00:00+00:00"))
        db.execute("INSERT INTO asset_takedowns(asset_id, workspace_id, state, since, updated_at) VALUES ('a1','w','under_review','x','x')")
        db.execute("INSERT INTO asset_takedowns(asset_id, workspace_id, state, since, updated_at) VALUES ('a2','w','under_review','x','x')")
        db.execute("INSERT INTO asset_takedowns(asset_id, workspace_id, state, since, updated_at) VALUES ('a3','w','removed','x','x')")
    assert takedown.hidden_ids("user-a") == {"a2", "a3"}, "a1 is held but it is the viewer's own: still visible to the owner; removed is hidden from everyone"
    assert takedown.hidden_ids("user-b") == {"a1", "a3"}, "a2 is user-b's own held asset: visible to its owner; a1 is another user's held asset and a3 is removed: hidden"
    assert takedown.hidden_ids(None) == {"a1", "a2", "a3"}
    for aid in ("a1", "a2", "a3"):
        for user in ("user-a", "user-b", None):
            assert (aid not in takedown.hidden_ids(user)) == takedown.visible_to(aid, user), (aid, user)
