"""R-071: demo data for a DEVELOPMENT environment (adapter tests and demo screens). Idempotent. Refuses to touch anything that could be real.

  DEMO_SEED=1 ASSET_DATABASE_PATH=./demo.sqlite3 ASSET_STORAGE_DIR=./demo_assets python scripts/seed_demo.py

It writes through the application's own API (so every rule of the server applies), in this process only, with FAKE demo sign-in tokens that exist nowhere else. What it creates, in ONE workspace ``demo-studio``:
  * 5 users: owner, admin, 2 editors, viewer
  * library items: 3 each of model / garment / bg, 2 of 3d / render (pictures drawn here, a tiny valid .glb), with attributes
  * work items in all six statuses (draft, req, ok, chg, rej, done), linked to assets
  * asset reviews in four states: requested, approved, changes requested, rejected
  * a free market listing (published) and one report on it
Safety (every one of these makes it refuse, creating nothing):
  * DEMO_SEED=1 must be set on purpose
  * SUPABASE_URL set (a real sign-in service is connected), DATABASE_BACKEND other than sqlite, PROVIDER_MODE other than mock, APP_ENV / ENVIRONMENT naming production or staging
  * the database already holds any workspace that is not a demo workspace (ids starting ``demo-``)
  * a half-finished earlier seed (it never repairs or deletes; start from a fresh database)
Running it again on a complete seed changes nothing.
"""
from __future__ import annotations

import io
import json
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WORKSPACE = "demo-studio"
MARKER_TITLE = "demo-seed-complete"
USERS = {"owner": ("demo-token-owner", "demo-owner"), "admin": ("demo-token-admin", "demo-admin"), "editor": ("demo-token-editor", "demo-editor"),
         "editor2": ("demo-token-editor2", "demo-editor2"), "viewer": ("demo-token-viewer", "demo-viewer")}
ROLES = {"admin": "admin", "editor": "editor", "editor2": "editor", "viewer": "viewer"}
PROD_WORDS = ("prod", "production", "staging", "live")


def refusals() -> list[str]:
    """Why this environment must not be seeded (empty = allowed)."""
    from app import config
    why = []
    if os.getenv("DEMO_SEED") != "1":
        why.append("DEMO_SEED=1 is not set")
    if os.getenv("SUPABASE_URL", "").strip() or config.SUPABASE_URL:
        why.append("SUPABASE_URL is set: a real sign-in service is connected")
    if os.getenv("DATABASE_BACKEND", config.DATABASE_BACKEND).strip().lower() != "sqlite":
        why.append("DATABASE_BACKEND is not sqlite")
    if config.PROVIDER_MODE != "mock":
        why.append("PROVIDER_MODE is not mock")
    for name in ("APP_ENV", "ENVIRONMENT", "ENV", "VERCEL_ENV"):
        if any(w in os.getenv(name, "").lower() for w in PROD_WORDS):
            why.append(f"{name} names a production-like environment")
    return why


def database_state() -> tuple[list[str], bool, bool]:
    """(workspaces that are not demo workspaces, whether the seed marker exists, whether the demo workspace exists at all)."""
    import sqlite3
    from app import config
    path = Path(config.ASSET_DATABASE_PATH)
    if not path.exists():
        return [], False, False
    db = sqlite3.connect(path)
    try:
        has = lambda t: db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone() is not None
        foreign = [r[0] for r in db.execute("SELECT workspace_id FROM workspaces").fetchall() if not r[0].startswith("demo-")] if has("workspaces") else []
        marker = bool(has("work_items") and db.execute("SELECT 1 FROM work_items WHERE workspace_id=? AND title=?", (WORKSPACE, MARKER_TITLE)).fetchone())
        started = bool(has("workspaces") and db.execute("SELECT 1 FROM workspaces WHERE workspace_id=?", (WORKSPACE,)).fetchone())
        return foreign, marker, started
    finally:
        db.close()


def png(color, size=(240, 320), shape="rect"):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, color)
    d = ImageDraw.Draw(im)
    w, h = size
    if shape == "rect":
        d.rectangle((w * .25, h * .2, w * .75, h * .8), fill=tuple(min(255, c + 50) for c in color))
    else:
        d.ellipse((w * .2, h * .15, w * .8, h * .6), fill=tuple(max(0, c - 40) for c in color))
    buf = io.BytesIO(); im.save(buf, format="PNG"); return buf.getvalue()


def glb() -> bytes:
    raw = json.dumps({"asset": {"version": "2.0"}}).encode()
    raw += b" " * ((4 - len(raw) % 4) % 4)
    chunk = struct.pack("<II", len(raw), 0x4E4F534A) + raw
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk


