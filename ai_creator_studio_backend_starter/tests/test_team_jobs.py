"""R-TEAM-01: team jobs - create, list scopes, transition table, notes, comments, bulk (partial failure), summary, workspace isolation, append-only history."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import config, team_jobs
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
J = "/v1/workspaces/wa/jobs"


@pytest.fixture
def team(env, monkeypatch):
    base = config.asset_api_tokens()
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {**base, "token-d": "user-d", "token-e": "user-e", "token-f": "user-f"})
    for u, role in (("user-d", "editor"), ("user-e", "admin"), ("user-f", "editor")):
        assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": u, "role": role}).status_code == 201
    return env


def make(who="d", title="촬영 A", workroom="photo", **extra):
    r = client.post(J, headers=auth(who), json={"workroom": workroom, "title": title, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def move(job, to, who, note=None):
    return client.post(f"{J}/{job['job_id']}/transition", headers=auth(who), json={"to": to, **({"note": note} if note else {})})


def test_create_starts_as_draft_owned_by_the_caller_and_viewers_cannot_create(team):
    job = make()
    assert job["status"] == "draft" and job["owner_user_id"] == "user-d" and job["workroom"] == "photo"
    assert client.post(J, headers=auth("c"), json={"workroom": "photo", "title": "x"}).status_code == 403
    assert client.post(J, headers=auth("d"), json={"workroom": "photo", "title": "  "}).status_code == 422
    assert client.post(J, headers=auth("d"), json={"workroom": "ads", "title": "x"}).status_code == 422
    assert client.post(J, headers=auth("d"), json={"workroom": "photo", "title": "x", "due_at": "soon"}).json()["detail"]["code"] == "JOB_DATE_INVALID"


def test_list_scope_admins_see_all_an_editor_only_their_own_a_viewer_reads_all(team):
    mine, theirs = make("d", "내 것"), make("f", "남의 것", "video")
    ids = lambda who, q="": {i["job_id"] for i in client.get(J + q, headers=auth(who)).json()["items"]}
    assert ids("e") == ids("a") == ids("c") == {mine["job_id"], theirs["job_id"]}
    assert ids("d") == {mine["job_id"]} and ids("f") == {theirs["job_id"]}
    assert ids("e", "?workroom=video") == {theirs["job_id"]} and ids("e", "?owner=user-d") == {mine["job_id"]} and ids("e", "?q=남의") == {theirs["job_id"]}
    assert ids("e", "?status=review") == set() and ids("e", "?since=2999-01-01T00:00:00Z") == set()
    assert client.get(J + "?limit=1", headers=auth("e")).json()["total"] == 2
    assert client.get(f"{J}/{theirs['job_id']}", headers=auth("d")).status_code == 404, "an editor does not open another's job"


def test_the_transition_table_is_fixed_and_decisions_belong_to_owner_and_admin(team):
    job = make()
    assert move(job, "approved", "e").json()["detail"]["code"] == "JOB_TRANSITION_INVALID"       # draft cannot jump to approved
    assert move(job, "review", "f").status_code == 403                                           # another editor cannot send it
    assert move(job, "review", "d").json()["status"] == "review"
    assert move(job, "approved", "d").status_code == 403                                         # the owner of the job cannot approve it
    assert move(job, "approved", "c").status_code == 403
    r = move(job, "changes", "e")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "JOB_NOTE_REQUIRED"
    assert move(job, "changes", "e", "색을 바꿔 주세요").json()["status"] == "changes"
    assert move(job, "review", "d").json()["status"] == "review"
    assert move(job, "approved", "a").json()["status"] == "approved"
    for to in ("draft", "review", "rejected", "changes"):
        assert move(job, to, "a", "x").status_code == 409, "approved is final"
    rej = make(title="r")
    move(rej, "review", "d")
    assert move(rej, "rejected", "e").status_code == 422 and move(rej, "rejected", "e", "쓸 수 없음").json()["status"] == "rejected"


def test_history_and_comments_are_recorded_in_order_and_are_append_only(team):
    job = make()
    move(job, "review", "d")
    move(job, "changes", "e", "다시")
    assert client.post(f"{J}/{job['job_id']}/comments", headers=auth("e"), json={"body": " 확인했어요 "}).status_code == 201
    assert client.post(f"{J}/{job['job_id']}/comments", headers=auth("d"), json={"body": "고칠게요"}).status_code == 201
    assert client.post(f"{J}/{job['job_id']}/comments", headers=auth("f"), json={"body": "x"}).status_code == 403
    assert client.post(f"{J}/{job['job_id']}/comments", headers=auth("c"), json={"body": "x"}).status_code == 403
    assert client.post(f"{J}/{job['job_id']}/comments", headers=auth("e"), json={"body": "  "}).status_code in (422,)
    got = client.get(f"{J}/{job['job_id']}", headers=auth("d")).json()
    assert [(e["from"], e["to"], e["by"]) for e in got["events"]] == [(None, "draft", "user-d"), ("draft", "review", "user-d"), ("review", "changes", "user-e")]
    assert got["events"][2]["note"] == "다시" and [c["body"] for c in got["comments"]] == ["확인했어요", "고칠게요"]
    db = sqlite3.connect(config.ASSET_DATABASE_PATH)
    for sql in ("UPDATE team_job_events SET note='x'", "DELETE FROM team_job_events", "UPDATE team_job_comments SET body='x'", "DELETE FROM team_job_comments"):
        with pytest.raises(sqlite3.DatabaseError):
            db.execute(sql)


def test_bulk_transition_reports_each_job_and_lets_part_fail(team):
    a, b, c = make("d", "a"), make("d", "b"), make("f", "c")
    for j in (a, b, c):
        move(j, "review", j["owner_user_id"][-1])
    move(b, "approved", "e")
    r = client.post(f"{J}:bulk-transition", headers=auth("e"), json={"ids": [a["job_id"], b["job_id"], "job_nope", c["job_id"]], "to": "changes", "note": "수정 요청"})
    assert r.status_code == 200, r.text
    res = {x["id"]: x for x in r.json()["results"]}
    assert res[a["job_id"]]["ok"] and res[c["job_id"]]["ok"] and res[a["job_id"]]["status"] == "changes"
    assert res[b["job_id"]]["error_code"] == "JOB_TRANSITION_INVALID" and res["job_nope"]["error_code"] == "NOT_FOUND"
    assert (r.json()["succeeded"], r.json()["failed"]) == (2, 2)
    fresh = make("d", "fresh")
    move(fresh, "review", "d")
    assert client.post(f"{J}:bulk-transition", headers=auth("e"), json={"ids": [fresh["job_id"]], "to": "rejected"}).json()["results"][0]["error_code"] == "JOB_NOTE_REQUIRED"
    assert client.post(f"{J}:bulk-transition", headers=auth("d"), json={"ids": [c["job_id"]], "to": "review"}).json()["results"][0]["error_code"] == "FORBIDDEN"
    assert client.post(f"{J}:bulk-transition", headers=auth("c"), json={"ids": [a["job_id"]], "to": "review"}).status_code == 403
    assert client.post(f"{J}:bulk-transition", headers=auth("e"), json={"ids": [a["job_id"], a["job_id"]], "to": "review"}).status_code == 422
    assert client.post(f"{J}:bulk-transition", headers=auth("e"), json={"ids": [], "to": "review"}).status_code == 422


def test_summary_counts_per_member_status_and_jobs_due_within_a_day(team):
    soon = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    late = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    a, b = make("d", "a", due_at=soon), make("d", "b", due_at=late)
    make("f", "c")
    move(a, "review", "d")
    move(a, "approved", "e")
    s = client.get("/v1/workspaces/wa/team/summary?period=week", headers=auth("e")).json()
    members = {m["user_id"]: m for m in s["members"]}
    assert members["user-d"]["jobs"] == 2 and members["user-d"]["approved"] == 1 and members["user-f"]["jobs"] == 1 and members["user-e"]["jobs"] == 0
    assert s["by_status"] == {"draft": 2, "review": 0, "changes": 0, "approved": 1, "rejected": 0}
    assert s["due_soon_24h"] == 0, "the due job is already approved; the other is 3 days away"
    c = make("d", "d", due_at=soon)
    assert client.get("/v1/workspaces/wa/team/summary", headers=auth("a")).json()["due_soon_24h"] == 1 and c
    assert all(m["credits_used"] is None for m in s["members"]) and "credits" in s["credits_note"]
    assert client.get("/v1/workspaces/wa/team/summary", headers=auth("d")).status_code == 403
    assert client.get("/v1/workspaces/wa/team/summary?period=year", headers=auth("a")).status_code == 422


def test_other_workspaces_never_see_these_jobs_and_anonymous_is_refused(team):
    job = make()
    assert client.get(J, headers=auth("b")).status_code in (403, 404)
    assert client.get(f"/v1/workspaces/wb/jobs/{job['job_id']}", headers=auth("b")).status_code == 404
    assert client.post(f"/v1/workspaces/wb/jobs/{job['job_id']}/transition", headers=auth("b"), json={"to": "review"}).status_code == 404
    assert client.get(J).status_code in (401, 403)
    assert team_jobs.TRANSITIONS["approved"] == set() and team_jobs.TRANSITIONS["rejected"] == set()


def test_the_list_and_the_job_carry_the_comment_count_for_the_board(team):
    job = make()
    for who in ("d", "e"):
        assert client.post(f"{J}/{job['job_id']}/comments", headers=auth(who), json={"body": "의견"}).status_code == 201
    listed = {i["job_id"]: i for i in client.get(J, headers=auth("e")).json()["items"]}
    assert listed[job["job_id"]]["comment_count"] == 2
    assert client.get(f"{J}/{job['job_id']}", headers=auth("e")).json()["comment_count"] == 2
    assert make(title="no comments")["comment_count"] == 0
