"""B-08: marketplace reports sent at the same time. The daily limit holds (never more reports than allowed), the same person reporting the same listing many times at once
leaves exactly one open report, and every answer is the same 202 / 429 (never a 5xx)."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from app import config
from tests.test_market import auth, client, made, publish, team  # noqa: F401
from tests.test_photo_steps_api import env  # noqa: F401

BODY = {"reason": "copyright", "details": "x"}


def reports_in_db():
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        return c.execute("SELECT listing_id, reporter_id, status FROM market_reports").fetchall()


def test_a_burst_of_reports_on_different_listings_never_passes_the_daily_limit(team, monkeypatch):
    monkeypatch.setattr(config, "MARKET_REPORT_DAILY_LIMIT", 2)
    ids = []
    for n in range(6):
        item = made(title=f"item {n}")
        publish(item["listing_id"])
        ids.append(item["listing_id"])
    with ThreadPoolExecutor(6) as pool:
        got = list(pool.map(lambda lid: client.post(f"/v1/market/listings/{lid}/reports", headers=auth("b"), json=BODY).status_code, ids))
    assert all(c in (202, 429) for c in got), got
    assert got.count(202) == 2 and got.count(429) == 4, got
    assert len(reports_in_db()) == 2


def test_the_same_report_sent_many_times_at_once_leaves_one_open_report(team):
    item = made()
    publish(item["listing_id"])
    with ThreadPoolExecutor(8) as pool:
        got = list(pool.map(lambda _: client.post(f"/v1/market/listings/{item['listing_id']}/reports", headers=auth("b"), json=BODY), range(8)))
    assert all(r.status_code == 202 and r.json() == {"status": "received"} for r in got), [r.status_code for r in got]
    assert reports_in_db() == [(item["listing_id"], "user-b", "open")]
