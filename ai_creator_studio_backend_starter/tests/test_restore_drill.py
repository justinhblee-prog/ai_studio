"""R-077: the restore drill passes on a healthy environment and FAILS (exit code 1 / exception) when the backup or the restored copy is damaged."""
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from app import config
from scripts import backup_restore, restore_drill


@pytest.fixture
def demo(tmp_path, monkeypatch):
    for name in ("ASSET_STORAGE_DIR", "OUTPUT_DIR", "ASSET_DATABASE_PATH", "GENERATION_DATABASE_PATH", "ASSET_SIGNING_SECRET", "asset_api_tokens", "RATE_LIMITS_ENABLED"):
        monkeypatch.setattr(config, name, getattr(config, name))      # the demo builder replaces these in this process: restore them afterwards
    db_path, assets = restore_drill.build_demo(tmp_path / "env", "small")
    return tmp_path, db_path, assets


def test_a_healthy_environment_drills_clean_with_every_check_and_the_application_smoke(demo):
    tmp, db_path, assets = demo
    report = restore_drill.drill(db_path, assets, tmp / "work", with_smoke=True)
    assert report["ok"] is True
    checks = report["checks"]
    assert set(checks) == {"integrity_check", "foreign_keys", "row_counts", "asset_files", "application_smoke"} and all(c["ok"] for c in checks.values())
    assert checks["row_counts"]["differences"] == {} and checks["row_counts"]["rows"] > 50 and checks["asset_files"]["checked"] == 6
    assert checks["application_smoke"]["library_total"] == 6 and checks["application_smoke"]["picture_status"] == 200
    assert set(report["seconds"]) == {"backup", "verify", "restore", "checks", "smoke"} and report["rto_seconds"] >= 0 and "backup step is not part" in report["rto_note"]
    assert report["sizes"]["file_count"] > 0


def test_the_source_is_only_read(demo):
    tmp, db_path, assets = demo
    before = {p.name: p.read_bytes() for p in assets.iterdir() if p.is_file()}
    counts = restore_drill.row_counts(db_path)
    restore_drill.drill(db_path, assets, tmp / "work")
    assert {p.name: p.read_bytes() for p in assets.iterdir() if p.is_file()} == before and restore_drill.row_counts(db_path) == counts


def test_a_damaged_backup_stops_the_drill_before_any_restore(demo, monkeypatch):
    tmp, db_path, assets = demo
    real = backup_restore.backup

    def damaging(*a, **k):
        out = real(*a, **k)
        victim = next((out / "files").rglob("*.png"))
        victim.write_bytes(victim.read_bytes() + b"x")            # a bit of rot in the backup
        return out

    monkeypatch.setattr(backup_restore, "backup", damaging)
    with pytest.raises(backup_restore.BackupVerificationError):
        restore_drill.drill(db_path, assets, tmp / "work")
    assert not (tmp / "work" / "restored").exists(), "nothing was restored from a damaged backup"


def test_the_checks_on_a_restored_copy_catch_each_kind_of_damage(demo):
    tmp, db_path, assets = demo
    report = restore_drill.drill(db_path, assets, tmp / "work")
    assert report["ok"]
    restored = next((tmp / "work" / "restored").rglob("*.sqlite3"))
    r_assets = tmp / "work" / "restored" / "files" / "assets"
    counts = restore_drill.row_counts(db_path)
    ok = restore_drill.check_restored(restored, r_assets, counts)
    assert all(c["ok"] for c in ok.values())
    # a missing file
    gone = next(r_assets.rglob("*.png")); keep = gone.read_bytes(); gone.unlink()
    broken = restore_drill.check_restored(restored, r_assets, counts)
    assert broken["asset_files"]["ok"] is False and broken["asset_files"]["missing"] == 1
    gone.write_bytes(keep + b"x")
    assert restore_drill.check_restored(restored, r_assets, counts)["asset_files"]["hash_or_size_mismatch"] == 1
    gone.write_bytes(keep)
    # a missing row
    with sqlite3.connect(restored) as db:
        db.execute("DELETE FROM asset_reviews")
    diff = restore_drill.check_restored(restored, r_assets, counts)["row_counts"]
    assert diff["ok"] is False and "asset_reviews" in diff["differences"]
    # a dangling foreign key
    with sqlite3.connect(restored) as db:
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("DELETE FROM workspaces")
    fk = restore_drill.check_restored(restored, r_assets, counts)["foreign_keys"]
    assert fk["ok"] is False and fk["violations"] > 0


def test_the_command_line_prints_a_report_and_exits_zero_or_one(tmp_path, monkeypatch, capsys):
    for name in ("ASSET_STORAGE_DIR", "OUTPUT_DIR", "ASSET_DATABASE_PATH", "GENERATION_DATABASE_PATH", "ASSET_SIGNING_SECRET", "asset_api_tokens", "RATE_LIMITS_ENABLED"):
        monkeypatch.setattr(config, name, getattr(config, name))
    out = tmp_path / "report.json"
    assert restore_drill.main(["--demo", "small", "--out", str(out)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["ok"] is True and json.loads(out.read_text(encoding="utf-8")) == printed
    for bad in ([], ["--demo", "small", "--db", "x"], ["--db", "x"]):
        with pytest.raises(SystemExit):
            restore_drill.main(bad)
    monkeypatch.setattr(restore_drill, "drill", lambda *a, **k: {"ok": False})
    assert restore_drill.main(["--demo", "small"]) == 1


def test_a_real_environment_is_drilled_without_touching_it(demo):
    tmp, db_path, assets = demo
    shutil.copytree(assets, tmp / "copy_assets")
    shutil.copy2(db_path, tmp / "copy.sqlite3")
    report = restore_drill.drill(tmp / "copy.sqlite3", tmp / "copy_assets", tmp / "work2")
    assert report["ok"] and "application_smoke" not in report["checks"], "the smoke test needs the demo's own token, so it runs in demo mode only"
