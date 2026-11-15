import threading
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.job import SQLiteJobRepository

client = TestClient(app)


class PaidStub:
    """Stands in for a paid provider; never touches the network."""
    name = "fashn"
    model = "stub"
    calls = 0

    async def start(self, payload):
        PaidStub.calls += 1
        return {"request_id": "req-stub"}


def auth(token="token-cap-a"):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cap_env(tmp_path, monkeypatch):
    import app.config as config
    import app.main as main
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "assets.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", tmp_path / "generation.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "c" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-cap-a": "cap-a"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(config, "PROVIDER_ROUTING_MODE", "MANUAL")
    for name in ("AI_JOBS_DISABLED", "AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "AI_JOB_LIMIT_GLOBAL_MONTH", "AI_JOB_STOP_PERCENT", "AI_PROVIDER_DAILY_LIMIT", "AI_PROVIDER_DAILY_LIMIT_FASHN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("AI_COST_LIMIT_USD_MONTH", raising=False)
    monkeypatch.setenv("AI_COST_LIMIT_USD_MONTH", "100000")  # money cap far away so the older tests keep testing the job-count caps
    monkeypatch.setenv("AI_JOB_STOP_PERCENT", "100")  # the older tests below assert "blocked exactly at the limit"; the 90% rule has its own tests
    PaidStub.calls = 0
    for ws in ("cap-ws", "cap-ws2"):
        assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": ws}).status_code == 201
    return main, monkeypatch


def use_paid(env):
    main, mp = env
    mp.setattr(main, "get_provider", lambda: PaidStub())
    mp.setattr(main, "get_provider_for_job", lambda job: PaidStub())


def post(ws="cap-ws", key=None, n=0):
    headers = auth()
    if key:
        headers["Idempotency-Key"] = key
    return client.post("/v1/generation-jobs", headers=headers, json={
        "workspace_id": ws, "prompt": f"p{n}",
        "model_image_url": "https://images.example.org/m.png",
        "garment_image_url": "https://images.example.org/g.png"})


def count_jobs():
    repo = SQLiteJobRepository()
    storage, path, _ = repo._context()
    with storage.transaction(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM generation_jobs").fetchone()[0]


def test_mock_jobs_are_never_limited(cap_env, monkeypatch):
    monkeypatch.setenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "1")
    monkeypatch.setenv("AI_JOBS_DISABLED", "1")
    assert [post(n=i).status_code for i in range(3)] == [202, 202, 202]


def test_workspace_monthly_limit_blocks_with_429_and_persists_nothing(cap_env, monkeypatch):
    use_paid(cap_env)
    monkeypatch.setenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "2")
    assert [post(n=i).status_code for i in range(2)] == [202, 202]
    blocked = post(n=9)
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "WORKSPACE_MONTHLY_LIMIT"
    # R-023: the workspace's own limit and usage are in the body so the screen can show "n/m".
    assert blocked.json()["detail"]["limit"] == 2 and blocked.json()["detail"]["used"] == 2
    assert count_jobs() == 2
    assert post(ws="cap-ws2", n=10).status_code == 202  # other workspace unaffected


def test_idempotent_replay_is_not_blocked_or_double_counted(cap_env, monkeypatch):
    use_paid(cap_env)
    monkeypatch.setenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "1")
    first = post(key="k1", n=1)
    assert first.status_code == 202
    again = post(key="k1", n=1)
    assert again.status_code == 202 and again.json()["job_id"] == first.json()["job_id"]
    assert count_jobs() == 1


def test_global_limit_spans_workspaces(cap_env, monkeypatch):
    use_paid(cap_env)
    monkeypatch.setenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "0")
    monkeypatch.setenv("AI_JOB_LIMIT_GLOBAL_MONTH", "2")
    assert post(n=1).status_code == 202
    assert post(ws="cap-ws2", n=2).status_code == 202
    third = post(n=3)
    assert third.status_code == 429 and third.json()["detail"]["code"] == "GLOBAL_MONTHLY_LIMIT"
    # R-023: service-wide numbers are operating information and are not exposed.
    assert set(third.json()["detail"]) == {"code", "message"}


