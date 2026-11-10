"""Temporary takedown of an asset after a rights-infringement report (L-08): storage and visibility rules, no HTTP.

States of an asset's takedown row (no row = not held):
- ``under_review``: a report is open. Only the asset's owner (assets.owner_id) can still see it.
- ``removed``: an operator upheld a report. Nobody sees it through the asset API, the owner included.
Nothing is deleted from storage here: a hold is reversible, and "removed" means hidden for good, not erased.
Reporter identities live only in ``content_reports`` and are returned to operators, never to the asset's owner.
"""
from __future__ import annotations

from typing import Any

UNDER_REVIEW = "under_review"
REMOVED = "removed"


def state_of(asset_id: str) -> dict[str, Any] | None:
    from app.assets.store import _connect, initialize
    initialize()
    with _connect() as db:
        row = db.execute("SELECT state, since FROM asset_takedowns WHERE asset_id=?", (asset_id,)).fetchone()
    return {"state": row["state"], "since": row["since"]} if row else None


def visible_to(asset_id: str, user_id: str | None) -> bool:
    """Whether the asset API may show this asset to this user (None = no identity, e.g. a signed URL). Membership is
    checked elsewhere; this only adds the hold."""
    from app.assets.store import _connect, initialize
    initialize()
    with _connect() as db:
        row = db.execute("""SELECT t.state, a.owner_id FROM asset_takedowns t JOIN assets a ON a.asset_id=t.asset_id
            WHERE t.asset_id=?""", (asset_id,)).fetchone()
    if row is None:
        return True
    return row["state"] == UNDER_REVIEW and row["owner_id"] == user_id


def filter_listing(items: list[dict[str, Any]], user_id: str) -> list[dict[str, Any]]:
    """Drop held assets the user may not see from a listing."""
    from app.assets.store import _connect, initialize
    initialize()
    with _connect() as db:
        held = {r["asset_id"]: (r["state"], r["owner_id"]) for r in db.execute(
            "SELECT t.asset_id, t.state, a.owner_id FROM asset_takedowns t JOIN assets a ON a.asset_id=t.asset_id")}
    return [i for i in items if i.get("asset_id") not in held
            or (held[i["asset_id"]][0] == UNDER_REVIEW and held[i["asset_id"]][1] == user_id)]


def held_among(db, asset_ids: list[str]) -> list[str]:
    """Which of these assets are on hold (any state), using an already open connection. Used by the paths that read an
    asset's bytes on their own (photo processing, lookbook export) so a held asset cannot be copied or packaged."""
    ids = [i for i in dict.fromkeys(asset_ids) if i]
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    return [r["asset_id"] for r in db.execute(f"SELECT asset_id FROM asset_takedowns WHERE asset_id IN ({marks})", ids)]
