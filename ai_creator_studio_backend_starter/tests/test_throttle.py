"""R-037: calls to a real provider stay below its concurrency and per-minute limits; mock is never throttled."""
import asyncio

from app.throttle import ProviderThrottle, throttle_for


def run(coro):
    return asyncio.run(coro)


def test_never_more_calls_in_flight_than_allowed():
    async def scenario():
        t = ProviderThrottle(max_concurrency=2, max_per_window=1000)
        inflight = peak = 0

        async def call():
            nonlocal inflight, peak
            async with t.slot():
                inflight += 1; peak = max(peak, inflight)
                await asyncio.sleep(0.01)
                inflight -= 1
        await asyncio.gather(*[call() for _ in range(10)])
        return peak
    assert run(scenario()) == 2


def test_never_more_calls_per_window_than_allowed_and_waiting_calls_go_through_later():
    async def scenario():
        now = [0.0]
        slept = []

        async def fake_sleep(seconds):
            slept.append(seconds); now[0] += seconds
        t = ProviderThrottle(max_concurrency=10, max_per_window=3, window_seconds=60, clock=lambda: now[0], sleep=fake_sleep)
        stamps = []
        for _ in range(7):
            async with t.slot():
                stamps.append(now[0])
        return stamps, slept
    stamps, slept = run(scenario())
    assert stamps[:3] == [0.0, 0.0, 0.0] and stamps[3] == 60.0 and stamps[6] == 120.0   # 3 per 60 s window, the rest wait for the next one
    assert slept and all(s > 0 for s in slept)
    # in any 60 s window at most 3 calls started
    assert all(sum(1 for x in stamps if lo <= x < lo + 60) <= 3 for lo in stamps)


def test_limits_come_from_the_environment_with_safe_defaults(monkeypatch):
    async def scenario():
        monkeypatch.delenv("PROVIDER_MAX_CONCURRENCY", raising=False); monkeypatch.delenv("PROVIDER_MAX_PER_MINUTE", raising=False)
        a = throttle_for("fashn-default")
        monkeypatch.setenv("PROVIDER_MAX_CONCURRENCY", "nonsense"); monkeypatch.setenv("PROVIDER_MAX_PER_MINUTE", "0")
        b = throttle_for("fashn-bad-values")
        return a._slots._value, a._max, b._slots._value, b._max, throttle_for("fashn-default") is a
    assert run(scenario()) == (4, 60, 4, 1, True)   # defaults below FASHN's 6 / 100; nonsense -> default concurrency; 0 -> at least 1
