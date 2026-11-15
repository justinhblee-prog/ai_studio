"""Throttle for calls to a real (external) AI provider (R-037, reply 14): at most N calls in flight and at most M calls per minute, per provider,
so the provider's own limits (FASHN: 100 requests / 60 s, 6 concurrent) are never reached by us. The mock provider is never throttled.

  PROVIDER_MAX_CONCURRENCY=4   (default 4, below FASHN's 6)
  PROVIDER_MAX_PER_MINUTE=60   (default 60, below FASHN's 100)
"""
from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from contextlib import asynccontextmanager


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


class ProviderThrottle:
    def __init__(self, max_concurrency: int, max_per_window: int, window_seconds: float = 60.0, clock=time.monotonic, sleep=asyncio.sleep):
        self._slots = asyncio.Semaphore(max_concurrency)
        self._max, self._window, self._clock, self._sleep = max_per_window, window_seconds, clock, sleep
        self._stamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def _wait_for_window(self) -> None:
        while True:
            async with self._lock:
                now = self._clock()
                while self._stamps and now - self._stamps[0] >= self._window:
                    self._stamps.popleft()
                if len(self._stamps) < self._max:
                    self._stamps.append(now)
                    return
                wait = self._window - (now - self._stamps[0])
            await self._sleep(max(wait, 0.01))

    @asynccontextmanager
    async def slot(self):
        async with self._slots:
            await self._wait_for_window()
            yield


_throttles: dict[str, ProviderThrottle] = {}


def throttle_for(provider: str) -> ProviderThrottle:
    """One throttle per provider and per event loop (limits are read from the environment when it is first needed)."""
    key = f"{provider}:{id(asyncio.get_running_loop())}"
    if key not in _throttles:
        _throttles[key] = ProviderThrottle(_int_env("PROVIDER_MAX_CONCURRENCY", 4), _int_env("PROVIDER_MAX_PER_MINUTE", 60))
    return _throttles[key]
