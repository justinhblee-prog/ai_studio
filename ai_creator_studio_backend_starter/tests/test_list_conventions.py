"""B-16: list endpoints (GET with a ``limit`` query parameter) follow one paging convention, read from the OpenAPI document so a new list cannot drift silently.

Convention: ``limit`` is an integer with minimum 1, a maximum and a default not above that maximum; ``offset`` (when present) is an integer with minimum 0.
Cursor style lists (``cursor`` instead of ``offset``) are allowed but must be named in CURSOR_LISTS so the choice is deliberate.
The table is printed (pytest -s) so the survey can be copied into docs.
"""
from app.main import app

CURSOR_LISTS = {"/v1/library/items", "/v1/generation-jobs/{job_id}/executions"}
MAX_LIMIT_CEILING = 500


def _survey() -> list[dict]:
    rows = []
    for path, item in sorted(app.openapi()["paths"].items()):
        op = item.get("get")
        if not op:
            continue
        params = {p["name"]: p for p in op.get("parameters", []) if p.get("in") == "query"}
        if "limit" not in params:
            continue
        lim = params["limit"]["schema"]
        rows.append({
            "path": path, "limit_default": lim.get("default"), "limit_min": lim.get("minimum"), "limit_max": lim.get("maximum"),
            "limit_type": lim.get("type"), "paging": "cursor" if "cursor" in params else ("offset" if "offset" in params else "none"),
            "offset_min": params["offset"]["schema"].get("minimum") if "offset" in params else None,
            "sort": "sort" in params,
        })
    return rows


def test_survey_prints_and_is_not_empty():
    rows = _survey()
    for r in rows:
        print("LIST", r)
    assert len(rows) >= 10


def test_every_list_has_bounded_limit():
    bad = [r["path"] for r in _survey() if r["limit_type"] != "integer" or not r["limit_min"] or r["limit_min"] < 1 or not r["limit_max"] or r["limit_max"] > MAX_LIMIT_CEILING
           or (r["limit_default"] is not None and r["limit_default"] > r["limit_max"])]
    print("UNBOUNDED", bad)
    assert bad == []


def test_offset_lists_have_non_negative_offset_and_cursor_lists_are_declared():
    rows = _survey()
    assert [r["path"] for r in rows if r["paging"] == "offset" and r["offset_min"] != 0] == []
    assert {r["path"] for r in rows if r["paging"] == "cursor"} == CURSOR_LISTS