def test_kill_switch_response_carries_no_numbers(cap_env, monkeypatch):
    use_paid(cap_env)
    monkeypatch.setenv("AI_JOBS_DISABLED", "1")
    blocked = post(n=1)
    assert blocked.status_code == 429 and set(blocked.json()["detail"]) == {"code", "message"}


def test_kill_switch_blocks_creation_and_worker_dispatch(cap_env, monkeypatch):
    import asyncio
    from app import worker
    use_paid(cap_env)
    assert post(n=1).status_code == 202            # queued before the switch
    monkeypatch.setenv("AI_JOBS_DISABLED", "1")
    blocked = post(n=2)
    assert blocked.status_code == 429 and blocked.json()["detail"]["code"] == "AI_JOBS_DISABLED"
    assert asyncio.run(worker.process_one()) is True
    assert PaidStub.calls == 0                      # provider never called
    monkeypatch.delenv("AI_JOBS_DISABLED")
    assert post(n=3).status_code == 202


def test_previous_months_do_not_count(cap_env, monkeypatch):
    from app.cost_cap import enforce_in_transaction, CostCapExceeded
    use_paid(cap_env)
    monkeypatch.setenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "1")
    assert post(n=1).status_code == 202
    repo = SQLiteJobRepository()
    storage, path, _ = repo._context()
    job = {"workspace_id": "cap-ws", "provider": "fashn"}
    with storage.transaction(path) as conn:
        with pytest.raises(CostCapExceeded):
            enforce_in_transaction(conn, job)
        nxt = datetime(2099, 1, 15, tzinfo=timezone.utc)
        enforce_in_transaction(conn, job, now=nxt)  # next month: counter restarts


def test_concurrent_creates_never_exceed_the_limit(cap_env, monkeypatch):
    use_paid(cap_env)
    monkeypatch.setenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "3")
    client.get("/v1/generation-jobs?workspace_id=cap-ws", headers=auth())
    barrier, codes = threading.Barrier(10), []

    def go(i):
        barrier.wait()
        codes.append(post(n=100 + i).status_code)

    ts = [threading.Thread(target=go, args=(i,)) for i in range(10)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert codes.count(202) == 3 and codes.count(429) == 7, codes
    assert count_jobs() == 3


def test_pilot_defaults_are_100_per_workspace_and_500_global_with_a_90_percent_stop(cap_env, monkeypatch):
    from app import cost_cap
    monkeypatch.delenv("AI_JOB_STOP_PERCENT")
    assert cost_cap.stop_percent() == 90
    assert [cost_cap.stop_at(n) for n in (100, 500, 10, 1, 2)] == [90, 450, 9, 1, 1]
    monkeypatch.setenv("AI_JOB_STOP_PERCENT", "100"); assert cost_cap.stop_at(100) == 100
    monkeypatch.setenv("AI_JOB_STOP_PERCENT", "0"); assert cost_cap.stop_percent() == 1     # never "stop at zero": clamped
    monkeypatch.setenv("AI_JOB_STOP_PERCENT", "250"); assert cost_cap.stop_percent() == 100


def test_real_calls_stop_at_90_percent_of_the_limit_with_the_true_limit_in_the_answer(cap_env, monkeypatch):
    use_paid(cap_env)
    monkeypatch.delenv("AI_JOB_STOP_PERCENT")
    monkeypatch.setenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "10")
    for n in range(9):
        assert post(n=n).status_code == 202, n
    blocked = post(n=99)
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "WORKSPACE_MONTHLY_LIMIT"
    assert blocked.json()["detail"]["limit"] == 10 and blocked.json()["detail"]["used"] == 9
    assert PaidStub.calls <= 9, "the blocked request never reached the provider"


def test_real_calls_are_refused_while_no_usd_limit_is_configured(cap_env, monkeypatch):
    use_paid(cap_env)
    monkeypatch.delenv("AI_COST_LIMIT_USD_MONTH")
    refused = post()
    assert refused.status_code == 429 and refused.json()["detail"]["code"] == "AI_JOBS_DISABLED"
    assert PaidStub.calls == 0
    monkeypatch.setenv("AI_COST_LIMIT_USD_MONTH", "not a number")
    assert post(n=1).status_code == 429 and PaidStub.calls == 0
    monkeypatch.setenv("AI_COST_LIMIT_USD_MONTH", "0")
    assert post(n=2).status_code == 429 and PaidStub.calls == 0


