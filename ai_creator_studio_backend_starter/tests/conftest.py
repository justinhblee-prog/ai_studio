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


@pytest.fixture(autouse=True)
def _far_away_usd_limit(monkeypatch):
    """Real-provider jobs are refused while no monthly USD limit is configured (R-037). The older tests that create paid-provider
    jobs are about other things, so they run with a limit far away; the tests of the money cap set or remove it themselves."""
    monkeypatch.setenv("AI_COST_LIMIT_USD_MONTH", "1000000")


@pytest.fixture(autouse=True)
def _no_external_notice_in_old_tests(monkeypatch):
    """The older tests create real-provider jobs (stubs) without acknowledging the external-transfer notice (R-037); the tests of the
    notice turn the requirement back on themselves."""
    import app.config as config
    monkeypatch.setattr(config, "EXTERNAL_NOTICE_REQUIRED", False)
