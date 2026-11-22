"""B-22: the outbox worker's decisions for one event, with a fake repository and fake providers (no database, no network, no paid call)."""
import asyncio

import pytest

from app import cost_cap, main, tryon_inputs, worker


class FakeRepo:
    def __init__(self, event=None, job=None):
        self.event, self.job = event, job
        self.calls = []

    def initialize(self):
        self.calls.append(("initialize",))

    def heartbeat_worker(self, worker_id, state, info):
        self.calls.append(("heartbeat", state, info["worker_type"]))

    def claim_next_outbox(self, worker_id, lease):
        self.calls.append(("claim", lease))
        event, self.event = self.event, None
        return event

    def get_job(self, job_id):
        return self.job

    def mark_outbox_unknown(self, event_id, job_id, message, worker_id):
        self.calls.append(("unknown", event_id, job_id, message))

    def complete_outbox_submission(self, event_id, job_id, request_id, worker_id):
        self.calls.append(("complete", event_id, job_id, request_id))


class FakeProvider:
    def __init__(self, name="mock", answer=None, error=None):
        self.name, self.answer, self.error, self.started = name, answer if answer is not None else {"request_id": "req_1"}, error, []

    async def start(self, payload):
        self.started.append(payload)
        if self.error:
            raise self.error
        return self.answer


EVENT = {"event_id": "e1", "job_id": "j1"}
JOB = {"job_id": "j1", "payload": {"x": 1}, "provider": "mock"}


@pytest.fixture
def wired(monkeypatch):
    holder = {"provider": FakeProvider()}
    monkeypatch.setattr(main, "get_provider_for_job", lambda job: holder["provider"])
    monkeypatch.setattr(tryon_inputs, "resolve_payload", lambda payload, for_provider: {**payload, "for_provider": for_provider})
    monkeypatch.setattr(cost_cap, "kill_switch_on", lambda: False)
    return holder


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_nothing_to_do_returns_false_and_touches_nothing_else():
    repo = FakeRepo()
    assert run(worker.process_one(repo)) is False and repo.calls == [("claim", worker.LEASE_SECONDS)]


def test_a_missing_job_record_is_marked_unknown_not_dropped(wired):
    repo = FakeRepo(EVENT, None)
    assert run(worker.process_one(repo)) is True
    assert repo.calls[-1] == ("unknown", "e1", "j1", "Job record missing for outbox event.")


def test_the_mock_provider_runs_without_the_throttle_and_the_submission_is_completed(wired):
    repo = FakeRepo(EVENT, JOB)
    assert run(worker.process_one(repo)) is True
    assert repo.calls[-1] == ("complete", "e1", "j1", "req_1") and wired["provider"].started == [{"x": 1, "for_provider": False}]


def test_a_real_provider_goes_through_the_throttle_and_gets_provider_addresses(wired):
    wired["provider"] = FakeProvider(name="fashn", answer={"request_id": "pred_7"})
    repo = FakeRepo(EVENT, JOB)
    assert run(worker.process_one(repo)) is True
    assert repo.calls[-1] == ("complete", "e1", "j1", "pred_7") and wired["provider"].started == [{"x": 1, "for_provider": True}]


def test_the_kill_switch_stops_a_real_provider_before_anything_is_sent(wired, monkeypatch):
    wired["provider"] = FakeProvider(name="fashn")
    monkeypatch.setattr(cost_cap, "kill_switch_on", lambda: True)
    repo = FakeRepo(EVENT, JOB)
    assert run(worker.process_one(repo)) is True
    assert wired["provider"].started == [] and repo.calls[-1] == ("unknown", "e1", "j1", "RuntimeError")


def test_the_kill_switch_does_not_stop_the_free_mock(wired, monkeypatch):
    monkeypatch.setattr(cost_cap, "kill_switch_on", lambda: True)
    repo = FakeRepo(EVENT, JOB)
    run(worker.process_one(repo))
    assert repo.calls[-1][0] == "complete"


@pytest.mark.parametrize("answer", [{}, {"request_id": ""}, {"request_id": None}])
def test_an_answer_without_a_request_id_is_marked_unknown(wired, answer):
    wired["provider"] = FakeProvider(answer=answer)
    repo = FakeRepo(EVENT, JOB)
    run(worker.process_one(repo))
    assert repo.calls[-1] == ("unknown", "e1", "j1", "RuntimeError")


@pytest.mark.parametrize("error", [TimeoutError("slow"), ConnectionError("gone"), ValueError("bad")])
def test_any_error_is_recorded_by_type_only_and_never_replayed(wired, error):
    """A timeout may come AFTER the provider accepted the work, so the event is never retried automatically; only the exception TYPE is kept (no message, no secret)."""
    wired["provider"] = FakeProvider(error=error)
    repo = FakeRepo(EVENT, JOB)
    assert run(worker.process_one(repo)) is True
    assert repo.calls[-1] == ("unknown", "e1", "j1", type(error).__name__) and len(wired["provider"].started) == 1


def test_run_forever_registers_a_heartbeat_and_sleeps_when_idle(monkeypatch):
    repo = FakeRepo()
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        raise asyncio.CancelledError

    monkeypatch.setattr(worker.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        run(worker.run_forever(repo))
    assert repo.calls[0] == ("initialize",) and repo.calls.count(("heartbeat", "running", "outbox")) == 2 and slept == [worker.POLL_SECONDS]
