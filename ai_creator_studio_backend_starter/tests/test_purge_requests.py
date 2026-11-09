import sqlite3
from io import BytesIO
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from scripts import purge_requests as purge

client = TestClient(app)


def auth(t):
    return {"Authorization": f"Bearer token-{t}"}


def char_body():
    return {"identity": {"name": "Mina", "gender": "female", "face_shape": "oval", "hairstyle": "long",
                         "body_type": "athletic", "skin_tone": "medium"},
            "outfits": [{"id": "o1", "name": "Casual", "category": "casual", "top": "shirt"}],
            "active_outfit_id": "o1", "asset_ids": []}


def upload(user, ws):
    buf = BytesIO(); Image.new("RGB", (16, 16), (1, 2, 3)).save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=auth(user), data={"workspace_id": ws},
                    files={"file": ("a.png", buf.getvalue(), "application/octet-stream")})
    assert r.status_code in (200, 201), r.text
    return r.json()["asset_id"]


def job(user, ws, n=0):
    r = client.post("/v1/generation-jobs", headers=auth(user), json={
        "workspace_id": ws, "prompt": f"p{n}",
        "model_image_url": "https://images.example.org/m.png",
        "garment_image_url": "https://images.example.org/g.png"})
    assert r.status_code == 202, r.text
    return r.json()["job_id"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    for ws, u in (("pa", "a"), ("pb", "b"), ("sh", "a")):
        assert client.post("/v1/workspaces", headers=auth(u), json={"workspace_id": ws}).status_code == 201
    assert client.post("/v1/workspaces/sh/members", headers=auth("a"), json={"user_id": "user-b", "role": "editor"}).status_code == 201
    out = {}
    for u, ws in (("a", "pa"), ("b", "pb"), ("a", "sh")):
        out[ws] = {"asset": upload(u, ws), "job": job(u, ws)}
        assert client.post(f"/v1/workspaces/{ws}/characters", headers=auth(u), json=char_body()).status_code == 201
    for u in ("a", "b"):
        client.get("/v1/me/legal-status", headers=auth(u))
        client.put("/v1/me/consents/ai_training", headers=auth(u), json={"granted": True})
    (tmp_path / "outputs").mkdir(exist_ok=True)
    db = sqlite3.connect(tmp_path / "a.sqlite3", isolation_level=None)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("UPDATE generation_jobs SET status='failed'")
    return tmp_path, db, out


def request(db, user, scope, ws=None, days_ago=10, rid=None):
    rid = rid or f"del_{user}_{scope}"
    at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    db.execute("INSERT INTO deletion_requests(request_id,user_id,scope,workspace_id,status,reason,requested_at) VALUES(?,?,?,?,?,?,?)",
               (rid, user, scope, ws, "pending", "why", at))
    return rid


def snapshot(db, where_ws=None):
    out = {}
    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        out[t] = db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    return out


def run(tmp_path, *extra):
    return purge.main(["--db", str(tmp_path / "a.sqlite3"), "--assets-dir", str(tmp_path / "private"),
                       "--outputs-dir", str(tmp_path / "outputs"), *extra])


def files(tmp_path):
    return sorted(p.name for p in (tmp_path / "private").glob("ast_*"))


def ws_rows(db, ws):
    tot = 0
    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        if t in ("deletion_requests", "workspaces", "workspace_members"):
            continue
        if "workspace_id" in [r[1] for r in db.execute(f'PRAGMA table_info("{t}")')]:
            tot += db.execute(f'SELECT COUNT(*) FROM "{t}" WHERE workspace_id=?', (ws,)).fetchone()[0]
    return tot


def orphans(db):
    return db.execute("PRAGMA foreign_key_check").fetchall()


def test_dry_run_and_missing_confirm_change_nothing(env, capsys):
    tmp, db, _ = env
    request(db, "user-b", "workspace_content", "pb")
    before, f = snapshot(db), files(tmp)
    assert run(tmp) == 0
    assert "dry-run" in capsys.readouterr().out
    assert snapshot(db) == before and files(tmp) == f
    with pytest.raises(SystemExit):
        run(tmp, "--apply")
    assert snapshot(db) == before and files(tmp) == f


def test_grace_period_is_enforced(env):
    tmp, db, _ = env
    rid = request(db, "user-b", "account", days_ago=2)
    assert run(tmp, "--apply", "--confirm", rid) == 2
    assert ws_rows(db, "pb") > 0
    assert run(tmp, "--apply", "--confirm", rid, "--grace-days", "1") == 0
    assert ws_rows(db, "pb") == 0


def test_workspace_content_purge_keeps_other_workspaces_and_the_shell(env):
    tmp, db, out = env
    rid = request(db, "user-b", "workspace_content", "pb")
    keep = snapshot(db)
    keep_other = {ws: ws_rows(db, ws) for ws in ("pa", "sh")}
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert ws_rows(db, "pb") == 0 and orphans(db) == []
    assert {ws: ws_rows(db, ws) for ws in ("pa", "sh")} == keep_other
    assert db.execute("SELECT COUNT(*) FROM workspaces WHERE workspace_id='pb'").fetchone()[0] == 1
    assert out["pb"]["asset"] not in " ".join(files(tmp))
    assert out["pa"]["asset"] in " ".join(files(tmp))
    assert db.execute("SELECT status,reason FROM deletion_requests WHERE request_id=?", (rid,)).fetchone() == ("completed", None)
    assert snapshot(db)["legal_acceptances"] == keep["legal_acceptances"]


def test_account_purge_deletes_sole_workspace_and_anonymizes_shared(env):
    tmp, db, out = env
    db.execute("UPDATE workspace_members SET role='owner' WHERE workspace_id='sh' AND user_id='user-b'")
    rid = request(db, "user-a", "account")
    other_before = ws_rows(db, "pb")
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert orphans(db) == []
    assert db.execute("SELECT COUNT(*) FROM workspaces WHERE workspace_id='pa'").fetchone()[0] == 0
    assert ws_rows(db, "pa") == 0
    assert ws_rows(db, "pb") == other_before
    assert db.execute("SELECT COUNT(*) FROM workspace_members WHERE user_id='user-a'").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM consents WHERE user_id='user-a'").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM consents WHERE user_id='user-b'").fetchone()[0] > 0
    assert db.execute("SELECT COUNT(*) FROM assets WHERE owner_id='user-a'").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM assets WHERE owner_id='deleted-user'").fetchone()[0] >= 1
    assert db.execute("SELECT COUNT(*) FROM generation_jobs WHERE owner_id='user-a'").fetchone()[0] == 0
    assert out["pa"]["asset"] not in " ".join(files(tmp))
    # the other user's references are untouched by anonymization
    assert db.execute("SELECT COUNT(*) FROM assets WHERE owner_id='user-b'").fetchone()[0] >= 1
    assert db.execute("SELECT COUNT(*) FROM generation_jobs WHERE owner_id='user-b'").fetchone()[0] >= 1


