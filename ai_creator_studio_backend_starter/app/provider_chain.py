"""R-046 / R-037 remainder: primary + fallback provider ORDER as a pure structure (no second adapter exists yet, nothing here calls a provider).

The one rule that matters for money: a fallback may only be tried when the previous provider DEFINITELY did not accept the job
(``not_accepted``: refused before any request id, e.g. a clear HTTP 4xx/5xx answer or a configuration refusal). A timeout, a dropped connection
or any answer we cannot read is ``unknown``: the job may be running (and billed) at the first provider, so it is NEVER replayed anywhere else.
"""
from __future__ import annotations

from dataclasses import dataclass

NOT_ACCEPTED, UNKNOWN, ACCEPTED = "not_accepted", "unknown", "accepted"


@dataclass(frozen=True)
class ProviderChain:
    primary: str
    fallbacks: tuple[str, ...] = ()

    def __post_init__(self):
        order = (self.primary, *self.fallbacks)
        if not self.primary or any(not p for p in order):
            raise ValueError("provider ids must not be empty")
        if len(set(order)) != len(order):
            raise ValueError("a provider may appear only once in a chain")

    @property
    def order(self) -> tuple[str, ...]:
        return (self.primary, *self.fallbacks)

    def next_after(self, tried: list[str], outcome: str) -> str | None:
        """The provider to try next, or None. ``tried`` are the providers already attempted, ``outcome`` is how the LAST one ended."""
        if outcome != NOT_ACCEPTED:
            return None   # accepted -> done, unknown -> never replay
        for provider in self.order:
            if provider not in tried:
                return provider
        return None


def parse_chain(primary: str, fallback_setting: str | None) -> ProviderChain:
    """``fallback_setting`` is a comma list from an environment value; unknown spellings are not guessed, duplicates are refused."""
    fallbacks = tuple(p.strip().lower() for p in (fallback_setting or "").split(",") if p.strip())
    return ProviderChain(primary.strip().lower(), fallbacks)
