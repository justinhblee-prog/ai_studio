"""B-08: duplicate and racing requests on reviews. The database refuses a second OPEN review of one asset (not only the check before the insert),
two simultaneous decisions on one review end with exactly one winner, and a new review is possible again once the first is final."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import config
from tests.test_asset_reviews import act, ask, asset, client, get, team  # noqa: F401
from tests.test_photo_steps_api import env  # noqa: F401


def test_the_database_refuses_a_second_open_review_even_without_the_check(team):
    a = asset("a", (3, 3, 3))
    assert ask(a, "d").status_code == 201
    con = sqlite3.connect(config.ASSET_DATABASE_PATH)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO asset_reviews(review_id, workspace_id, asset_id, status, requested_by, requested_at, updated_at) VALUES ('rev_dup','wa',?,'requested','user-d','t','t')", (a,))
    finally:
        con.close()


def test_a_second_request_while_open_is_409_and_a_new_one_is_fine_after_a_final_decision(team):
    a = asset("a", (4, 4, 4))
    first = ask(a, "d").json()
    again = ask(a, "d")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "REVIEW_ALREADY_OPEN"
    assert act(first["review_id"], "approve", "e").status_code == 200
    assert ask(a, "d").status_code == 201, "an approved review is final: a new one may be opened"


def test_a_changes_requested_review_still_blocks_a_new_request_and_can_be_resubmitted(team):
    a = asset("a", (5, 5, 5))
    rid = ask(a, "d").json()["review_id"]
    assert act(rid, "request-changes", "e", "fix the hem").status_code == 200
    assert ask(a, "d").status_code == 409
    assert act(rid, "resubmit", "d").status_code == 200, "both open states share the one-open rule, resubmitting must not trip it"


def test_many_simultaneous_requests_for_one_asset_open_exactly_one_review(team):
    a = asset("a", (6, 6, 6))
    with ThreadPoolExecutor(8) as pool:
        codes = sorted(r.status_code for r in pool.map(lambda _: ask(a, "d"), range(8)))
    assert codes == [201] + [409] * 7, codes


def test_two_simultaneous_decisions_on_one_review_have_exactly_one_winner(team):
    rid = ask(asset("a", (7, 7, 7)), "d").json()["review_id"]
    with ThreadPoolExecutor(2) as pool:
        got = list(pool.map(lambda action: act(rid, action, "e", "because"), ["approve", "reject"]))
    assert sorted(r.status_code for r in got) == [200, 409], [r.status_code for r in got]
    assert get(rid, "a").json()["status"] in ("approved", "rejected")
