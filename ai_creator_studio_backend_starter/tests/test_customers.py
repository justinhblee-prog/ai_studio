"""R-057 (reply 37): customer / contract / acquisition statistics. Collection is OFF by default; values are reduced to non-identifying forms;
aggregation is computed from the stored records and agrees with the company list; coverage names what is measured and what is not."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_ops_overview import auth, client, env, job  # noqa: F401  (co-paid: owner a + editor c; co-two: owner b; operator = user-o)

ACQ = {"source": "google", "medium": "cpc", "campaign": "spring-2026", "referrer_host": "google.com", "landing": "/pricing", "first_seen": "2026-11-01T09:30:00Z"}
SURVEY = {"found": "friend", "industry": "fashion", "size": "6-20"}


@pytest.fixture(autouse=True)
def collection_on(monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "CUSTOMER_STATS_COLLECTION", True)


def record(ws="co-paid", who="a", **body):
    return client.post(f"/v1/workspaces/{ws}/acquisition", headers=auth(who), json=body)


def companies(**params):
    return client.get("/internal/ops/customers/companies", headers=auth("o"), params=params)


def stats(**params):
    return client.get("/internal/ops/customers", headers=auth("o"), params=params)


def contract(ws, **body):
    return client.put(f"/internal/ops/customers/{ws}/contract", headers=auth("o"), json=body)


def db():
    import app.config as config
    return sqlite3.connect(config.ASSET_DATABASE_PATH)


def row_of(ws="co-paid"):
    return next(c for c in companies().json() if c["company"] == ws)


def test_collection_is_off_by_default_and_nothing_is_stored_then(env, monkeypatch):
    import subprocess
    import sys
    from pathlib import Path
    clean = {k: v for k, v in __import__("os").environ.items() if k != "CUSTOMER_STATS_COLLECTION"}
    out = subprocess.run([sys.executable, "-c", "import app.config as c; print(c.CUSTOMER_STATS_COLLECTION)"], cwd=Path(__file__).resolve().parents[1], env=clean,
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "False", "the real default is off"
    import app.config as config
    monkeypatch.setattr(config, "CUSTOMER_STATS_COLLECTION", False)
    r = record(acq=ACQ, survey=SURVEY)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "COLLECTION_DISABLED"
    assert row_of()["acq"] is None and row_of()["survey"] is None
    assert stats().json()["collection_enabled"] is False


def test_the_owner_records_acq_and_survey_and_the_operator_sees_them(env):
    r = record(acq=ACQ, survey=SURVEY)
    assert r.status_code == 200, r.text
    assert r.json()["acq"] == ACQ and r.json()["survey"] == SURVEY
    row = row_of()
    assert row["acq"] == ACQ and row["survey"] == SURVEY and row["users"] == 2
    assert row["contract"]["status"] == "trial" and row["joined_at"] and row["churned_at"] is None


def test_first_acq_wins_the_survey_can_change_and_everything_is_in_the_history(env):
    record(acq=ACQ, survey=SURVEY)
    again = record(acq={"source": "other"}, survey={"found": "event", "industry": "retail", "size": "50+"})
    assert again.json()["acq"] == ACQ, "the first touch stays"
    assert again.json()["survey"] == {"found": "event", "industry": "retail", "size": "50+"}
    history = client.get("/internal/ops/customers/co-paid/history", headers=auth("o")).json()
    assert [(h["field"], h["actor_id"]) for h in history] == [("acq", "user-a"), ("survey", "user-a"), ("survey", "user-a")]
    assert history[0]["old_value"] is None and history[2]["old_value"] == SURVEY
    record(survey={"found": "event", "industry": "retail", "size": "50+"})
    assert len(client.get("/internal/ops/customers/co-paid/history", headers=auth("o")).json()) == 3, "an unchanged survey adds no history"


def test_values_are_reduced_to_plain_non_identifying_forms(env):
    r = record(acq={"source": "news", "referrer_host": "https://News.Example.com:8443/a/b?token=secret#x", "landing": "/pricing?email=a@b.com#frag", "campaign": "a b+c-1"})
    assert r.status_code == 200, r.text
    assert r.json()["acq"] == {"source": "news", "campaign": "a b+c-1", "referrer_host": "news.example.com", "landing": "/pricing"}
    assert "@" not in json.dumps(r.json()) and "token" not in json.dumps(r.json())


@pytest.mark.parametrize("body", [
    {"acq": {"referrer_host": "1.2.3.4"}}, {"acq": {"referrer_host": "user@evil.com"}}, {"acq": {"source": "a@b.com"}}, {"acq": {"campaign": "x=1&y=2"}},
    {"acq": {"landing": "https://evil.example/x"}}, {"acq": {"landing": "pricing"}}, {"acq": {"first_seen": "yesterday"}}, {"acq": {"ip": "203.0.113.9"}},
    {"acq": {"ip_address": "203.0.113.9"}}, {"acq": {"url": "https://a.example/x?y=1"}}, {"survey": {"found": "a@b.com"}}, {"survey": {"size": "many people"}},
    {"survey": {"email": "a@b.com"}}, {"extra": 1},
])
def test_identifying_or_malformed_values_are_refused_and_nothing_is_stored(env, body):
    assert record(**body).status_code == 422
    assert row_of()["acq"] is None and row_of()["survey"] is None


def test_roles_and_scopes(env):
    assert record(who="c", acq=ACQ).status_code == 403, "an editor is not the owner"
    assert record(ws="co-paid", who="b", acq=ACQ).status_code in (403, 404)
    assert client.post("/v1/workspaces/co-paid/acquisition", json={"acq": ACQ}).status_code == 401
    assert record(ws="no-such-company", who="a", acq=ACQ).status_code in (403, 404)
    for who in "abc":
        for method, path, kw in (("get", "/internal/ops/customers", {}), ("get", "/internal/ops/customers/companies", {}), ("get", "/internal/ops/customers/retention", {}),
                                 ("get", "/internal/ops/customers/co-paid/contract", {}), ("get", "/internal/ops/customers/co-paid/history", {}),
                                 ("put", "/internal/ops/customers/co-paid/contract", {"json": {"plan": "x"}})):
            assert getattr(client, method)(path, headers=auth(who), **kw).status_code == 403, path
    assert client.get("/internal/ops/customers").status_code == 401


def test_first_job_last_activity_and_the_joining_window(env):
    job("co-paid", "a", 1); job("co-paid", "c", 2)
    row = row_of()
    assert row["first_job_at"] and row["last_active_at"] and row["first_job_at"] <= row["last_active_at"]
    assert row_of("co-two")["first_job_at"] is None
    assert companies(**{"from": "2000-01-01", "to": "2000-02-01"}).json() == []
    assert {c["company"] for c in companies(**{"from": "2000-01-01"}).json()} == {"co-paid", "co-two"}
    for bad in ({"from": "soon"}, {"to": "later"}):
        assert companies(**bad).status_code == 422 and stats(**bad).status_code == 422


def test_contract_roundtrip_churn_statuses_and_history(env):
    assert client.get("/internal/ops/customers/co-paid/contract", headers=auth("o")).json()["contract"] == {"start": None, "end": None, "status": "trial", "plan": None}
    r = contract("co-paid", plan="pilot", start="2026-11-01", end="2027-10-31", status="active")
    assert r.status_code == 200, r.text
    assert r.json()["contract"] == {"start": "2026-11-01", "end": "2027-10-31", "status": "active", "plan": "pilot"} and r.json()["churned_at"] is None
    cancelled = contract("co-paid", status="cancelled", churn_reason="budget")
    assert cancelled.json()["contract"]["status"] == "cancelled" and cancelled.json()["churned_at"] and cancelled.json()["churn_reason"] == "budget"
    first = cancelled.json()["churned_at"]
    ended = contract("co-paid", status="ended", churn_reason="budget cut")
    assert ended.json()["churned_at"] == first, "the leaving time is not moved by a later edit"
    back = contract("co-paid", status="active", clear_end=True)
    assert back.json()["churned_at"] is None and back.json()["churn_reason"] is None and back.json()["contract"]["end"] is None
    history = client.get("/internal/ops/customers/co-paid/history", headers=auth("o")).json()
    assert {h["actor_id"] for h in history} == {"user-o"} and {"plan", "contract_status", "churned_at", "churn_reason", "contract_end"} <= {h["field"] for h in history}
    assert row_of()["contract"]["plan"] == "pilot"


@pytest.mark.parametrize("body", [{"start": "11/01/2026"}, {"end": "2026-13-45x"}, {"plan": "a@b.com"}, {"status": "expiring"}, {"churn_reason": "x=1"}, {"nonsense": 1}, {"amount": 5}])
def test_bad_contract_input_is_refused(env, body):
    assert contract("co-paid", **body).status_code == 422
    assert contract("no-such-company", plan="x").status_code == 404


def test_the_history_cannot_be_changed_or_deleted(env):
    record(acq=ACQ)
    with db() as c:
        for sql in ("UPDATE company_profile_history SET actor_id='x'", "DELETE FROM company_profile_history"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                c.execute(sql)


def seed_months(env):
    """4 companies: co-paid (older, converted), co-two (last month, cancelled this month), co-third and co-fourth (this month)."""
    for ws, who in (("co-third", "a"), ("co-fourth", "b")):
        assert client.post("/v1/workspaces", headers=auth(who), json={"workspace_id": ws}).status_code == 201
    now = datetime.now(timezone.utc)
    this_m, last_m = now.strftime("%Y-%m"), (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    older = (now.replace(day=1) - timedelta(days=70)).strftime("%Y-%m")
    record("co-paid", "a", acq={"source": "google", "campaign": "spring"}, survey={"industry": "fashion", "size": "6-20"})
    record("co-two", "b", acq={"source": "friend"}, survey={"industry": "retail"})
    record("co-third", "a", acq={"source": "google", "campaign": "spring"})
    contract("co-paid", status="active", plan="pilot")
    contract("co-two", status="cancelled", churn_reason="moved")
    with db() as c:
        for ws, month in (("co-paid", older), ("co-two", last_m), ("co-third", this_m), ("co-fourth", this_m)):
            c.execute("UPDATE company_profiles SET joined_at=? WHERE workspace_id=?", (month + "-10T12:00:00+00:00", ws))
        c.execute("UPDATE company_profiles SET churned_at=? WHERE workspace_id='co-two'", (this_m + "-05T12:00:00+00:00",))
    return older, last_m, this_m


def test_aggregation_by_channel_agrees_with_the_company_list(env):
    older, last_m, this_m = seed_months(env)
    body = stats(by="channel").json()
    rows = {(r["bucket"], r["key"]): r for r in body["rows"]}
    assert rows[(older, "google")] == {"bucket": older, "key": "google", "signups": 1, "churned": 0, "active_end": 1, "trials": 1, "converted": 1}
    assert rows[(last_m, "friend")]["signups"] == 1 and rows[(last_m, "friend")]["converted"] == 0 and rows[(last_m, "friend")]["active_end"] == 1
    assert rows[(this_m, "friend")]["churned"] == 1 and rows[(this_m, "friend")]["active_end"] == 0
    assert rows[(this_m, "google")]["signups"] == 1 and rows[(this_m, "google")]["active_end"] == 2
    assert rows[(this_m, "unknown")]["signups"] == 1
    totals = body["totals"]
    assert totals["signups"] == len(companies().json()) == 4, "signups over all buckets add up to the company list"
    assert totals["churned"] == sum(1 for c in companies().json() if c["churned_at"]) == 1
    assert totals["active_end"] == 3 and totals["trials"] == 4 and totals["converted"] == 1
    assert body["group_by"] == "month" and body["by"] == "channel" and body["to"] == this_m
    # every month in the range appears or has no rows at all; the sums over any grouping agree
    for by in ("industry", "size", "plan"):
        assert stats(by=by).json()["totals"] == totals, by
    assert {r["key"] for r in stats(by="plan").json()["rows"]} == {"pilot", "(none)"}
    assert {r["key"] for r in stats(by="industry").json()["rows"]} == {"fashion", "retail", "unknown"}


def test_year_grouping_range_and_coverage(env):
    seed_months(env)
    y = stats(group_by="year").json()
    assert y["group_by"] == "year" and y["to"] == str(datetime.now(timezone.utc).year) and y["totals"]["signups"] == 4
    ranged = stats(**{"from": "2000-01", "to": "2000-06"}).json()
    assert ranged["rows"] == [] and ranged["totals"]["signups"] == 0
    assert stats(**{"from": "1900-01", "to": "2026-12"}).status_code == 422, "too many buckets"
    assert stats(by="nonsense").status_code == 422 and stats(group_by="week").status_code == 422
    cov = y["coverage"]
    assert {"signups", "churned", "active_end", "trials", "converted", "by=channel", "by=industry|size"} <= set(cov)
    assert all({"source", "measured", "estimated", "not_measured"} <= set(v) for v in cov.values())
    assert any("operator" in s for s in cov["churned"]["not_measured"]), "inactivity is not churn: said openly"
    assert any("no revenue" in n for n in y["notes"])


def test_the_responses_hold_no_personal_data(env):
    job("co-paid", "a", 1)
    record(acq=ACQ, survey=SURVEY)
    contract("co-paid", plan="pilot", status="active")
    text = " ".join(json.dumps(r.json()) for r in (companies(), stats(), stats(by="industry"), client.get("/internal/ops/customers/retention", headers=auth("o")),
                                                  client.get("/internal/ops/customers/co-paid/contract", headers=auth("o")),
                                                  client.get("/internal/ops/customers/co-paid/history", headers=auth("o"))))
    for needle in ("@", "prompt", "photo", "password", "token", "email", "ip_address"):
        assert needle not in text, needle


def test_retention_cohorts_count_those_not_churned_n_months_after_joining(env):
    older, last_m, this_m = seed_months(env)
    body = client.get("/internal/ops/customers/retention", headers=auth("o")).json()
    cohorts = {c["cohort"]: c for c in body["cohorts"]}
    assert cohorts[this_m]["size"] == 2 and [x["month"] for x in cohorts[this_m]["retention"]] == [0]
    assert cohorts[this_m]["retention"][0]["retained"] == 2
    last = cohorts[last_m]["retention"]
    assert [x["month"] for x in last] == [0, 1] and last[0]["retained"] == 1 and last[1]["retained"] == 0 and last[1]["rate"] == 0.0, "cancelled one month after joining"
    old = cohorts[older]["retention"]
    age = (int(this_m[:4]) - int(older[:4])) * 12 + int(this_m[5:7]) - int(older[5:7])
    assert len(old) == age + 1 and all(x["retained"] == 1 and x["rate"] == 1.0 for x in old)
    assert "retention" in body["coverage"] and any("inactiv" in s for s in body["coverage"]["retention"]["not_measured"])
