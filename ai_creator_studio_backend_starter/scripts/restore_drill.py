"""R-077: restore drill. backup -> verify -> restore into a NEW empty folder -> integrity checks on the RESTORED copy, with the time of every step (the restore part is the measured RTO).

  python scripts/restore_drill.py --demo small                 # builds a throw-away demo environment, drills it, deletes it
  python scripts/restore_drill.py --demo scale                 # 10,000 / 10,000 / 50,000 rows and 10,000 files
  python scripts/restore_drill.py --db PATH --assets-dir PATH  # drill a copy of a real environment (it is only READ; the restore goes to a temp folder)

Checks on the restored copy (any failure = exit code 1): SQLite ``integrity_check`` ok; ``foreign_key_check`` empty; row count of EVERY table equal to the source; every asset row's file present with
the recorded SHA-256 and size; in demo mode also a smoke test: the application is pointed at the restored copy and lists the library and reads a stored picture back.
Never touches the source (read-only backup), never writes outside its own temp folder, never contacts a network service, never reads secrets. A real environment's backup directory is not used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backup_restore  # noqa: E402

WS, OWNER = "drill-ws", "user-drill"


def sha(path: Path) -> str:
    d = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            d.update(chunk)
    return d.hexdigest()


def row_counts(db_path: Path) -> dict[str, int]:
    db = sqlite3.connect(db_path)
    try:
        return {t: db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    finally:
        db.close()


def check_restored(db_path: Path, assets_dir: Path, source_counts: dict[str, int]) -> dict:
    """The integrity checks on a restored copy. Returns {name: {"ok": bool, ...}}."""
    out: dict[str, dict] = {}
    db = sqlite3.connect(db_path)
    try:
        out["integrity_check"] = {"ok": db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"}
        fk = db.execute("PRAGMA foreign_key_check").fetchall()
        out["foreign_keys"] = {"ok": not fk, "violations": len(fk)}
        counts = row_counts(db_path)
        diff = {t: [source_counts.get(t), counts.get(t)] for t in set(source_counts) | set(counts) if source_counts.get(t) != counts.get(t)}
        out["row_counts"] = {"ok": not diff, "tables": len(counts), "rows": sum(counts.values()), "differences": diff}
        missing, bad, checked = [], [], 0
        if "assets" in counts:
            for aid, key, checksum, size in db.execute("SELECT asset_id, storage_key, checksum_sha256, size_bytes FROM assets WHERE deleted_at IS NULL"):
                path = assets_dir / key
                checked += 1
                if not path.is_file():
                    missing.append(aid)
                elif path.stat().st_size != size or sha(path) != checksum:
                    bad.append(aid)
        out["asset_files"] = {"ok": not missing and not bad, "checked": checked, "missing": len(missing), "hash_or_size_mismatch": len(bad), "examples": (missing + bad)[:3]}
    finally:
        db.close()
    return out


def build_demo(root: Path, size: str) -> tuple[Path, Path]:
    """A throw-away environment made through the application (small) or by bulk insert (scale)."""
    from app import config
    import scale_probe
    config.ASSET_STORAGE_DIR, config.OUTPUT_DIR = root / "assets", root / "outputs"
    config.ASSET_DATABASE_PATH, config.GENERATION_DATABASE_PATH = root / "source.sqlite3", None
    config.ASSET_SIGNING_SECRET = "s" * 48
    config.asset_api_tokens = lambda: {"token-drill": OWNER}
    config.RATE_LIMITS_ENABLED = False
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    from fastapi.testclient import TestClient
    from app.main import app
    from PIL import Image
    import io
    client, h = TestClient(app), {"Authorization": "Bearer token-drill"}
    assert client.post("/v1/workspaces", headers=h, json={"workspace_id": WS}).status_code == 201
    for i in range(6 if size == "small" else 3):
        buf = io.BytesIO(); Image.new("RGB", (40, 40), (i * 30 % 250, 90, 160)).save(buf, format="PNG")
        r = client.post(f"/v1/workspaces/{WS}/library", headers=h, data={"kind": "model", "name": f"m{i}", "rights_confirmed": "true", "attrs": json.dumps({"i": i})}, files={"file": (f"m{i}.png", buf.getvalue(), "image/png")})
        assert r.status_code == 201, r.text
        a = r.json()["asset_id"]
        rv = client.post(f"/v1/workspaces/{WS}/reviews", headers=h, json={"asset_id": a})
        client.post(f"/v1/workspaces/{WS}/reviews/{rv.json()['review_id']}/approve", headers=h, json={})
        client.post(f"/v1/workspaces/{WS}/work-items", headers=h, json={"kind": "tryon", "title": f"w{i}", "status": "ok", "asset_ids": [a]})
    if size == "scale":
        db = sqlite3.connect(config.ASSET_DATABASE_PATH)
        scale_probe.build(db, 10000, 10000, 50000)
        db.commit()
        assets_dir = config.ASSET_STORAGE_DIR
        assets_dir.mkdir(parents=True, exist_ok=True)
        rows = db.execute("SELECT asset_id FROM assets WHERE storage_key LIKE 'ast_0%'").fetchall()
        for (aid,) in rows:                       # real tiny files for the bulk-inserted rows, so the hash check is real
            data = f"drill file {aid}".encode()
            (assets_dir / f"{aid}.png").write_bytes(data)
            db.execute("UPDATE assets SET checksum_sha256=?, size_bytes=? WHERE asset_id=?", (hashlib.sha256(data).hexdigest(), len(data), aid))
        db.commit()
        db.close()
    return Path(config.ASSET_DATABASE_PATH), Path(config.ASSET_STORAGE_DIR)


def smoke(restored_db: Path, restored_assets: Path) -> dict:
    """The application, pointed at the RESTORED copy, answers: lists the library and reads a stored picture back."""
    from app import config
    config.ASSET_DATABASE_PATH, config.ASSET_STORAGE_DIR = restored_db, restored_assets
    from fastapi.testclient import TestClient
    from app.main import app
    client, h = TestClient(app), {"Authorization": "Bearer token-drill"}
    lib = client.get(f"/v1/workspaces/{WS}/library", headers=h, params={"limit": 5})
    ok = lib.status_code == 200 and lib.json()["total"] >= 1
    pic = None
    if ok:
        asset_id = lib.json()["items"][0]["asset_id"]
        vid = client.get(f"/v1/assets/{asset_id}/versions", headers=h).json()
        vid = (vid["items"] if isinstance(vid, dict) else vid)[0]["version_id"]
        pic = client.get(f"/v1/assets/{asset_id}/versions/{vid}/preview-content", headers=h)
    return {"ok": bool(ok and pic is not None and pic.status_code == 200 and len(pic.content) > 0), "library_total": lib.json().get("total") if lib.status_code == 200 else None,
            "picture_status": pic.status_code if pic is not None else None}


def drill(db_path: Path, assets_dir: Path, work: Path, with_smoke: bool = False) -> dict:
    t = {}
    source_counts = row_counts(db_path)
    s = time.perf_counter()
    backup_dir = backup_restore.backup({"assets": db_path}, {"assets": assets_dir}, work / "backups")
    t["backup"] = time.perf_counter() - s
    s = time.perf_counter()
    manifest = backup_restore.verify(backup_dir)
    t["verify"] = time.perf_counter() - s
    s = time.perf_counter()
    restored = backup_restore.restore(backup_dir, work / "restored")
    t["restore"] = time.perf_counter() - s
    r_db = Path(restored["databases"]["assets"])
    r_assets = Path(restored["areas"]["assets"])
    s = time.perf_counter()
    checks = check_restored(r_db, r_assets, source_counts)
    t["checks"] = time.perf_counter() - s
    if with_smoke:
        s = time.perf_counter()
        checks["application_smoke"] = smoke(r_db, r_assets)
        t["smoke"] = time.perf_counter() - s
    totals = manifest.get("totals", {})
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks, "sizes": totals,
            "seconds": {k: round(v, 2) for k, v in t.items()}, "rto_seconds": round(t["verify"] + t["restore"] + t["checks"] + t.get("smoke", 0), 2),
            "rto_note": "RTO = verify + restore + integrity checks (+ application smoke) on this machine; the backup step is not part of recovery time"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--demo", choices=["small", "scale"])
    p.add_argument("--db", type=Path)
    p.add_argument("--assets-dir", type=Path)
    p.add_argument("--out", type=Path, help="also write the JSON report here")
    args = p.parse_args(argv)
    if bool(args.demo) == bool(args.db):
        p.error("give exactly one of --demo or --db")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if args.demo:
            db_path, assets_dir = build_demo(work / "env", args.demo)
            report = drill(db_path, assets_dir, work, with_smoke=True)
        else:
            if not args.assets_dir:
                p.error("--assets-dir is required with --db")
            report = drill(args.db, args.assets_dir, work)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
