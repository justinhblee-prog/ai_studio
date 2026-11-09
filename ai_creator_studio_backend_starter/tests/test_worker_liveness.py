"""A worker that heartbeats while idle or working is alive; only error/stopped or a stale heartbeat is not."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def ops(monkeypatch, tmp_path):
    from app import config
    from app.repositories.operations import build_operations_monitoring_repository, build_worker_health_repository, build_worker_heartbeat_repository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "liveness.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    return {"config": config, "beat": build_worker_heartbeat_repository().heartbeat, "health": build_worker_health_repository(),
            "monitor": build_operations_monitoring_repository()}


def age(config, worker_id, seconds):
    old = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
    db = sqlite3.connect(config.ASSET_DATABASE_PATH)
    db.execute("UPDATE generation_worker_heartbeats SET last_seen_at=? WHERE worker_id=?", (old, worker_id)); db.commit(); db.close()


@pytest.mark.parametrize("state,alive", [("running", True), ("idle", True), ("working", True), ("error", False), ("stopped", False)])
def test_worker_health_depends_on_the_heartbeat_state(ops, state, alive):
    ops["beat"]("w1", state, {"worker_type": "output_asset_link"})
    worker = ops["health"].worker_health(30)["workers"][0]
    assert worker["healthy"] is alive, state
    assert ops["monitor"].snapshot(30)["workers"][0]["healthy"] is alive, state


def test_a_stale_heartbeat_is_not_healthy_whatever_the_state(ops):
    ops["beat"]("w1", "idle", {"worker_type": "output_asset_link"})
    age(ops["config"], "w1", 120)
    assert ops["health"].worker_health(30)["workers"][0]["healthy"] is False


def test_an_idle_asset_link_worker_does_not_raise_a_worker_stale_alert(ops):
    """The default required worker types include output_asset_link, which only ever reports idle/working."""
    for worker_id, worker_type, state in (("o", "outbox", "running"), ("p", "provider_poll", "running"), ("l", "output_asset_link", "idle")):
        ops["beat"](worker_id, state, {"worker_type": worker_type})
    alerts = ops["monitor"].evaluate_alerts(required_worker_types=("outbox", "provider_poll", "output_asset_link"))
    assert [a["fingerprint"] for a in alerts if a["fingerprint"].startswith("worker:")] == []


def test_a_missing_or_errored_required_worker_still_alerts(ops):
    ops["beat"]("o", "running", {"worker_type": "outbox"})
    ops["beat"]("l", "error", {"worker_type": "output_asset_link"})
    fingerprints = {a["fingerprint"] for a in ops["monitor"].evaluate_alerts(required_worker_types=("outbox", "provider_poll", "output_asset_link"))}
    assert fingerprints == {"worker:provider_poll:stale", "worker:output_asset_link:stale"}
