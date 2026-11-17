"""B-04: who may read the platform's operations / audit records. Every GET under /internal/ or /v1/ops is for platform operators only (OPS_ADMIN_USER_IDS):
an ordinary workspace owner gets 403, nobody gets 401, and an operator is let through. Driven by the OpenAPI document, so a new operations route is covered automatically."""
from tests.test_authz_matrix import _fill, _operations, auth, client, seeded  # noqa: F401
from app import config


WORKSPACE_ADMIN_TOOLS = {"/internal/ops/poll-tasks"}      # by design a per-workspace view for that workspace's owner/admin (needs ?workspace_id=); everyone else is refused


def _ops_gets():
    for method, path, op in _operations():
        if method == "get" and (path.startswith("/internal/") or path.startswith("/v1/ops")):
            yield path, op


def _call(path, op, seeded_ids, token):
    query = {p["name"]: seeded_ids.get(p["name"], "x") for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")}
    kw = {"headers": auth(token)} if token else {}
    return client.get(_fill(path, seeded_ids), params=query, **kw).status_code


def test_operations_and_audit_reads_are_for_platform_operators_only(seeded, monkeypatch):
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"tok-a": "user-a", "tok-b": "user-b", "tok-ops": "user-ops"})
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", ("user-ops",))
    paths = list(_ops_gets())
    assert len(paths) >= 8, [p for p, _ in paths]
    leaks, anon, blocked_operator = [], [], []
    for path, op in paths:
        if path in WORKSPACE_ADMIN_TOOLS:
            assert _call(path, op, seeded, "tok-b") in (403, 404), f"{path}: a stranger to the workspace must be refused"
            assert _call(path, op, seeded, None) == 401
            continue
        if _call(path, op, seeded, "tok-a") not in (401, 403):          # the workspace OWNER is not a platform operator
            leaks.append(path)
        if _call(path, op, seeded, None) != 401:
            anon.append(path)
        if _call(path, op, seeded, "tok-ops") in (401, 403):
            blocked_operator.append(path)
    assert not leaks, f"an ordinary workspace owner can read: {leaks}"
    assert not anon, f"anonymous callers are not refused with 401: {anon}"
    assert not blocked_operator, f"a platform operator is refused: {blocked_operator}"
