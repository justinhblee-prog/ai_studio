"""B-24: every date-time the API sends is unambiguous. A timestamp without a time zone ("2026-11-17T09:00:00") is read in the viewer's own zone by browsers and drifts by hours;
the server must send UTC with an explicit offset ("...Z" or "+00:00"). All GET operations are called as the owner of a seeded workspace and every string in every JSON answer that
looks like a date-time must carry an offset (and must not use a space instead of the "T")."""
import json
import re

from tests.test_authz_matrix import _fill, _operations, auth, client, seeded  # noqa: F401

DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?")
HAS_OFFSET = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")
KNOWN: set[str] = set()      # JSON paths allowed to be naive for now (e.g. "GET /path: field"), with a reason; empty is the goal


def _walk(value, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk(v, f"{path}.{k}" if path else k)
    elif isinstance(value, list):
        for v in value[:20]:
            yield from _walk(v, path + "[]")
    elif isinstance(value, str):
        yield path, value


def test_every_timestamp_in_every_get_answer_has_a_time_zone(seeded):
    bad, seen = [], 0
    for method, path, op in _operations():
        if method != "get":
            continue
        query = {p["name"]: seeded.get(p["name"], "x") for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")}
        r = client.get(_fill(path, seeded), headers=auth("tok-a"), params=query)
        if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
            continue
        try:
            body = r.json()
        except json.JSONDecodeError:
            continue
        for field, text in _walk(body):
            if DATETIME.match(text):
                seen += 1
                key = f"GET {path}: {field}"
                if (not HAS_OFFSET.search(text) or " " in text[:11]) and key not in KNOWN:
                    bad.append((key, text))
    print("TIMESTAMPS SEEN", seen, "BAD", bad)
    assert seen >= 5, seen
    assert not bad, bad