def test_keep_history_retains_consent_rows(env):
    tmp, db, _ = env
    rid = request(db, "user-b", "account")
    assert run(tmp, "--apply", "--confirm", rid, "--keep-history") == 0
    assert db.execute("SELECT COUNT(*) FROM consents WHERE user_id='user-b'").fetchone()[0] > 0


def test_last_owner_with_other_members_is_blocked(env, capsys):
    tmp, db, _ = env
    rid = request(db, "user-a", "account")
    before = snapshot(db)
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert "LAST_OWNER:sh" in capsys.readouterr().out
    assert snapshot(db) == before
    assert db.execute("SELECT status FROM deletion_requests WHERE request_id=?", (rid,)).fetchone()[0] == "pending"


def test_job_in_progress_blocks_and_nothing_is_deleted(env, capsys):
    tmp, db, _ = env
    db.execute("UPDATE generation_jobs SET status='queued' WHERE workspace_id='pb'")
    rid = request(db, "user-b", "workspace_content", "pb")
    before = snapshot(db)
    run(tmp, "--apply", "--confirm", rid)
    assert "JOB_IN_PROGRESS" in capsys.readouterr().out
    assert snapshot(db) == before


def test_unmapped_table_fails_closed(env, capsys):
    tmp, db, _ = env
    db.execute("CREATE TABLE secret_notes (note TEXT)")
    db.execute("INSERT INTO secret_notes VALUES ('x')")
    rid = request(db, "user-b", "workspace_content", "pb")
    before = snapshot(db)
    run(tmp, "--apply", "--confirm", rid)
    assert "UNMAPPED_TABLE:secret_notes" in capsys.readouterr().out
    assert snapshot(db) == before