def test_the_usd_limit_stops_real_calls_at_90_percent_and_never_limits_mock(cap_env, monkeypatch):
    use_paid(cap_env)
    monkeypatch.delenv("AI_JOB_STOP_PERCENT")
    monkeypatch.setenv("AI_COST_LIMIT_USD_MONTH", "1.00")   # 90% = $0.90 = 12 jobs at $0.075
    for n in range(12):
        assert post(ws="cap-ws" if n % 2 else "cap-ws2", n=n).status_code == 202, n
    blocked = post(n=99)
    assert blocked.status_code == 429 and blocked.json()["detail"]["code"] == "GLOBAL_MONTHLY_LIMIT"
    assert "limit" not in blocked.json()["detail"] and "used" not in blocked.json()["detail"], "service-wide money numbers are not exposed"
    monkeypatch.setenv("AI_COST_LIMIT_USD_MONTH", "2.00")   # raising the limit lets calls through again
    assert post(n=100).status_code == 202


def test_unit_costs_default_to_the_safe_side():
    from app import cost_cap
    assert cost_cap.unit_cost("fashn") == 0.075 and cost_cap.unit_cost("FASHN") == 0.075
    assert cost_cap.unit_cost("some-new-provider") == 0.10


def test_every_job_gets_a_cost_row_estimated_from_the_unit_price_and_a_refused_request_leaves_none(cap_env, monkeypatch):
    import sqlite3
    import app.config as config
    use_paid(cap_env)
    paid = post(n=1)
    assert paid.status_code == 202
    monkeypatch.setenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "1")
    assert post(n=2).status_code == 429                    # refused: nothing may be recorded for it
    db = sqlite3.connect(config.GENERATION_DATABASE_PATH)
    rows = db.execute("SELECT job_id, provider, estimated_cost_usd, latency_ms, error_code FROM generation_job_costs").fetchall()
    assert rows == [(paid.json()["job_id"], "fashn", 0.075, None, None)]
    assert db.execute("SELECT COUNT(*) FROM generation_jobs").fetchone()[0] == 1


def test_mock_jobs_are_recorded_with_zero_cost(cap_env):
    import sqlite3
    import app.config as config
    created = post(n=3)
    assert created.status_code == 202
    db = sqlite3.connect(config.GENERATION_DATABASE_PATH)
    assert db.execute("SELECT provider, estimated_cost_usd FROM generation_job_costs WHERE job_id=?", (created.json()["job_id"],)).fetchone() == ("mock", 0.0)


def test_a_provider_has_its_own_daily_limit_across_workspaces_without_exposing_numbers(cap_env, monkeypatch):
    use_paid(cap_env)
    monkeypatch.setenv("AI_PROVIDER_DAILY_LIMIT", "3")
    assert [post(ws=("cap-ws", "cap-ws2")[n % 2], n=n).status_code for n in range(3)] == [202, 202, 202]
    blocked = post(n=9)
    assert blocked.status_code == 429 and blocked.json()["detail"]["code"] == "DAILY_JOB_LIMIT_EXCEEDED"
    assert "limit" not in blocked.json()["detail"] and "used" not in blocked.json()["detail"]
    monkeypatch.setenv("AI_PROVIDER_DAILY_LIMIT_FASHN", "5")   # the provider-specific value overrides the general one
    assert post(n=10).status_code == 202
    monkeypatch.delenv("AI_PROVIDER_DAILY_LIMIT_FASHN"); monkeypatch.setenv("AI_PROVIDER_DAILY_LIMIT", "0")
    assert post(n=11).status_code == 202, "0 switches the limit off"


def test_the_provider_daily_limit_never_applies_to_mock(cap_env, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_DAILY_LIMIT", "1")
    assert [post(n=n).status_code for n in range(4)] == [202] * 4
