"""Backup -> restore -> read back (SQLite + local files). Uses the real API with the mock provider; no network."""
import hashlib
import importlib.util
import io
import json
import sqlite3
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_restore.py"
spec = importlib.util.spec_from_file_location("backup_restore", SCRIPT)
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)

client = TestClient(app)
WS = "ws-backup"


def auth():
    return {"Authorization": "Bearer token-user-a"}


def png(shade):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (shade, 60, 120)).save(buf, format="PNG")
    return buf.getvalue()


def point_app_at(config, monkeypatch, db, storage, outputs):
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", db)
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", storage)
    monkeypatch.setattr(config, "OUTPUT_DIR", outputs)


@pytest.fixture
def live(tmp_path, monkeypatch):
    import app.config as config
    from app.assets.store import create_workspace
    point_app_at(config, monkeypatch, tmp_path / "live" / "assets.sqlite3", tmp_path / "live" / "private", tmp_path / "live" / "outputs")
    (tmp_path / "live").mkdir()
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a"})
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    create_workspace(WS, "user-a")
    return config


def populate():
    """Create rows in many tables through the API: assets, products, photo drafts with a processed run, a generation job."""
    ids = []
    for shade in (10, 90, 170):
        res = client.post("/v1/assets/images", headers=auth(), data={"workspace_id": WS}, files={"file": (f"p{shade}.png", png(shade), "image/png")})
        assert res.status_code == 201, res.text
        ids.append(res.json()["asset_id"])
    prod = client.post("/v1/products", headers=auth(), json={"workspace_id": WS, "sku": "BK-1", "name": "Backup shirt", "category": "shirt", "image_asset_ids": ids[:2]})
    assert prod.status_code == 201, prod.text
    draft = client.post("/v1/photo-drafts", headers=auth(), json={"workspace_id": WS, "source_asset_id": ids[2], "operation": "ENHANCE", "preserve_identity": True,
                                                                  "preserve_product_geometry": True, "preserve_text_and_logo": True, "output_format": "PNG", "output_count": 1})
    assert draft.status_code == 201, draft.text
    run = client.post(f"/v1/photo-drafts/{draft.json()['draft_id']}/process-local?workspace_id={WS}", headers=auth() | {"Idempotency-Key": "backup-key-1"}, json={})
    assert run.status_code == 200, run.text
    job = client.post("/v1/generation-jobs", headers=auth(), json={"workspace_id": WS, "model_image_url": "https://example.com/m.jpg", "garment_image_url": "https://example.com/g.jpg"})
    assert job.status_code == 202, job.text
    return ids


def snapshot_view():
    """What a user can read back through the API (stable fields only)."""
    assets = client.get(f"/v1/assets?workspace_id={WS}", headers=auth()).json()["items"]
    out = {"assets": sorted((a["asset_id"], a["original_filename"], a["size_bytes"], a["checksum_sha256"]) for a in assets)}
    out["versions"] = {a["asset_id"]: [(v["version_number"], v["checksum_sha256"]) for v in client.get(f"/v1/assets/{a['asset_id']}/versions", headers=auth()).json()["items"]] for a in assets}
    out["provenance"] = {a["asset_id"]: sorted((p["event_type"], p["version_number"]) for p in client.get(f"/v1/assets/{a['asset_id']}/provenance", headers=auth()).json()["items"]) for a in assets}
    out["products"] = sorted((p["sku"], p["name"], tuple(p["image_asset_ids"])) for p in client.get(f"/v1/products?workspace_id={WS}", headers=auth()).json()["items"])
    drafts = client.get(f"/v1/photo-drafts?workspace_id={WS}", headers=auth()).json()["items"]
    out["drafts"] = [(d["draft_id"], tuple(sorted(r["status"] for r in client.get(f"/v1/photo-drafts/{d['draft_id']}/runs?workspace_id={WS}", headers=auth()).json()["items"]))) for d in drafts]
    out["jobs"] = sorted(j["job_id"] for j in client.get(f"/v1/generation-jobs?workspace_id={WS}", headers=auth()).json())
    return out


