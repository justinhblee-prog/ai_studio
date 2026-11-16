"""R-060: file a finished job's result in the workspace library (kind render) with server-recorded attributes; idempotent; same workspace only."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.output_asset_link_worker import process_one
from tests.test_output_asset_link_worker import linked_output_env  # noqa: F401
from tests.test_photo_steps_api import auth as auth_photo, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)
from tests.test_video_jobs import item, make, pattern

client = TestClient(app)
A = {"Authorization": "Bearer token-user-a"}
B = {"Authorization": "Bearer token-user-b"}
WS = "ws-output-link"


def lib(headers=A, ws=WS):
    return client.get(f"/v1/workspaces/{ws}/library", headers=headers).json()


def from_job(body, headers=A, ws=WS):
    return client.post(f"/v1/workspaces/{ws}/library/from-job", headers=headers, json=body)


def png_asset(ws=WS, headers=A, color=(9, 9, 9)):
    buf = io.BytesIO(); Image.new("RGB", (16, 16), color).save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=headers, data={"workspace_id": ws, "rights_confirmed": "true"}, files={"file": ("s.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def linked(env_):
    job_id = env_["job_id"]
    out = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=A).json()["data"][0]
    assert process_one(worker_id="delivery-worker") is True
    return job_id, out["id"]


def test_an_unreviewed_result_is_not_filed_and_an_approved_one_is_filed_once(linked_output_env):
    job_id, output_id = linked(linked_output_env)
    r = from_job({"job_id": job_id})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "OUTPUT_NOT_APPROVED" and lib()["total"] == 0
    assert client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve", headers=A, json={"comment": "ok"}).status_code == 200
    assert lib()["total"] == 1, "the approval itself already filed it (R-046)"
    first = from_job({"job_id": job_id, "name": "내 결과", "attrs": {"sku": "SKU-001"}})
    assert first.status_code == 200, first.text      # already filed: the existing item is returned
    again = from_job({"job_id": job_id})
    assert again.status_code == 200 and again.json()["item_id"] == first.json()["item_id"] and lib()["total"] == 1
    item_ = again.json()
    assert item_["kind"] == "render" and item_["origin"] == "ai" and item_["is_ai_generated"] is True
    assert item_["attrs"]["service"] == "tryon", "the server-known attributes were added to the item the approval had filed"


def test_style_region_and_inputs_are_recorded_and_the_callers_attributes_are_validated(linked_output_env):
    import app.workspace_library as wl
    from app.main import app as _app  # noqa: F401
    job_id, output_id = linked(linked_output_env)
    # file before approval is impossible, so approve through the review API with the hook turned off to see the from-job path create the item
    import app.main as main
    original = wl.file_generated_output
    wl.file_generated_output = lambda *a, **k: "skipped"
    try:
        assert client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve", headers=A, json={"comment": "ok"}).status_code == 200
    finally:
        wl.file_generated_output = original
    assert lib()["total"] == 0
    extra = png_asset(color=(1, 2, 3))
    r = from_job({"job_id": job_id, "output_id": output_id, "name": " 가을 룩 ", "tags": ["a", "b"], "attrs": {"sku": "SKU-9", "service": "hacked"}, "source_asset_ids": [extra, extra]})
    assert r.status_code == 201, r.text
    item_ = r.json()
    assert item_["name"] == "가을 룩" and item_["tags"] == ["a", "b"] and item_["kind"] == "render" and item_["origin"] == "ai"
    assert item_["attrs"]["service"] == "tryon", "the caller cannot overwrite what the server knows"
    assert item_["attrs"]["sku"] == "SKU-9" and item_["attrs"]["source_asset_ids"] == [extra], "listed once"
    assert from_job({"job_id": job_id}).status_code == 200 and lib()["total"] == 1
    assert [i["attrs"]["service"] for i in lib(ws=WS)["items"]] == ["tryon"]
    found = client.get(f"/v1/workspaces/{WS}/library", headers=A, params={"attr": "service:tryon"}).json()
    assert found["total"] == 1, "R-058 filters see it"


def test_bad_attributes_and_sources_are_refused_and_nothing_is_filed(linked_output_env):
    import app.workspace_library as wl
    job_id, output_id = linked(linked_output_env)
    original = wl.file_generated_output
    wl.file_generated_output = lambda *a, **k: "skipped"
    try:
        client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve", headers=A, json={"comment": "ok"})
    finally:
        wl.file_generated_output = original
    for bad in ({"attrs": {"Bad Key": "x"}}, {"attrs": {"k": "x" * 61}}, {"attrs": "x"}, {"source_asset_ids": ["asset_nope"]}, {"source_asset_ids": [1]},
                {"source_asset_ids": ["a"] * 11}, {"unknown": 1}, {"output_id": "out_nope"}):
        r = from_job({"job_id": job_id, **bad})
        assert r.status_code in (404, 422), (bad, r.status_code, r.text)
    assert lib()["total"] == 0


def test_another_workspaces_assets_and_jobs_are_refused(linked_output_env):
    import app.workspace_library as wl
    from app.assets.store import create_workspace
    job_id, output_id = linked(linked_output_env)
    original = wl.file_generated_output
    wl.file_generated_output = lambda *a, **k: "skipped"
    try:
        client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve", headers=A, json={"comment": "ok"})
    finally:
        wl.file_generated_output = original
    create_workspace("ws-other", "user-a")
    foreign = png_asset(ws="ws-other")
    r = from_job({"job_id": job_id, "source_asset_ids": [foreign]})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "SOURCE_ASSET_INVALID" and lib()["total"] == 0, "an asset of another workspace is not a valid input"
    assert from_job({"job_id": job_id}, ws="ws-other").status_code == 404, "the job belongs to another workspace"
    assert lib(ws="ws-other")["total"] == 0


def test_roles_and_authentication(linked_output_env):
    job_id, _ = linked(linked_output_env)
    assert client.post(f"/v1/workspaces/{WS}/library/from-job", json={"job_id": job_id}).status_code == 401
    assert from_job({"job_id": job_id}, headers=B).status_code in (403, 404), "not a member"


def test_unfinished_and_unknown_jobs_are_refused(linked_output_env):
    assert from_job({"job_id": "job_" + "0" * 32}).status_code == 404
    queued = client.post("/v1/generation-jobs", headers=A, json={"workspace_id": WS, "model_image_url": "https://example.com/m.jpg", "garment_image_url": "https://example.com/g.jpg"})
    assert queued.status_code == 202
    r = from_job({"job_id": queued.json()["job_id"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "JOB_NOT_FINISHED"


def test_a_deleted_result_asset_cannot_be_filed(linked_output_env):
    import app.workspace_library as wl
    job_id, output_id = linked(linked_output_env)
    original = wl.file_generated_output
    wl.file_generated_output = lambda *a, **k: "skipped"
    try:
        approved = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve", headers=A, json={"comment": "ok"})
    finally:
        wl.file_generated_output = original
    asset_id = approved.json()["output"]["asset_id"]
    assert client.delete(f"/v1/assets/{asset_id}", headers=A).status_code in (200, 204)
    r = from_job({"job_id": job_id})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "OUTPUT_UNAVAILABLE" and lib()["total"] == 0


def test_a_finished_video_is_filed_with_its_inputs_and_only_once(env):
    ids = [item(pattern(1), name="a"), item(pattern(2), name="b")]
    job = make({"input_item_ids": ids}).json()
    assert job["status"] == "succeeded"
    r = client.post("/v1/workspaces/wa/library/from-job", headers=auth_photo("a"), json={"job_id": job["job_id"], "name": "룩북 영상"})
    assert r.status_code in (200, 201), r.text
    it = r.json()
    assert it["kind"] == "render" and it["asset_id"] == job["output_asset_id"] and it["attrs"]["service"] == "video" and it["name"] in ("룩북 영상", it["name"])
    inputs = client.get("/v1/workspaces/wa/library", headers=auth_photo("a")).json()["items"]
    in_assets = {i["asset_id"] for i in inputs if i["item_id"] in ids}
    assert set(it["attrs"]["source_asset_ids"]) == in_assets, "the video's input pictures are linked"
    again = client.post("/v1/workspaces/wa/library/from-job", headers=auth_photo("a"), json={"job_id": job["job_id"]})
    assert again.status_code == 200 and again.json()["item_id"] == it["item_id"]
    assert sum(1 for i in client.get("/v1/workspaces/wa/library", headers=auth_photo("a")).json()["items"] if i["asset_id"] == job["output_asset_id"]) == 1
    assert client.post("/v1/workspaces/wa/library/from-job", headers=auth_photo("c"), json={"job_id": job["job_id"]}).status_code == 403, "a viewer cannot file"
    assert client.post("/v1/workspaces/wb/library/from-job", headers=auth_photo("b"), json={"job_id": job["job_id"]}).status_code == 404, "another workspace's job"


def test_a_failed_video_is_not_filed(env):
    from tests.test_video_jobs import solid
    job = make({"input_item_ids": [item(solid(), name="flat")], "duration_seconds": 3}).json()
    assert job["status"] == "failed"
    r = client.post("/v1/workspaces/wa/library/from-job", headers=auth_photo("a"), json={"job_id": job["job_id"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "JOB_NOT_FINISHED"
