"""Lane 2/5: public routes for the generated base human models."""
import pytest
from fastapi.testclient import TestClient

from app.assets.validation import validate_gltf_upload
from app.glb_tools import parse_glb
from app.main import app

client = TestClient(app)


def test_the_choices_are_listed_without_signing_in():
    r = client.get("/v1/base-models")
    assert r.status_code == 200 and r.headers["cache-control"].startswith("public")
    body = r.json()
    assert body["sexes"] == ["male", "female"] and body["top_styles"] == ["tank", "tshirt", "longsleeve"] and body["bottom_styles"] == ["shorts", "pants"]
    assert set(body["default_colors"]) == {"skin", "top", "bottom"} and body["materials"] == ["skin", "top", "bottom"]


@pytest.mark.parametrize("sex", ["male", "female"])
def test_the_glb_is_a_valid_binary_model_with_cache_headers_and_no_sign_in(sex):
    r = client.get(f"/v1/base-models/{sex}/glb")
    assert r.status_code == 200 and r.headers["content-type"] == "model/gltf-binary"
    assert validate_gltf_upload("m.glb", r.content).media_type == "model/gltf-binary"
    assert r.headers["etag"].startswith('"') and "max-age=86400" in r.headers["cache-control"] and f"base_{sex}.glb" in r.headers["content-disposition"]
    assert parse_glb(r.content)[0]["nodes"][0]["extras"]["sex_preset"] == sex


def test_query_colours_and_styles_change_the_file():
    plain = client.get("/v1/base-models/male/glb").content
    red = client.get("/v1/base-models/male/glb", params={"top": "FF0000", "bottom": "00ff00", "skin": "0a141e"})
    assert red.status_code == 200 and red.content != plain
    doc, _ = parse_glb(red.content)
    mats = {m["name"]: m["pbrMetallicRoughness"]["baseColorFactor"] for m in doc["materials"]}
    assert mats["top"][:3] == [1.0, 0.0, 0.0] and mats["bottom"][:3] == [0.0, 1.0, 0.0] and mats["skin"][0] == pytest.approx(10 / 255, abs=1e-6)
    assert client.get("/v1/base-models/male/glb", params={"top_style": "longsleeve", "bottom_style": "shorts"}).content != plain
    assert client.get("/v1/base-models/male/glb", params={"top": "ff0000"}).content == client.get("/v1/base-models/male/glb", params={"top": "FF0000"}).content, "case does not matter"


def test_a_repeat_request_with_the_etag_gets_304_and_nothing_else():
    first = client.get("/v1/base-models/female/glb")
    again = client.get("/v1/base-models/female/glb", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304 and again.content == b"" and again.headers["etag"] == first.headers["etag"]
    assert client.get("/v1/base-models/female/glb", headers={"If-None-Match": '"other"'}).status_code == 200


@pytest.mark.parametrize("path,params", [
    ("/v1/base-models/robot/glb", {}), ("/v1/base-models/male/glb", {"top_style": "cape"}), ("/v1/base-models/male/glb", {"bottom_style": "skirt"}),
    ("/v1/base-models/male/glb", {"top": "#ff0000"}), ("/v1/base-models/male/glb", {"top": "ff00"}), ("/v1/base-models/male/glb", {"skin": "zzzzzz"}),
    ("/v1/base-models/male/glb", {"bottom": "ff00001"}),
])
def test_bad_input_is_a_422_and_never_a_file(path, params):
    r = client.get(path, params=params)
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/json")


def test_the_routes_are_in_the_openapi_description():
    spec = client.get("/openapi.json").json()
    assert "/v1/base-models" in spec["paths"] and "/v1/base-models/{sex}/glb" in spec["paths"]
    ops = {spec["paths"]["/v1/base-models"]["get"]["operationId"], spec["paths"]["/v1/base-models/{sex}/glb"]["get"]["operationId"]}
    assert ops == {"listBaseModels", "getBaseModelGlb"}