def main(argv=None) -> int:
    from app import config
    why = refusals()
    if why:
        print("seed_demo: refused: " + "; ".join(why))
        return 2
    foreign, marker, started = database_state()
    if foreign:
        print(f"seed_demo: refused: the database already holds non-demo workspaces ({', '.join(foreign[:3])}{'...' if len(foreign) > 3 else ''})")
        return 2
    if marker:
        print("seed_demo: the demo data is already there; nothing changed")
        return 0
    if started:
        print("seed_demo: refused: an earlier seed was left half-finished; start from a fresh database (nothing is repaired or deleted here)")
        return 2

    from fastapi.testclient import TestClient
    tokens = {token: user for token, user in USERS.values()}
    config.asset_api_tokens = lambda: dict(tokens)          # this process only: fake demo tokens
    config.RATE_LIMITS_ENABLED = False
    from app.main import app
    client = TestClient(app)
    hd = {role: {"Authorization": f"Bearer {tok}"} for role, (tok, _) in USERS.items()}

    def ok(response, what):
        if response.status_code not in (200, 201, 202):
            raise SystemExit(f"seed_demo: {what} failed ({response.status_code}): {response.text[:200]}")
        return response.json()

    ok(client.post("/v1/workspaces", headers=hd["owner"], json={"workspace_id": WORKSPACE}), "workspace")
    for role, r in ROLES.items():
        ok(client.post(f"/v1/workspaces/{WORKSPACE}/members", headers=hd["owner"], json={"user_id": USERS[role][1], "role": r}), f"member {role}")

    def upload(kind, name, content, filename, attrs, who="editor"):
        data = {"kind": kind, "name": name, "rights_confirmed": "true", "attrs": json.dumps(attrs)}
        mime = "model/gltf-binary" if kind == "3d" else "image/png"
        return ok(client.post(f"/v1/workspaces/{WORKSPACE}/library", headers=hd[who], data=data, files={"file": (filename, content, mime)}), f"library {name}")

    items = {}
    palette = [(200, 90, 90), (90, 160, 210), (120, 190, 120)]
    for i, (name, gender) in enumerate((("모델 하늘", "female"), ("모델 도윤", "male"), ("모델 서아", "female"))):
        items[f"model{i}"] = upload("model", name, png(palette[i], shape="oval"), f"model{i}.png", {"gender": gender, "age": 25 + i, "demo": "seed"})
    for i, (name, cat) in enumerate((("린넨 셔츠", "top"), ("데님 팬츠", "bottom"), ("울 코트", "outer"))):
        items[f"garment{i}"] = upload("garment", name, png(palette[(i + 1) % 3]), f"garment{i}.png", {"category": cat, "season": ["summer", "all", "winter"][i], "demo": "seed"})
    for i, (name, place) in enumerate((("스튜디오 흰 배경", "indoor"), ("해변", "outdoor"), ("거리", "outdoor"))):
        items[f"bg{i}"] = upload("bg", name, png((235 - 40 * i,) * 3, (320, 240)), f"bg{i}.png", {"place": place, "demo": "seed"})
    for i in range(2):
        items[f"3d{i}"] = upload("3d", f"의자 {i + 1}", glb(), f"chair{i}.glb", {"demo": "seed"})
        items[f"render{i}"] = upload("render", f"결과 {i + 1}", png((180, 140 + 30 * i, 100)), f"render{i}.png", {"service": "tryon", "style": "photo", "demo": "seed"})

    asset = lambda key: items[key]["asset_id"]
    reviews = {}
    for state, key in (("requested", "render0"), ("approved", "render1"), ("changes_requested", "garment0"), ("rejected", "garment1")):
        rv = ok(client.post(f"/v1/workspaces/{WORKSPACE}/reviews", headers=hd["editor"], json={"asset_id": asset(key), "comment": "시연용 검수 요청"}), f"review {state}")
        reviews[state] = rv["review_id"]
    ok(client.post(f"/v1/workspaces/{WORKSPACE}/reviews/{reviews['approved']}/approve", headers=hd["admin"], json={"comment": "좋습니다"}), "approve")
    ok(client.post(f"/v1/workspaces/{WORKSPACE}/reviews/{reviews['changes_requested']}/request-changes", headers=hd["admin"], json={"comment": "색을 조금 밝게"}), "request changes")
    ok(client.post(f"/v1/workspaces/{WORKSPACE}/reviews/{reviews['rejected']}/reject", headers=hd["admin"], json={"comment": "다른 제품 사진"}), "reject")

    def work(kind, title, status, keys, attrs=None, who="editor"):
        return ok(client.post(f"/v1/workspaces/{WORKSPACE}/work-items", headers=hd[who], json={"kind": kind, "title": title, "status": status, "asset_ids": [asset(k) for k in keys], "attrs": attrs or {"demo": "seed"}}), f"work {title}")

    work("tryon", "작성 중인 시착", "draft", [])
    work("tryon", "검수 요청한 시착", "req", ["render0"])
    work("tryon", "승인된 시착", "ok", ["render1"])
    work("lookbook", "변경 요청받은 룩북", "chg", ["garment0"])
    work("tryon", "반려된 시착", "rej", ["garment1"])
    work("video", "완료한 영상", "done", ["render1", "bg0"], who="editor2")

    listing = ok(client.post("/v1/market/listings", headers=hd["editor"], json={
        "workspace_id": WORKSPACE, "kind": "preset", "title": "시연용 무료 프리셋", "description": "시연 화면용 항목입니다", "tags": ["demo", "free"], "price": 0,
        "payload": {"br": 8, "shadow": True}, "license_scope": "demo only", "is_ai_generated": False, "rights_confirmed": True}), "market listing")
    ok(client.post(f"/v1/market/listings/{listing['listing_id']}/publish", headers=hd["editor"], json={"rights_confirmed": True}), "publish")
    ok(client.post(f"/v1/market/listings/{listing['listing_id']}/reports", headers=hd["viewer"], json={"reason": "other", "details": "시연용 신고"}), "report")

    work("demo", MARKER_TITLE, "done", [], who="owner")      # written LAST: its presence means the seed is complete
    print(f"seed_demo: done. Workspace '{WORKSPACE}': 5 users, {len(items)} library items, 6 work items, 4 reviews, 1 market listing + 1 report.")
    print("seed_demo: demo sign-in tokens (fake, for a local server with this database only): ASSET_API_TOKENS=" + ",".join(f"{t}:{u}" for t, u in USERS.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
