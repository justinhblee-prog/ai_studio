"""B-08: deleting an asset twice or from many requests at once. Exactly one call removes it (204), every other call is a clean 404 (never a 500),
the stored file is gone, and a re-upload of the same bytes afterwards works."""
from concurrent.futures import ThreadPoolExecutor

from tests.test_assets_api import asset_env, auth, client, glb_bytes, upload  # noqa: F401


def delete(asset_id):
    return client.delete(f"/v1/assets/{asset_id}", headers=auth())


def test_a_second_delete_is_404_not_an_error(asset_env):
    asset_id = upload().json()["asset_id"]
    assert delete(asset_id).status_code == 204
    assert delete(asset_id).status_code == 404
    assert client.get(f"/v1/assets/{asset_id}", headers=auth()).status_code == 404
    assert list((asset_env / "private").glob(f"{asset_id}.*")) == []


def test_simultaneous_deletes_have_exactly_one_winner(asset_env):
    asset_id = upload().json()["asset_id"]
    with ThreadPoolExecutor(8) as pool:
        codes = sorted(r.status_code for r in pool.map(lambda _: delete(asset_id), range(8)))
    assert codes == [204] + [404] * 7, codes
    assert client.get("/v1/assets?workspace_id=ws-a", headers=auth()).json()["items"] == []


def test_deleting_while_others_list_and_upload_never_errors(asset_env):
    ids = [upload().json()["asset_id"] for _ in range(4)]

    def work(i):
        if i < 4:
            return delete(ids[i]).status_code
        if i < 8:
            return client.get("/v1/assets?workspace_id=ws-a", headers=auth()).status_code
        return upload().status_code
    with ThreadPoolExecutor(10) as pool:
        codes = list(pool.map(work, range(10)))
    assert all(c < 500 for c in codes), codes
    assert codes[:4] == [204] * 4
    left = client.get("/v1/assets?workspace_id=ws-a", headers=auth()).json()["items"]
    assert {a["asset_id"] for a in left}.isdisjoint(ids)


def test_the_same_bytes_can_be_uploaded_again_after_a_delete(asset_env):
    first = upload().json()["asset_id"]
    assert delete(first).status_code == 204
    again = upload()
    assert again.status_code == 201 and again.json()["asset_id"] != first