def table_counts(db_path):
    db = sqlite3.connect(db_path)
    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {n: db.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def make_backup(live, tmp_path):
    return br.backup({"assets": Path(live.ASSET_DATABASE_PATH)}, {"private_assets": Path(live.ASSET_STORAGE_DIR), "outputs": Path(live.OUTPUT_DIR)}, tmp_path / "backups")


def test_backup_restore_round_trip_reads_back_identically_through_the_api(live, tmp_path, monkeypatch):
    populate()
    before_view, before_counts = snapshot_view(), table_counts(live.ASSET_DATABASE_PATH)
    before_files = tree_hashes(live.ASSET_STORAGE_DIR) | {"outputs/" + k: v for k, v in tree_hashes(live.OUTPUT_DIR).items()} if Path(live.OUTPUT_DIR).exists() else tree_hashes(live.ASSET_STORAGE_DIR)
    out = make_backup(live, tmp_path)
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["totals"]["rows"] == sum(before_counts.values()) and manifest["totals"]["file_count"] >= 4
    assert manifest["seconds"]["total"] >= 0 and set(manifest["seconds"]) == {"databases", "files", "total"}
    restored = br.restore(out, tmp_path / "restored")
    assert restored["totals"] == manifest["totals"]
    assert table_counts(restored["databases"]["assets"]) == before_counts
    # point the app at the restored copy and read everything back through the API
    point_app_at(live, monkeypatch, Path(restored["databases"]["assets"]), Path(restored["areas"]["private_assets"]), Path(restored["areas"]["outputs"]))
    assert snapshot_view() == before_view
    assert tree_hashes(restored["areas"]["private_assets"]) == tree_hashes(out / "files" / "private_assets")
    asset_id = before_view["assets"][0][0]
    version = client.get(f"/v1/assets/{asset_id}/versions", headers=auth()).json()["items"][0]
    content = client.get(f"/v1/assets/{asset_id}/versions/{version['version_id']}/preview-content", headers=auth())
    assert content.status_code == 200, content.text
    assert hashlib.sha256(content.content).hexdigest() == version["checksum_sha256"], "restored bytes must match the recorded checksum"
    assert before_files, "the dataset must include stored files"


def test_a_tampered_backup_file_is_refused_and_nothing_is_restored(live, tmp_path):
    populate()
    out = make_backup(live, tmp_path)
    victim = next(p for p in (out / "files" / "private_assets").iterdir() if p.is_file())
    victim.write_bytes(victim.read_bytes() + b"x")
    with pytest.raises(br.BackupVerificationError, match="file changed"):
        br.restore(out, tmp_path / "restored")
    assert not (tmp_path / "restored").exists(), "a refused restore must not create the target"
    with pytest.raises(br.BackupVerificationError):
        br.verify(out)


def test_a_tampered_database_snapshot_is_refused(live, tmp_path):
    populate()
    out = make_backup(live, tmp_path)
    db_file = out / "db" / "assets.sqlite3"
    data = bytearray(db_file.read_bytes()); data[-10] ^= 0xFF; db_file.write_bytes(bytes(data))
    with pytest.raises(br.BackupVerificationError, match="database file changed"):
        br.restore(out, tmp_path / "restored")


def test_a_missing_backup_file_and_a_missing_manifest_are_refused(live, tmp_path):
    populate()
    out = make_backup(live, tmp_path)
    next(p for p in (out / "files" / "private_assets").iterdir() if p.is_file()).unlink()
    with pytest.raises(br.BackupVerificationError, match="missing file"):
        br.verify(out)
    (out / "manifest.json").unlink()
    with pytest.raises(br.BackupVerificationError, match="manifest"):
        br.verify(out)


def test_restore_never_writes_into_a_non_empty_target(live, tmp_path):
    populate()
    out = make_backup(live, tmp_path)
    target = tmp_path / "occupied"
    target.mkdir(); (target / "keep.txt").write_text("precious")
    with pytest.raises(br.BackupError, match="not empty"):
        br.restore(out, target)
    assert (target / "keep.txt").read_text() == "precious" and sorted(p.name for p in target.iterdir()) == ["keep.txt"]


def test_backup_taken_while_another_connection_writes_is_a_consistent_database(live, tmp_path):
    populate()
    stop = threading.Event()
    written = []

    def writer():
        db = sqlite3.connect(live.ASSET_DATABASE_PATH, timeout=30)
        i = 0
        while not stop.is_set():
            db.execute("INSERT INTO workspaces(workspace_id, owner_id, created_at) VALUES(?,?,?)", (f"ws-race-{i}", "user-a", "2026-01-01T00:00:00+00:00"))
            db.commit(); written.append(i); i += 1
        db.close()
    thread = threading.Thread(target=writer); thread.start()
    try:
        out = make_backup(live, tmp_path)
    finally:
        stop.set(); thread.join()
    manifest = br.verify(out)
    restored = br.restore(out, tmp_path / "restored")
    check, _ = br._integrity(Path(restored["databases"]["assets"]))
    assert check == "ok" and len(written) > 0
    counted = table_counts(restored["databases"]["assets"])["workspaces"]
    assert 1 <= counted <= 1 + len(written) and manifest["databases"][0]["integrity_check"] == "ok"


def test_backup_refuses_a_destination_inside_the_data_and_a_missing_database(live, tmp_path):
    populate()
    with pytest.raises(br.BackupError, match="must not contain each other"):
        br.backup({"assets": Path(live.ASSET_DATABASE_PATH)}, {"private_assets": Path(live.ASSET_STORAGE_DIR)}, Path(live.ASSET_STORAGE_DIR) / "inside")
    with pytest.raises(br.BackupError, match="not found"):
        br.backup({"assets": tmp_path / "nope.sqlite3"}, {}, tmp_path / "b")


def test_an_absent_file_area_is_recorded_not_invented(live, tmp_path):
    populate()
    out = br.backup({"assets": Path(live.ASSET_DATABASE_PATH)}, {"private_assets": Path(live.ASSET_STORAGE_DIR), "outputs": tmp_path / "no-outputs-here"}, tmp_path / "backups")
    manifest = json.loads((out / "manifest.json").read_text())
    assert {"area": "outputs", "missing_source": True} in manifest["files"]
    restored = br.restore(out, tmp_path / "restored")
    assert Path(restored["areas"]["outputs"]).is_dir() and list(Path(restored["areas"]["outputs"]).iterdir()) == []


def test_command_line_backup_verify_and_restore(live, tmp_path, capsys):
    populate()
    assert br.main(["backup", "--dest", str(tmp_path / "cli-backups")]) == 0
    backup_dir = next((tmp_path / "cli-backups").iterdir())
    assert br.main(["verify", str(backup_dir)]) == 0
    assert br.main(["restore", str(backup_dir), "--target", str(tmp_path / "cli-restored")]) == 0
    assert (tmp_path / "cli-restored" / "db" / "assets.sqlite3").is_file()
    (backup_dir / "db" / "assets.sqlite3").write_bytes(b"corrupt")
    assert br.main(["verify", str(backup_dir)]) == 1


def test_same_size_corruption_is_caught_by_the_checksum_not_only_by_the_size(live, tmp_path):
    populate()
    out = make_backup(live, tmp_path)
    victim = next(p for p in (out / "files" / "private_assets").iterdir() if p.is_file())
    data = bytearray(victim.read_bytes()); data[len(data) // 2] ^= 0x01; victim.write_bytes(bytes(data))
    assert victim.stat().st_size == len(data)
    with pytest.raises(br.BackupVerificationError, match="file changed"):
        br.verify(out)  # verify() alone must catch it (restore re-checks after copying, which could hide a weak verify)
    with pytest.raises(br.BackupVerificationError, match="file changed"):
        br.restore(out, tmp_path / "restored")


def test_asset_and_generation_database_may_be_the_same_file(live, tmp_path):
    populate()
    same = Path(live.ASSET_DATABASE_PATH)
    out = br.backup({"assets": same, "generation": same}, {"private_assets": Path(live.ASSET_STORAGE_DIR)}, tmp_path / "backups")
    manifest = json.loads((out / "manifest.json").read_text())
    assert [d.get("same_as") for d in manifest["databases"]] == [None, "assets"]
    assert [f.name for f in (out / "db").iterdir()] == ["assets.sqlite3"], "one physical snapshot file and no -wal/-shm side files"
    restored = br.restore(out, tmp_path / "restored")
    assert restored["databases"]["assets"] == restored["databases"]["generation"]


def test_a_snapshot_is_one_self_contained_file_without_wal_side_files(live, tmp_path):
    populate()
    out = make_backup(live, tmp_path)
    assert [f.name for f in (out / "db").iterdir()] == ["assets.sqlite3"]
    br.verify(out)
    assert sorted(f.name for f in (out / "db").iterdir()) == ["assets.sqlite3"], "verifying must not create side files either"
    assert sqlite3.connect(out / "db" / "assets.sqlite3").execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def test_backup_contains_committed_data_that_has_not_been_checkpointed_out_of_the_wal(live, tmp_path):
    """A plain file copy of the database would miss rows that still live only in the -wal file."""
    populate()
    holder = sqlite3.connect(live.ASSET_DATABASE_PATH)
    try:
        holder.execute("PRAGMA wal_autocheckpoint=0")
        holder.execute("INSERT INTO workspaces(workspace_id, owner_id, created_at) VALUES('ws-in-wal','user-a','2026-01-01T00:00:00+00:00')")
        holder.commit()
        wal = Path(str(live.ASSET_DATABASE_PATH) + "-wal")
        assert wal.exists() and wal.stat().st_size > 0, "the row must still be in the WAL for this test to mean anything"
        out = make_backup(live, tmp_path)
    finally:
        holder.close()
    restored = br.restore(out, tmp_path / "restored")
    row = sqlite3.connect(restored["databases"]["assets"]).execute("SELECT workspace_id FROM workspaces WHERE workspace_id='ws-in-wal'").fetchone()
    assert row == ("ws-in-wal",), "the backup lost a committed row that was only in the WAL"


@pytest.mark.parametrize("target_kind", ["database", "file"])
def test_restore_detects_a_copy_that_does_not_match_the_backup(live, tmp_path, monkeypatch, target_kind):
    """Corrupt only the database copy, or only a stored file copy, so each post-copy check is tested on its own."""
    populate()
    out = make_backup(live, tmp_path)
    real_copy2 = br.shutil.copy2

    def corrupting_copy(src, dst, *a, **k):
        result = real_copy2(src, dst, *a, **k)
        is_db = str(dst).endswith(".sqlite3")
        if (target_kind == "database") == is_db:
            data = bytearray(Path(dst).read_bytes())
            if data:
                data[len(data) // 2] ^= 0x01
                Path(dst).write_bytes(bytes(data))
        return result
    monkeypatch.setattr(br.shutil, "copy2", corrupting_copy)
    with pytest.raises(br.BackupVerificationError, match="restored"):
        br.restore(out, tmp_path / "restored")


def test_symlinks_in_a_file_area_are_not_followed_into_the_backup(live, tmp_path):
    populate()
    secret_dir = tmp_path / "outside"
    secret_dir.mkdir()
    (secret_dir / "secret.txt").write_text("not part of the data")
    area = Path(live.ASSET_STORAGE_DIR)
    (area / "link-to-file.txt").symlink_to(secret_dir / "secret.txt")
    (area / "link-to-dir").symlink_to(secret_dir, target_is_directory=True)
    out = make_backup(live, tmp_path)
    manifest = json.loads((out / "manifest.json").read_text())
    assert not [f for f in manifest["files"] if "link-to" in f.get("path", "")]
    assert not list(out.rglob("secret.txt"))
    br.verify(out)


def test_verify_reports_a_file_in_the_backup_that_the_manifest_does_not_list(live, tmp_path):
    populate()
    out = make_backup(live, tmp_path)
    (out / "files" / "outputs" / "smuggled.bin").parent.mkdir(parents=True, exist_ok=True)
    (out / "files" / "outputs" / "smuggled.bin").write_bytes(b"x")
    with pytest.raises(br.BackupVerificationError, match="unlisted file"):
        br.verify(out)
    with pytest.raises(br.BackupVerificationError):
        br.restore(out, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()
