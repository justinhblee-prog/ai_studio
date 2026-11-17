"""B-08: simultaneous workspace exports. The daily allowance is a limit, not a hint: with room for N, a burst of many requests gets exactly N exports and the rest 429
(never more), every export that was made is a complete, checksum-valid ZIP, and download / delete racing each other end cleanly (no 5xx, no half files left)."""
import hashlib
from concurrent.futures import ThreadPoolExecutor

from app import config
from tests.test_data_export import auth, client, make_export, team, zip_of  # noqa: F401
from tests.test_photo_steps_api import env  # noqa: F401


def test_a_burst_never_exceeds_the_daily_allowance(team, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DAILY_LIMIT_PER_WORKSPACE", 2)
    with ThreadPoolExecutor(8) as pool:
        codes = sorted(r.status_code for r in pool.map(lambda _: make_export(), range(8)))
    assert codes == [201, 201] + [429] * 6, codes
    listed = client.get("/v1/workspaces/wa/exports", headers=auth("a")).json()
    assert len([e for e in listed if e["status"] == "ready"]) == 2


def test_exports_made_at_the_same_time_are_all_complete_and_distinct(team, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DAILY_LIMIT_PER_WORKSPACE", 6)
    with ThreadPoolExecutor(4) as pool:
        made = list(pool.map(lambda _: make_export(), range(4)))
    assert all(r.status_code == 201 for r in made), [r.status_code for r in made]
    ids = [r.json()["export_id"] for r in made]
    assert len(set(ids)) == 4
    for export_id in ids:
        got = client.get(f"/v1/exports/{export_id}/download", headers=auth("a"))
        assert got.status_code == 200
        z = zip_of(got)
        assert z.testzip() is None and "manifest.json" in z.namelist()
    leftovers = list((config.ASSET_STORAGE_DIR / "exports").glob("*.partial")) if (config.ASSET_STORAGE_DIR / "exports").exists() else []
    assert leftovers == [], "no half-written file may remain"


def test_download_and_delete_racing_end_cleanly(team, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_DAILY_LIMIT_PER_WORKSPACE", 6)
    export_id = make_export().json()["export_id"]

    def act(i):
        if i % 2:
            return client.delete(f"/v1/exports/{export_id}", headers=auth("a")).status_code
        return client.get(f"/v1/exports/{export_id}/download", headers=auth("a")).status_code
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(act, range(8)))
    assert all(c < 500 for c in codes), codes
    assert set(codes) <= {200, 204, 404, 409, 410}, codes
    after = client.get(f"/v1/exports/{export_id}/download", headers=auth("a"))
    assert after.status_code in (404, 410), "once deleted it stays gone"
