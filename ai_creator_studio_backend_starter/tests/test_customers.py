"""R-057: customer / marketing statistics data: acquisition (first write wins, plain values only), survey, contract, churn, history, aggregation."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_ops_overview import auth, client, env, job  # noqa: F401  (co-paid: owner a + editor c; co-two: owner b; operator = user-o)

ACQ = {"channel": "search", "referrer_host": "google.com", "utm_source": "google", "utm_medium": "cpc", "utm_campaign": "spring-2026", "landing_page": "/pricing",
       "first_visit_at": "2026-11-01T09:30:00Z"}
SURVEY = {"found": "friend", "industry": "fashion", "team_size": "6-20"}


def record(ws="co-paid", who="a", **body):
    return client.post(f"/v1/workspaces/{ws}/acquisition", headers=auth(who), json=body)


def customers(**params):
    return client.get("/internal/ops/customers", headers=auth("o"), params=params)


def contract(ws, **body):
    return client.put(f"/internal/ops/customers/{ws}/contract", headers=auth("o"), json=body)


def db(env_):
    import app.config as config
    return sqlite3.connect(config.ASSET_DATABASE_PATH)


def test_the_owner_records_acquisition_and_survey_and_the_operator_sees_them(env):
    r = record(acquisition=ACQ, survey=SURVEY)
    assert r.status_code == 200, r.text
    assert r.json()["acquisition"] == ACQ and r.json()["survey"] == SURVEY
    row = next(c for c in customers().json() if c["company"] == "co-paid")
    assert row["acquisition"] == ACQ and row["survey"] == SURVEY and row["email_domain"] is None
    assert row["users"] == 2 and row["contract_status"] == "trial" and row["joined_at"] and row["churned_at"] is None


def test_first_acquisition_wins_but_the_survey_can_be_updated_and_everything_is_in_the_history(env):
    record(acquisition=ACQ, survey=SURVEY)
    again = record(acquisition={"channel": "ads", "utm_campaign": "other"}, survey={"found": "event", "industry": "retail", "team_size": "50+"})
    assert again.json()["acquisition"] == ACQ, "the first touch stays"
    assert again.json()["survey"] == {"found": "event", "industry": "retail", "team_size": "50+"}
    history = client.get("/internal/ops/customers/co-paid/history", headers=auth("o")).json()
    assert [(h["field"], h["actor_id"]) for h in history] == [("acquisition", "user-a"), ("survey", "user-a"), ("survey", "user-a")]
    assert history[0]["old_value"] is None and history[2]["old_value"] == SURVEY and history[2]["new_value"]["found"] == "event"
    again2 = record(survey={"found": "event", "industry": "retail", "team_size": "50+"})
    assert again2.status_code == 200 and len(client.get("/internal/ops/customers/co-paid/history", headers=auth("o")).json()) == 3, "an unchanged survey adds no history"


def test_values_are_reduced_to_plain_non_identifying_forms(env):
    r = record(acquisition={"channel": "referral", "referrer_host": "https://News.Example.com:8443/a/b?token=secret#x", "landing_page": "/pricing?email=a@b.com#frag", "utm_campaign": "a b+c-1"})
    assert r.status_code == 200, r.text
    assert r.json()["acquisition"] == {"channel": "referral", "referrer_host": "news.example.com", "landing_page": "/pricing", "utm_campaign": "a b+c-1"}
    assert "@" not in json.dumps(r.json()) and "token" not in json.dumps(r.json())


@pytest.mark.parametrize("body", [
    {"acquisition": {"channel": "tv"}}, {"acquisition": {"referrer_host": "1.2.3.4"}}, {"acquisition": {"referrer_host": "user@evil.com"}},
    {"acquisition": {"utm_source": "a@b.com"}}, {"acquisition": {"utm_campaign": "x=1&y=2"}}, {"acquisition": {"landing_page": "https://evil.example/x"}},
    {"acquisition": {"landing_page": "pricing"}}, {"acquisition": {"first_visit_at": "yesterday"}}, {"acquisition": {"ip": "203.0.113.9"}},
    {"acquisition": {"ip_address": "203.0.113.9"}}, {"survey": {"found": "a@b.com"}}, {"survey": {"team_size": "many people"}}, {"survey": {"email": "a@b.com"}}, {"extra": 1},
])
def test_identifying_or_malformed_values_are_refused_and_nothing_is_stored(env, body):
    assert record(**body).status_code == 422
    row = next(c for c in customers().json() if c["company"] == "co-paid")
    assert row["acquisition"] is None and row["survey"] is None


def test_roles_and_scopes(env):
    assert record(who="c", acquisition=ACQ).status_code == 403, "an editor is not the owner"
    assert record(ws="co-paid", who="b", acquisition=ACQ).status_code in (403, 404)
    assert client.post("/v1/workspaces/co-paid/acquisition", json={"acquisition": ACQ}).status_code == 401
    assert record(ws="no-such-company", who="a", acquisition=ACQ).status_code in (403, 404)
    for who in "abc":
        assert client.get("/internal/ops/customers", headers=auth(who)).status_code == 403
        assert client.get("/internal/ops/marketing", headers=auth(who)).status_code == 403
        assert client.put("/internal/ops/customers/co-paid/contract", headers=auth(who), json={"plan": "x"}).status_code == 403
        assert client.get("/internal/ops/customers/co-paid/history", headers=auth(who)).status_code == 403
    assert client.get("/internal/ops/customers").status_code == 401


def test_first_job_last_activity_and_the_joining_window_come_from_our_own_records(env):
    job("co-paid", "a", 1); job("co-paid", "c", 2)
    row = next(c for c in customers().json() if c["company"] == "co-paid")
    assert row["first_job_at"] and row["last_active_at"] and row["first_job_at"] <= row["last_active_at"]
    assert next(c for c in customers().json() if c["company"] == "co-two")["first_job_at"] is None
    assert {c["company"] for c in customers(**{"from": "2000-01-01", "to": "2000-02-01"}).json()} == set()
    assert {c["company"] for c in customers(**{"from": "2000-01-01"}).json()} == {"co-paid", "co-two"}
    for bad in ({"from": "soon"}, {"to": "later"}):
        assert customers(**bad).status_code == 422


def test_contract_changes_are_recorded_and_ending_sets_churned_at(env):
    r = contract("co-paid", plan="pilot", contract_start="2026-11-01", contract_end="2027-10-31", contract_status="active")
    assert r.status_code == 200, r.text
    assert (r.json()["plan"], r.json()["contract_start"], r.json()["contract_status"], r.json()["churned_at"]) == ("pilot", "2026-11-01", "active", None)
    soon = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()
    assert contract("co-paid", contract_end=soon).json()["contract_status"] == "expiring", "active with an end date within 30 days"
    past = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
    assert contract("co-paid", contract_end=past).json()["contract_status"] == "ended", "the end date has passed"
    assert contract("co-paid", clear_contract_end=True).json()["contract_status"] == "active"
    ended = contract("co-paid", contract_status="ended", churn_reason="budget")
    assert ended.json()["contract_status"] == "ended" and ended.json()["churned_at"] and ended.json()["churn_reason"] == "budget"
    first_churn = ended.json()["churned_at"]
    assert contract("co-paid", churn_reason="budget cut").json()["churned_at"] == first_churn, "the leaving time is not moved"
    back = contract("co-paid", contract_status="active")
    assert back.json()["churned_at"] is None and back.json()["churn_reason"] is None and back.json()["contract_status"] == "active"
    history = client.get("/internal/ops/customers/co-paid/history", headers=auth("o")).json()
    assert {h["actor_id"] for h in history} == {"user-o"} and {"plan", "contract_status", "churned_at", "churn_reason", "contract_end"} <= {h["field"] for h in history}


@pytest.mark.parametrize("body", [{"contract_start": "11/01/2026"}, {"contract_end": "2026-13-45x"}, {"plan": "a@b.com"}, {"contract_status": "expiring"}, {"churn_reason": "x=1"}, {"nonsense": 1}])
def test_bad_contract_input_is_refused(env, body):
    assert contract("co-paid", **body).status_code == 422
    assert contract("no-such-company", plan="x").status_code == 404


def test_the_history_cannot_be_changed_or_deleted(env):
    record(acquisition=ACQ)
    with db(env) as c:
        for sql in ("UPDATE company_profile_history SET actor_id='x'", "DELETE FROM company_profile_history"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                c.execute(sql)


def test_marketing_series_channels_campaigns_and_distributions_agree_with_the_customer_list(env):
    # three companies joined in different months, one of them ended; channels and surveys differ
    for ws, who in (("co-third", "a"), ("co-fourth", "b")):
        assert client.post("/v1/workspaces", headers=auth(who), json={"workspace_id": ws}).status_code == 201
    now = datetime.now(timezone.utc)
    this_m, last_m = now.strftime("%Y-%m"), (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    older = (now.replace(day=1) - timedelta(days=70)).strftime("%Y-%m")
    record("co-paid", "a", acquisition={"channel": "search", "utm_campaign": "spring"}, survey={"industry": "fashion", "team_size": "6-20"})
    record("co-two", "b", acquisition={"channel": "referral"}, survey={"industry": "retail"})
    record("co-third", "a", acquisition={"channel": "search", "utm_campaign": "spring"})
    job("co-paid", "a", 1)
    contract("co-two", contract_status="ended", churn_reason="moved")
    with db(env) as c:
        for ws, month in (("co-paid", older), ("co-two", last_m), ("co-third", this_m), ("co-fourth", this_m)):
            c.execute("UPDATE company_profiles SET joined_at=? WHERE workspace_id=?", (month + "-10T12:00:00+00:00", ws))
        c.execute("UPDATE company_profiles SET churned_at=? WHERE workspace_id='co-two'", (this_m + "-05T12:00:00+00:00",))
    body = client.get("/internal/ops/marketing", headers=auth("o"), params={"period": "m"}).json()
    series = {s["bucket"]: s for s in body["series"]}
    assert len(body["series"]) == 12 and body["series"][-1]["bucket"] == this_m
    assert (series[older]["new"], series[last_m]["new"], series[this_m]["new"], series[this_m]["ended"], series[this_m]["net"]) == (1, 1, 2, 1, 1)
    assert (series[older]["active"], series[last_m]["active"], series[this_m]["active"]) == (1, 2, 3), "active = joined and not yet ended at the end of that month"
    assert sum(s["new"] for s in body["series"]) == len(customers().json()) == body["totals"]["companies"] == 4, "the monthly new figures add up to the customer list"
    assert sum(s["ended"] for s in body["series"]) == body["totals"]["ended"] == 1
    channels = {c["key"]: c for c in body["by_channel"]}
    assert channels["search"] == {"key": "search", "signups": 2, "first_job": 1, "retained": 2}
    assert channels["referral"]["signups"] == 1 and channels["referral"]["retained"] == 0 and channels["unknown"]["signups"] == 1
    assert {c["key"]: c["signups"] for c in body["by_campaign"]} == {"spring": 2, "(none)": 2}
    assert {d["key"]: d["count"] for d in body["industry"]} == {"fashion": 1, "retail": 1, "unknown": 2}
    assert {d["key"]: d["count"] for d in body["team_size"]} == {"6-20": 1, "unknown": 3}
    year = client.get("/internal/ops/marketing", headers=auth("o"), params={"period": "y"}).json()
    assert len(year["series"]) == 5 and year["series"][-1]["bucket"] == str(now.year)
    assert client.get("/internal/ops/marketing", headers=auth("o"), params={"period": "w"}).status_code == 422
    assert any("revenue" in n for n in body["notes"])
