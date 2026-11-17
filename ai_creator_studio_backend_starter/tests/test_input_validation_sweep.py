"""B-09: every JSON write operation gets hostile bodies (missing fields, over-long strings, wrong types, NUL / control characters, very deep nesting) as the workspace OWNER,
so validation (not authorization) decides. None may answer 5xx, and no answer may carry internal detail (stack trace, file path, SQL, driver names).
Driven by the OpenAPI document, so a new route is covered automatically. Known gaps are listed in KNOWN and shrink over time."""
import json
import re

import pytest

from tests.test_authz_matrix import _body, _fill, _operations, auth, client, seeded  # noqa: F401

LEAKS = re.compile(r"Traceback|sqlite3|psycopg|\bSELECT\b|\bINSERT\b|\.py\"|\.py:|[A-Za-z]:\\|/home/|/app/|site-packages|OperationalError|IntegrityError", re.I)
KNOWN: set[tuple[str, str]] = set()      # (method, path) allowed to fail for now; empty is the goal


def _variants(body):
    yield "empty", {}
    yield "wrong-types", {k: 12345 if isinstance(v, str) else "text" for k, v in (body.items() if isinstance(body, dict) else [])}
    yield "long-strings", {k: ("x" * 20000 if isinstance(v, str) else v) for k, v in (body.items() if isinstance(body, dict) else [])}
    yield "control-chars", {k: ("a\u0000b‮\x07" if isinstance(v, str) else v) for k, v in (body.items() if isinstance(body, dict) else [])}
    deep: object = "leaf"
    for _ in range(300):
        deep = {"a": deep}
    yield "deep", {k: deep for k in (body if isinstance(body, dict) else ["x"])}
    yield "list-body", [body]
    yield "null-body", None


def test_no_json_operation_answers_5xx_or_leaks_internals_on_hostile_bodies(seeded):
    bad, leaks, tried = [], [], 0
    for method, path, op in _operations():
        if method == "get" or "application/json" not in op.get("requestBody", {}).get("content", {}):
            continue
        url = _fill(path, seeded)
        query = {p["name"]: seeded.get(p["name"], "x") for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")}
        base = _body(op, seeded)
        for label, payload in _variants(base):
            resp = client.request(method.upper(), url, headers={**auth("tok-a"), "Content-Type": "application/json"}, params=query, content=json.dumps(payload))
            tried += 1
            if resp.status_code >= 500 and (method, path) not in KNOWN:
                bad.append((method, path, label, resp.status_code))
            if LEAKS.search(resp.text):
                leaks.append((method, path, label, LEAKS.search(resp.text).group(0)))
    print("TRIED", tried, "BAD", bad, "LEAKS", leaks)
    assert tried > 100, tried
    assert not leaks, leaks
    assert not bad, bad


@pytest.mark.parametrize("value", ["x" * 5000, "..%2f..%2fetc%2fpasswd", "%00", "a b", "ä" * 300])
def test_odd_path_ids_are_clean_4xx(seeded, value):
    from urllib.parse import quote
    bad = []
    for method, path, op in _operations():
        if method != "get" or "{" not in path:
            continue
        url = re.sub(r"\{[^}]+\}", quote(value, safe=""), path)
        query = {p["name"]: seeded.get(p["name"], "x") for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")}
        resp = client.get(url, headers=auth("tok-a"), params=query)
        if resp.status_code >= 500 or LEAKS.search(resp.text):
            bad.append((path, resp.status_code))
    assert not bad, bad
