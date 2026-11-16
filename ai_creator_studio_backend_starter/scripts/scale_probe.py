"""R-076: scale probe. Builds a throw-away database (library items, work items, review records), then times the list / filter / facet / search endpoints through the application.

  python scripts/scale_probe.py --items 10000 --work 10000 --reviews 50000

Everything lives in a temporary directory that is removed afterwards: it never touches a real database. Prints one JSON object with sizes, build time and per-endpoint milliseconds
(median and worst of --repeat runs) plus the query plans of the hot queries (is an index used?).
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WS, OWNER = "scale-ws", "user-scale"
KINDS = ("model", "garment", "prop", "bg", "pose", "render")
CATEGORIES = ("top", "pants", "outer", "dress", "skirt")
SEASONS = ("spring", "summer", "autumn", "winter")
STATUSES = ("draft", "req", "ok", "chg", "rej", "done")
REVIEW = ("requested", "approved", "changes_requested", "rejected", "withdrawn")


def fill(db, table: str, values: dict) -> dict:
    """The row with every NOT NULL column without a default filled in (so the probe survives a schema change)."""
    out = dict(values)
    for _, name, ctype, notnull, default, pk in db.execute(f'PRAGMA table_info("{table}")').fetchall():
        if name not in out and notnull and default is None and not pk:
            out[name] = 0 if "INT" in (ctype or "").upper() else "x"
    return out


def insert_many(db, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0])
    db.executemany(f'INSERT INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) VALUES ({", ".join("?" * len(cols))})', [[r[c] for c in cols] for r in rows])


def build(db, items: int, work: int, reviews: int) -> dict:
    rnd = random.Random(7)
    now = datetime.now(timezone.utc)
    t = lambda i: (now - timedelta(seconds=i)).isoformat()
    db.execute("INSERT OR IGNORE INTO workspaces(workspace_id, owner_id, created_at) VALUES (?,?,?)", (WS, OWNER, t(0)))
    db.execute("INSERT OR IGNORE INTO workspace_members(workspace_id, user_id, role, created_at) VALUES (?,?,?,?)", (WS, OWNER, "owner", t(0)))
    n_assets = max(items, 1)
    asset_ids = [f"ast_{i:08d}" for i in range(n_assets)]
    insert_many(db, "assets", [fill(db, "assets", {"asset_id": a, "owner_id": OWNER, "workspace_id": WS, "original_filename": f"{a}.png", "storage_key": f"{a}.png", "media_type": "image/png",
                                                  "size_bytes": 1000, "checksum_sha256": "0" * 64, "gltf_version": "", "embedded_binary": 0, "created_at": t(i), "updated_at": t(i)}) for i, a in enumerate(asset_ids)])
    insert_many(db, "workspace_library_items", [fill(db, "workspace_library_items", {
        "item_id": f"wli_{i:08d}", "workspace_id": WS, "asset_id": asset_ids[i], "kind": KINDS[i % len(KINDS)], "origin": "upload", "name": f"항목 {i}", "tags_json": json.dumps([f"t{i % 50}"]),
        "attrs_json": json.dumps({"category": CATEGORIES[i % 5], "season": SEASONS[i % 4], "colors": ["white", "beige"][: 1 + i % 2], "size_no": 85 + i % 20}),
        "created_by": OWNER, "created_at": t(i), "updated_at": t(i)}) for i in range(items)])
    insert_many(db, "work_items", [fill(db, "work_items", {
        "item_id": f"wk_{i:08d}", "workspace_id": WS, "kind": "tryon" if i % 3 else "video", "title": f"작업 {i}", "status": STATUSES[i % 6], "attrs_json": "{}",
        "asset_ids_json": json.dumps([asset_ids[i % n_assets]] + ([asset_ids[(i * 7) % n_assets]] if i % 2 else [])), "created_by": OWNER, "created_at": t(i), "updated_at": t(i)}) for i in range(work)])
    review_rows = []
    for i in range(reviews):
        review_rows.append(fill(db, "asset_reviews", {"review_id": f"rev_{i:08d}", "workspace_id": WS, "asset_id": asset_ids[i % n_assets], "status": REVIEW[(i // n_assets + i) % 5],
                                                    "requested_by": OWNER, "requested_at": t(reviews - i), "updated_at": t(reviews - i)}))
    insert_many(db, "asset_reviews", review_rows)
    return {"assets": n_assets, "library_items": items, "work_items": work, "reviews": reviews}


def plans(db) -> dict:
    queries = {
        "library_by_workspace_kind": ("SELECT * FROM workspace_library_items WHERE workspace_id=? AND kind=? ORDER BY created_at DESC", (WS, "garment")),
        "library_by_workspace": ("SELECT * FROM workspace_library_items WHERE workspace_id=? ORDER BY created_at DESC, item_id", (WS,)),
        "work_items_active": ("SELECT * FROM work_items WHERE workspace_id=? AND archived_at IS NULL ORDER BY updated_at DESC, item_id", (WS,)),
        "work_items_status": ("SELECT * FROM work_items WHERE workspace_id=? AND archived_at IS NULL AND status=? ORDER BY updated_at DESC", (WS, "ok")),
        "reviews_latest_of_asset": ("SELECT status FROM asset_reviews WHERE workspace_id=? AND asset_id=? ORDER BY requested_at DESC, rowid DESC LIMIT 1", (WS, "ast_00000001")),
        "reviews_by_status": ("SELECT * FROM asset_reviews WHERE workspace_id=? AND status=? ORDER BY requested_at DESC", (WS, "approved")),
    }
    return {name: [r[-1] for r in db.execute("EXPLAIN QUERY PLAN " + sql, args).fetchall()] for name, (sql, args) in queries.items()}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--items", type=int, default=10000)
    p.add_argument("--work", type=int, default=10000)
    p.add_argument("--reviews", type=int, default=50000)
    p.add_argument("--repeat", type=int, default=3)
    args = p.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        from app import config
        config.ASSET_STORAGE_DIR, config.OUTPUT_DIR = tmp / "private", tmp / "outputs"
        config.ASSET_DATABASE_PATH, config.GENERATION_DATABASE_PATH = tmp / "scale.sqlite3", None
        config.ASSET_SIGNING_SECRET = "s" * 48
        config.asset_api_tokens = lambda: {"token-scale": OWNER}
        config.RATE_LIMITS_ENABLED = False
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        h = {"Authorization": "Bearer token-scale"}
        assert client.get("/v1/workspaces", headers=h).status_code == 200
        client.post("/v1/workspaces/" + WS + "/work-items", headers=h, json={"kind": "x", "title": "warm"})   # creates the tables through the application's own code
        client.get(f"/v1/workspaces/{WS}/reviews", headers=h)
        client.get(f"/v1/workspaces/{WS}/library", headers=h)
        t0 = time.perf_counter()
        db = sqlite3.connect(config.ASSET_DATABASE_PATH)
        db.execute("PRAGMA journal_mode=WAL")
        sizes = build(db, args.items, args.work, args.reviews)
        db.commit()
        built = round(time.perf_counter() - t0, 2)
        a50 = ",".join(f"ast_{i:08d}" for i in range(0, 100, 1))
        calls = {
            "library list (50)": ("get", f"/v1/workspaces/{WS}/library", {"limit": 50}),
            "library list kind=garment": ("get", f"/v1/workspaces/{WS}/library", {"kind": "garment", "limit": 50}),
            "library list page 100": ("get", f"/v1/workspaces/{WS}/library", {"limit": 50, "offset": 5000}),
            "library attr filter (2 attrs)": ("get", f"/v1/workspaces/{WS}/library", {"attr": ["category:top", "season:summer"], "limit": 50}),
            "library search q": ("get", f"/v1/workspaces/{WS}/library", {"q": "항목 77", "limit": 50}),
            "library facets": ("get", f"/v1/workspaces/{WS}/library/facets", {}),
            "library facets kind=garment": ("get", f"/v1/workspaces/{WS}/library/facets", {"kind": "garment"}),
            "work-items list (50)": ("get", f"/v1/workspaces/{WS}/work-items", {"limit": 50}),
            "work-items status=ok": ("get", f"/v1/workspaces/{WS}/work-items", {"status": "ok", "limit": 50}),
            "work-items q": ("get", f"/v1/workspaces/{WS}/work-items", {"q": "작업 55", "limit": 50}),
            "work-items by asset_id": ("get", f"/v1/workspaces/{WS}/work-items", {"asset_id": "ast_00000042"}),
            "reviews list (50)": ("get", f"/v1/workspaces/{WS}/reviews", {"limit": 50}),
            "reviews status=approved": ("get", f"/v1/workspaces/{WS}/reviews", {"status": "approved", "limit": 50}),
            "reviews status of 100 assets": ("get", f"/v1/workspaces/{WS}/reviews/status", {"asset_ids": a50.split(",")}),
        }
        results = {}
        for name, (_, path, params) in calls.items():
            times, status, total = [], None, None
            for _ in range(args.repeat):
                s = time.perf_counter()
                r = client.get(path, headers=h, params=params)
                times.append((time.perf_counter() - s) * 1000)
                status = r.status_code
                body = r.json() if status == 200 else {}
                total = body.get("total") if isinstance(body, dict) else None
            results[name] = {"status": status, "total": total, "median_ms": round(statistics.median(times)), "worst_ms": round(max(times))}
        report = {"sizes": sizes, "build_seconds": built, "endpoints": results, "plans": plans(db)}
        db.close()
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
