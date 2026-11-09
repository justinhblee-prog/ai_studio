"""Test-suite defaults.

Image uploads require a rights declaration by default (D2). The older tests upload images without one, so the suite
runs in the legacy mode unless a test opts in (the rights tests set ASSET_REQUIRE_RIGHTS_CONFIRMATION themselves).
The real default is checked in tests/test_upload_rights_acceptance.py by reading a fresh interpreter's config.
"""
import pytest


@pytest.fixture(autouse=True)
def _legacy_rights_mode(monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", False)
