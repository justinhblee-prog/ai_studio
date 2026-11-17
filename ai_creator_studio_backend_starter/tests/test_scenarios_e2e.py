"""B-12: whole stories through the real API (no browser), each step depending on the one before.
1. Team review story: an editor uploads, asks for a review, the viewer cannot decide, the admin approves, the status says "exportable", the admin exports the workspace,
   the ZIP holds the picture and the manifest, only members may download it, and the history lists the steps in order.
2. Market story: a seller makes a listing, it is invisible until published, a stranger finds it, reports it (always the same answer), and an operator reads the report."""
import io
import zipfile

from app import config
from tests.test_asset_reviews import act, ask, asset, client, team as review_team  # noqa: F401
from tests.test_market import BODY, auth, made, publish, search, team as market_team  # noqa: F401
from tests.test_photo_steps_api import env  # noqa: F401


def test_upload_review_approve_export_and_audit_story(review_team):
    # 1) the editor uploads and asks for a review
    asset_id = asset("d", (11, 22, 33))
    review = ask(asset_id, "d", "봄 룩북 최종본")
    assert review.status_code == 201
    rid = review.json()["review_id"]
    status = client.get("/v1/workspaces/wa/reviews/status", headers=auth("c"), params={"asset_ids": [asset_id]}).json()["items"][0]
    assert status["status"] == "requested" and status["exportable"] is False
    # 2) the viewer can read but not decide; the admin approves
    assert act(rid, "approve", "c").status_code == 403
    assert act(rid, "approve", "e").status_code == 200
    status = client.get("/v1/workspaces/wa/reviews/status", headers=auth("c"), params={"asset_ids": [asset_id]}).json()["items"][0]
    assert status["status"] == "approved" and status["exportable"] is True
    # 3) only owner/admin export; the ZIP holds the picture and the manifest
    assert client.post("/v1/workspaces/wa/exports", headers=auth("c")).status_code == 403
    exp = client.post("/v1/workspaces/wa/exports", headers=auth("e"))
    assert exp.status_code == 201
    export_id = exp.json()["export_id"]
    got = client.get(f"/v1/exports/{export_id}/download", headers=auth("e"))
    assert got.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(got.content))
    assert z.testzip() is None and "manifest.json" in z.namelist()
    entry = next(n for n in z.namelist() if n.startswith(f"assets/{asset_id}"))
    assert z.read(entry)[:8] == b"\x89PNG\r\n\x1a\n"
    # 4) a stranger cannot fetch it
    assert client.get(f"/v1/exports/{export_id}/download", headers=auth("b")).status_code in (403, 404)
    # 5) the history lists request then approval, with who did it
    events = client.get(f"/v1/workspaces/wa/reviews/{rid}/events", headers=auth("c")).json()
    assert [(e["action"], e["actor_id"]) for e in events] == [("request", "user-d"), ("approve", "user-e")]


def test_market_listing_search_report_and_operator_story(market_team, monkeypatch):
    item = made("a")
    lid = item["listing_id"]
    assert all(x["listing_id"] != lid for x in search("b")["items"]), "a private listing is not found"
    assert publish(lid).status_code == 200
    assert any(x["listing_id"] == lid for x in search("b")["items"]), "published: a stranger finds it"
    report = client.post(f"/v1/market/listings/{lid}/reports", headers=auth("b"), json={"reason": "copyright", "details": "looks copied"})
    assert report.status_code == 202 and report.json() == {"status": "received"}
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-o": "user-o"})
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", ("user-o",))
    rows = client.get("/internal/market/reports", headers=auth("o")).json()["items"]
    assert [r["listing_id"] for r in rows] == [lid] and rows[0]["reason"] == "copyright"
    assert client.get("/internal/market/reports", headers=auth("b")).status_code == 403