def test_file_delete_failure_keeps_request_pending(env, monkeypatch, capsys):
    from pathlib import Path
    tmp, db, out = env
    real = Path.unlink

    def boom(self, *a, **k):
        if self.name.startswith(out["pb"]["asset"]):
            raise PermissionError("locked")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", boom)
    rid = request(db, "user-b", "workspace_content", "pb")
    run(tmp, "--apply", "--confirm", rid)
    assert "retry:" in capsys.readouterr().out
    assert db.execute("SELECT status FROM deletion_requests WHERE request_id=?", (rid,)).fetchone()[0] == "pending"
    assert ws_rows(db, "pb") == 0  # rows are gone; rerun only has files left


def test_output_files_are_removed_with_generation_outputs(env):
    tmp, db, out = env
    jid = out["pb"]["job"]
    key = f"{jid}.attempt-1.deadbeef.png"
    (tmp / "outputs" / key).write_bytes(b"png")
    db.execute("INSERT INTO generation_outputs(output_id,job_id,storage_key,media_type,size_bytes,created_at,checksum_sha256) VALUES('o1',?,?,?,?,?,?)",
               (jid, key, "image/png", 3, "2026-01-01", "x"))
    rid = request(db, "user-b", "workspace_content", "pb")
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert not (tmp / "outputs" / key).exists()
    assert db.execute("SELECT COUNT(*) FROM generation_outputs").fetchone()[0] == 0


def test_storage_key_escaping_the_root_is_never_deleted(env):
    tmp, db, out = env
    victim = tmp / "victim.txt"
    victim.write_text("keep me")
    db.execute("PRAGMA foreign_keys=OFF")
    db.execute("UPDATE asset_versions SET storage_key='../victim.txt' WHERE workspace_id='pb'")
    db.execute("PRAGMA foreign_keys=ON")
    rid = request(db, "user-b", "workspace_content", "pb")
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert victim.exists()


def test_missing_deletion_requests_table_means_nothing_to_do(tmp_path, capsys):
    db = tmp_path / "empty.sqlite3"
    sqlite3.connect(db).close()
    assert purge.main(["--db", str(db), "--assets-dir", str(tmp_path / "p"), "--outputs-dir", str(tmp_path / "o")]) == 0
    assert "dry-run" in capsys.readouterr().out


def test_account_purge_handles_tables_created_by_products_projects_and_photo_drafts(env):
    """The schema grows lazily as features are used; every table the app creates must be mapped, never silently skipped."""
    tmp, db, out = env
    aid = out["pb"]["asset"]
    assert client.post("/v1/products", headers=auth("b"), json={"workspace_id": "pb", "sku": "PX-1", "name": "Shirt", "category": "shirt", "image_asset_ids": [aid]}).status_code == 201
    assert client.post("/v1/projects", headers=auth("b"), json={"workspace_id": "pb", "name": "Spring"}).status_code == 201
    draft = client.post("/v1/photo-drafts", headers=auth("b"), json={"workspace_id": "pb", "source_asset_id": aid, "operation": "ENHANCE", "preserve_identity": True,
                                                                     "preserve_product_geometry": True, "preserve_text_and_logo": True, "output_format": "PNG", "output_count": 1})
    assert draft.status_code == 201, draft.text
    tables = {t for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"products", "projects", "photo_drafts"} <= tables, sorted(tables)  # the features really created their tables
    pre = {t: db.execute(f'SELECT COUNT(*) FROM "{t}" WHERE workspace_id=?', ("pb",)).fetchone()[0] for t in ("products", "projects", "photo_drafts")}
    assert all(pre.values()), pre
    rid = request(db, "user-b", "account")
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert db.execute("SELECT status FROM deletion_requests WHERE request_id=?", (rid,)).fetchone()[0] == "completed"
    assert ws_rows(db, "pb") == 0
    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        for c in ("actor_id", "owner_id", "created_by"):
            if c in [r[1] for r in db.execute(f'PRAGMA table_info("{t}")')]:
                assert db.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{c}"=?', ("user-b",)).fetchone()[0] == 0, (t, c)
    assert orphans(db) == []
