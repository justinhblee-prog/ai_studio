"""Preflight tests only; these never contact FASHN or incur provider charges."""
import pytest

from app import config
from scripts import live_fashn_smoke as smoke


def test_live_smoke_requires_explicit_cost_confirmation(monkeypatch):
    monkeypatch.setattr(config, "FASHN_API_KEY", "")
    monkeypatch.delenv("FASHN_LIVE_TEST_CONFIRM_COST", raising=False)
    with pytest.raises(RuntimeError, match="cost confirmation"):
        smoke.preflight()


def test_live_smoke_requires_api_key_after_cost_confirmation(monkeypatch):
    monkeypatch.setenv("FASHN_LIVE_TEST_CONFIRM_COST", smoke.COST_CONFIRMATION)
    monkeypatch.setattr(config, "FASHN_API_KEY", "")
    with pytest.raises(RuntimeError, match="FASHN_API_KEY"):
        smoke.preflight()


def test_live_smoke_requires_credential_free_https_input_urls(monkeypatch):
    monkeypatch.setenv("FASHN_LIVE_TEST_CONFIRM_COST", smoke.COST_CONFIRMATION)
    monkeypatch.setattr(config, "FASHN_API_KEY", "test-key-not-used")
    monkeypatch.setenv("FASHN_LIVE_TEST_MODEL_IMAGE_URL", "http://example.com/model.png")
    monkeypatch.setenv("FASHN_LIVE_TEST_GARMENT_IMAGE_URL", "https://example.com/garment.png")
    with pytest.raises(ValueError, match="credential-free HTTPS"):
        smoke.preflight()


def test_live_smoke_preflight_accepts_public_https_urls(monkeypatch):
    monkeypatch.setenv("FASHN_LIVE_TEST_CONFIRM_COST", smoke.COST_CONFIRMATION)
    monkeypatch.setattr(config, "FASHN_API_KEY", "test-key-not-used")
    monkeypatch.setenv("FASHN_LIVE_TEST_MODEL", "tryon-v1.6")
    monkeypatch.setenv("FASHN_LIVE_TEST_MODEL_IMAGE_URL", "https://assets.example.org/model.png?sig=redacted")
    monkeypatch.setenv("FASHN_LIVE_TEST_GARMENT_IMAGE_URL", "https://assets.example.org/garment.png?sig=redacted")
    assert smoke.preflight() == (
        "tryon-v1.6",
        "https://assets.example.org/model.png?sig=redacted",
        "https://assets.example.org/garment.png?sig=redacted",
    )
