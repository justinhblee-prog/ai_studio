"""POST /v1/workspaces/{id}/fit-check: S/M/L ease comparison + recommendation (ease_map), behind the own3d flag, viewer or above."""
import pytest
from fastapi.testclient import TestClient

from app import config, ease_map
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
URL = "/v1/workspaces/wa/fit-check"
BODY = {"sex": "female", "kind": "top"}


@pytest.fixture
def opened(env, monkeypatch):
    monkeypatch.setattr(config, "RENDER3D_ENABLED", True)
    return env


def test_closed_by_default_after_the_usual_checks(env):
    assert client.post(URL, json=BODY).status_code in (401, 403)
    assert client.post(URL, headers=auth("a"), json=BODY).json()["detail"]["code"] == "RENDER3D_CLOSED"
    assert client.post("/v1/workspaces/wb/fit-check", headers=auth("a"), json=BODY).status_code in (403, 404)


def test_returns_the_three_sizes_with_zone_ease_and_a_recommendation(opened):
    r = client.post(URL, headers=auth("a"), json=BODY)
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data["sizes"]) == {"S", "M", "L"} and data["engine"] == "own3d" and data["limits"]["source"] == "proposal"
    assert data["recommended"] in (None, "S", "M", "L")
    for size in data["sizes"].values():
        assert set(size["zones"]) == {"chest_cm", "waist_cm"} and {"min", "median", "p95"} <= set(size["clearance_cm"]) and 0 <= size["pressure_share"] <= 1
    assert data == {**ease_map.compare("top", "female"), "engine": "own3d"}          # the endpoint adds nothing to the library result


def test_a_viewer_may_ask_and_a_bigger_body_moves_the_recommendation_up(opened):
    assert client.post(URL, headers=auth("c"), json=BODY).status_code == 200
    small = client.post(URL, headers=auth("a"), json={**BODY, "measurements": {"chest_cm": 80, "waist_cm": 66}}).json()
    large = client.post(URL, headers=auth("a"), json={**BODY, "measurements": {"chest_cm": 104, "waist_cm": 90}}).json()
    order = {None: 4, "S": 1, "M": 2, "L": 3}
    assert order[large["recommended"]] >= order[small["recommended"]]


@pytest.mark.parametrize("body", [{**BODY, "measurements": {"chest_cm": 5}}, {**BODY, "nominal": {"inseam": 80}}, {**BODY, "nominal": {"chest_cm": 900}}])
def test_bad_values_are_422_with_a_catalogued_code(opened, body):
    r = client.post(URL, headers=auth("a"), json=body)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "FIT_CHECK_INVALID"


def test_unknown_fields_and_kinds_are_refused(opened):
    assert client.post(URL, headers=auth("a"), json={**BODY, "extra": 1}).status_code == 422
    assert client.post(URL, headers=auth("a"), json={**BODY, "kind": "hat"}).status_code == 422
