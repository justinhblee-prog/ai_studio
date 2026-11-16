"""R-072: the error-code text table: complete against the source, both languages, legal wording left empty, public endpoint, document up to date, real answers use catalogued codes."""
import io
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, error_catalog as ec
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import error_codes_scan  # noqa: E402
import generate_error_codes_doc  # noqa: E402

client = TestClient(app)
HANGUL = re.compile(r"[가-힣]")
LEGAL = {"EXTERNAL_NOTICE_REQUIRED", "LEGAL_ACCEPTANCE_REQUIRED", "TAKEDOWN_ACTIVE", "ASSET_UNDER_REVIEW", "LIBRARY_RIGHTS_NOT_CONFIRMED", "RIGHTS_CONFIRMATION_REQUIRED", "MARKET_RIGHTS_REQUIRED",
         "MARKET_LICENSE_REQUIRED"}


def test_every_code_the_server_can_send_has_an_entry():
    found = error_codes_scan.scan()
    assert len(found) >= 150, "the scan itself still finds the codes"
    missing = {c: w for c, w in found.items() if c not in ec.CODES}
    assert not missing, f"codes without a text in app/error_catalog.py: {missing}"
    assert all(c in ec.CODES for c in ec.EXTRA_CODES)


def test_both_languages_are_written_and_are_really_in_their_language():
    for code, text in ec.CODES.items():
        if text is None:
            continue
        ko, en = text
        assert ko.strip() and en.strip(), code
        assert HANGUL.search(ko), f"{code}: the Korean text has no Korean"
        assert not HANGUL.search(en), f"{code}: the English text contains Korean"
        for t in (ko, en):
            assert "TODO" not in t and "None" not in t and code not in t and len(t) < 160, (code, t)
        assert en[0].isupper() and en.rstrip().endswith((".", ")")), f"{code}: English sentence form"


def test_legal_wording_is_left_empty_on_purpose_and_nothing_else_is():
    assert set(ec.NEEDS_DECISION) == LEGAL
    for code in LEGAL:
        assert ec.CODES[code] is None
    for lang in ("ko", "en"):
        cat = ec.catalog(lang)["codes"]
        for code in LEGAL:
            assert cat[code]["message"] is None and cat[code]["needs_decision"] is True
        assert all(v["message"] and not v["needs_decision"] for c, v in cat.items() if c not in LEGAL)


def test_the_http_fallbacks_cover_the_statuses_the_server_uses():
    assert {"401", "403", "404", "409", "413", "422", "429", "500", "503"} <= set(ec.HTTP)
    for ko, en in ec.HTTP.values():
        assert HANGUL.search(ko) and not HANGUL.search(en)


def test_the_endpoint_is_public_serves_both_languages_and_defaults_to_korean():
    ko = client.get("/v1/error-catalog")
    assert ko.status_code == 200 and ko.headers["cache-control"] == "public, max-age=300", "no sign-in needed"
    assert ko.json() == client.get("/v1/error-catalog", params={"lang": "ko"}).json()
    en = client.get("/v1/error-catalog", params={"lang": "en"}).json()
    kj = ko.json()
    assert kj["lang"] == "ko" and en["lang"] == "en" and kj["version"] == en["version"] == ec.VERSION
    assert set(kj["codes"]) == set(en["codes"]) == set(ec.CODES)
    assert kj["codes"]["RATE_LIMITED"]["kind"] == "limit" and kj["codes"]["RATE_LIMITED"]["area"] == "general" and kj["codes"]["MARKET_PRICE_INVALID"]["area"] == "market"
    assert HANGUL.search(kj["codes"]["REVIEW_NOT_APPROVED"]["message"]) and not HANGUL.search(en["codes"]["REVIEW_NOT_APPROVED"]["message"])
    assert kj["http"]["429"] and en["http"]["401"] and "법무" in kj["note"] and "legal" in en["note"].lower()
    assert client.get("/v1/error-catalog", params={"lang": "fr"}).status_code == 422


def test_the_document_is_up_to_date_with_the_table():
    assert generate_error_codes_doc.main(["--check"]) == 0, "run: python scripts/generate_error_codes_doc.py"
    text = generate_error_codes_doc.DOC.read_text(encoding="utf-8")
    assert all(f"`{c}`" in text for c in ec.CODES) and text.count("[결정 필요: 법무]") >= len(LEGAL)


def png(shade=1):
    buf = io.BytesIO(); Image.new("RGB", (10, 10), (shade, shade, shade)).save(buf, format="PNG"); return buf.getvalue()


def test_real_answers_use_catalogued_codes(env, monkeypatch):
    """A sample of real refusals from different parts of the server: every code in them is in the table."""
    seen = []

    def code_of(r):
        d = r.json().get("detail")
        if isinstance(d, dict) and "code" in d:
            seen.append(d["code"])
            assert d["code"] in ec.CODES, d
        return r

    code_of(client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": ("x.png", b"not a picture", "image/png")}))
    code_of(client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": ("x.jpg", png(), "image/jpeg")}))
    code_of(client.post("/v1/workspaces/wa/work-items", headers=auth("a"), json={"kind": "BAD", "title": "t"}))
    code_of(client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "model", "name": " ", "rights_confirmed": "true"}, files={"file": ("a.png", png(), "image/png")}))
    code_of(client.post("/v1/market/listings", headers=auth("a"), json={"workspace_id": "wa", "kind": "preset", "title": "t", "license_scope": "x", "is_ai_generated": False, "rights_confirmed": True, "price": -1}))
    code_of(client.post("/v1/workspaces/wa/reviews", headers=auth("a"), json={"asset_id": env["asset"]}))
    code_of(client.get("/internal/ops/audit", headers=auth("a"), params={"from": "x"}))
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", frozenset({"user-a"}))
    code_of(client.get("/internal/ops/audit", headers=auth("a"), params={"from": "soon"}))
    code_of(client.get("/internal/ops/audit", headers=auth("a"), params={"offset": 900, "limit": 200}))
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", True)
    monkeypatch.setattr(config, "RATE_UPLOAD_USER_PER_MINUTE", 1)
    for shade in (1, 2, 3):
        code_of(client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": ("a.png", png(shade + 5), "image/png")}))
    assert {"IMAGE_DECODE_FAILED", "RATE_LIMITED"} <= set(seen) and len(set(seen)) >= 4, seen
