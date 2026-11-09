"""D2 x purge: confirmation rows must not outlive an account deletion (30-day deletion decision)."""
import pytest

from test_purge_requests import env, request, run, orphans, client, auth  # noqa: F401  (reuse the purge fixture)
from io import BytesIO
from PIL import Image


def _confirmed_upload(user, ws):
    buf = BytesIO(); Image.new("RGB", (16, 16), (9, 9, 9)).save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=auth(user), data={"workspace_id": ws, "rights_confirmed": "true"},
                    files={"file": ("c.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def test_account_purge_leaves_no_rights_rows_for_the_deleted_user(env):
    tmp, db, out = env
    a_own = _confirmed_upload("a", "pa")       # deleted with the sole workspace
    a_shared = _confirmed_upload("a", "sh")    # workspace survives (user-b stays)
    b_own = _confirmed_upload("b", "pb")
    db.execute("UPDATE workspace_members SET role='owner' WHERE workspace_id='sh' AND user_id='user-b'")
    assert db.execute("SELECT COUNT(*) FROM upload_rights_confirmations").fetchone()[0] == 3
    rid = request(db, "user-a", "account")
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert orphans(db) == []
    assert db.execute("SELECT COUNT(*) FROM upload_rights_confirmations WHERE user_id='user-a'").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM upload_rights_confirmations WHERE asset_id=? AND user_id='deleted-user'", (a_shared,)).fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM upload_rights_confirmations WHERE asset_id=?", (a_own,)).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM upload_rights_confirmations WHERE user_id='user-b'").fetchone()[0] == 1


def test_workspace_content_purge_removes_rights_rows_of_that_workspace_only(env):
    tmp, db, out = env
    in_pa = _confirmed_upload("a", "pa")
    in_sh = _confirmed_upload("a", "sh")
    rid = request(db, "user-a", "workspace_content", ws="pa")
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert orphans(db) == []
    assert db.execute("SELECT COUNT(*) FROM upload_rights_confirmations WHERE asset_id=?", (in_pa,)).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM upload_rights_confirmations WHERE asset_id=?", (in_sh,)).fetchone()[0] == 1
