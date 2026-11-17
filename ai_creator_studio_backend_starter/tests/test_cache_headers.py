"""B-17: cache headers of the picture / preview paths. A signed address is a bearer token, so what it returns must not be kept by shared caches
and the private copy must not outlive the address by much: thumbnails ``private`` with a short max-age, full previews ``no-store``; both ``nosniff``."""
import re
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from app.main import app
from tests.test_image_thumbs import png, upload
from tests.test_photo_steps_api import auth, env  # noqa: F401

client = TestClient(app)
SIGNED_URL_LIFETIME = 900     # seconds: the server refuses addresses expiring later than now+901


def _directives(response) -> set[str]:
    return {d.strip().lower() for d in response.headers.get("cache-control", "").split(",") if d.strip()}


def test_thumbnail_is_private_short_lived_and_not_sniffable(env):
    r = upload(png((900, 600)), "c.png").json()
    got = client.get(r["thumbs"]["480"])
    assert got.status_code == 200
    d = _directives(got)
    assert "private" in d and "public" not in d and "no-store" not in d
    max_age = [int(m.group(1)) for x in d if (m := re.fullmatch(r"max-age=(\d+)", x))]
    assert max_age and 0 < max_age[0] <= 300 and max_age[0] < SIGNED_URL_LIFETIME
    assert got.headers["x-content-type-options"] == "nosniff"
    assert got.headers["content-type"] == "image/webp"


def test_full_preview_is_never_stored(env):
    asset_id = upload(png((900, 600)), "p.png").json()["asset_id"]
    link = client.post(f"/v1/assets/{asset_id}/preview-url", headers=auth("a"))
    assert link.status_code == 200
    u = urlsplit(link.json()["url"])
    got = client.get(u.path + "?" + u.query)
    assert got.status_code == 200
    d = _directives(got)
    assert "no-store" in d and "private" in d and "public" not in d
    assert got.headers["x-content-type-options"] == "nosniff"


def test_refused_signed_addresses_carry_no_cacheable_picture(env):
    r = upload(png((900, 600)), "e.png").json()
    bad = client.get(f"/v1/assets/{r['asset_id']}/thumb/480?expires=1&signature={'0' * 64}")
    assert bad.status_code == 403
    assert "public" not in _directives(bad) and "max-age" not in bad.headers.get("cache-control", "")
