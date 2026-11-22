"""B-22: the FASHN adapter's request building, polling and error mapping, tested OFFLINE: every HTTP answer is faked (httpx.MockTransport), no network and no paid call.
(The one real call lives in test_live_fashn_smoke.py and is opt-in.)"""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from app import config
from app.providers import fashn
from app.providers.base import ProviderAdapterError

REAL_CLIENT = httpx.AsyncClient


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setattr(config, "FASHN_API_KEY", "offline-test-value")          # a fake value: nothing is sent anywhere
    seen = []

    def install(handler):
        def fake_client(**kwargs):
            return REAL_CLIENT(transport=httpx.MockTransport(lambda request: (seen.append(request), handler(request))[1]), **kwargs)
        monkeypatch.setattr(fashn.httpx, "AsyncClient", fake_client)
        return seen
    return install


def run(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------------------------------------- Retry-After
def test_retry_after_accepts_seconds_dates_and_ignores_garbage():
    assert fashn._retry_after_seconds(None) is None and fashn._retry_after_seconds("") is None
    assert fashn._retry_after_seconds(" 7 ") == 7.0 and fashn._retry_after_seconds("-5") == 0.0
    future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=60), usegmt=True)
    assert 50 < fashn._retry_after_seconds(future) <= 60
    assert fashn._retry_after_seconds(format_datetime(datetime.now(timezone.utc) - timedelta(seconds=30), usegmt=True)) == 0.0, "a date in the past is zero, never negative"
    naive = (datetime.now(timezone.utc) + timedelta(seconds=40)).strftime("%a, %d %b %Y %H:%M:%S -0000")
    assert fashn._retry_after_seconds(naive) is not None
    assert fashn._retry_after_seconds("soon") is None


@pytest.mark.parametrize("status, code, retryable", [(429, "PROVIDER_RATE_LIMITED", True), (500, "PROVIDER_POLL_HTTP_ERROR", True), (503, "PROVIDER_POLL_HTTP_ERROR", True),
                                                      (404, "PROVIDER_POLL_HTTP_ERROR", False), (401, "PROVIDER_POLL_HTTP_ERROR", False)])
def test_polling_http_errors_are_mapped_with_retryability_and_retry_after(adapter, status, code, retryable):
    adapter(lambda request: httpx.Response(status, headers={"Retry-After": "12"}, json={"error": "x"}))
    with pytest.raises(ProviderAdapterError) as exc:
        run(fashn.FashnProvider().status("abc"))
    assert exc.value.code == code and exc.value.retryable is retryable and exc.value.retry_after_seconds == 12.0


# ---------------------------------------------------------------------------------------------------------- construction and request bodies
def test_construction_needs_a_key_and_a_known_model(monkeypatch):
    monkeypatch.setattr(config, "FASHN_API_KEY", "")
    with pytest.raises(RuntimeError, match="not configured"):
        fashn.FashnProvider()
    monkeypatch.setattr(config, "FASHN_API_KEY", "offline-test-value")
    with pytest.raises(RuntimeError, match="tryon-v1.6 or tryon-max"):
        fashn.FashnProvider("something-else")
    assert fashn.FashnProvider(" TRYON-MAX ").model == "tryon-max", "the model name is trimmed and lower-cased"
    assert fashn.FashnProvider().describe_capabilities() == ["TRY_ON_IMAGE"] and fashn.FashnProvider.supports_idempotency is False


def test_both_images_are_required(monkeypatch):
    monkeypatch.setattr(config, "FASHN_API_KEY", "offline-test-value")
    provider = fashn.FashnProvider("tryon-v1.6")
    for payload in ({}, {"model_image_url": "a"}, {"garment_image_url": "b"}):
        with pytest.raises(ValueError):
            provider.validate_request(payload)
    provider.validate_request({"model_image_url": "a", "garment_image_url": "b"})


def test_request_bodies_for_the_two_models(monkeypatch):
    monkeypatch.setattr(config, "FASHN_API_KEY", "offline-test-value")
    base = {"model_image_url": "https://x/m.png", "garment_image_url": "https://x/g.png"}
    max_body = fashn.FashnProvider("tryon-max").build_request({**base, "mode": "performance", "prompt": "red", "resolution": "1k"})
    assert max_body == {"model_name": "tryon-max", "inputs": {"model_image": base["model_image_url"], "product_image": base["garment_image_url"], "generation_mode": "fast",
                                                              "resolution": "1k", "output_format": "png", "num_images": 1, "prompt": "red"}}
    assert fashn.FashnProvider("tryon-max").build_request(base)["inputs"]["generation_mode"] == "balanced" and "prompt" not in fashn.FashnProvider("tryon-max").build_request(base)["inputs"]
    v16 = fashn.FashnProvider("tryon-v1.6").build_request({**base, "category": "outerwear"})
    assert v16["inputs"]["category"] == "auto" and v16["inputs"]["garment_image"] == base["garment_image_url"] and "resolution" not in v16["inputs"]
    assert fashn.FashnProvider("tryon-v1.6").build_request({**base, "category": "tops"})["inputs"]["category"] == "tops"


# ---------------------------------------------------------------------------------------------------------- start
def test_start_posts_the_body_with_the_bearer_key_and_returns_the_request_id(adapter):
    seen = adapter(lambda request: httpx.Response(200, json={"id": "pred_1"}))
    result = run(fashn.FashnProvider("tryon-v1.6").start({"model_image_url": "https://x/m.png", "garment_image_url": "https://x/g.png"}))
    assert result == {"request_id": "pred_1", "status": "running"}
    request = seen[0]
    assert request.method == "POST" and request.url.path == "/v1/run" and request.headers["Authorization"] == "Bearer offline-test-value"
    assert b'"model_name":"tryon-v1.6"' in request.content.replace(b" ", b"")


@pytest.mark.parametrize("answer, message", [({"error": "bad"}, "rejected"), ({}, "request id"), ({"id": ""}, "request id")])
def test_start_refuses_a_rejection_or_an_answer_without_an_id(adapter, answer, message):
    adapter(lambda request: httpx.Response(200, json=answer))
    with pytest.raises(RuntimeError, match=message):
        run(fashn.FashnProvider("tryon-v1.6").start({"model_image_url": "a", "garment_image_url": "b"}))


def test_start_passes_an_http_error_up_so_the_worker_marks_it_unknown_never_replays(adapter):
    adapter(lambda request: httpx.Response(500, json={}))
    with pytest.raises(httpx.HTTPStatusError):
        run(fashn.FashnProvider("tryon-v1.6").start({"model_image_url": "a", "garment_image_url": "b"}))


# ---------------------------------------------------------------------------------------------------------- status
@pytest.mark.parametrize("answer, mapped, url, has_message", [
    ({"status": "completed", "output": ["https://x/out.png"]}, "succeeded", "https://x/out.png", False),
    ({"status": "Succeeded", "outputs": [{"url": "https://x/o2.png"}]}, "succeeded", "https://x/o2.png", False),
    ({"status": "success", "output": []}, "failed", None, True),
    ({"status": "failed"}, "failed", None, True),
    ({"status": "cancelled"}, "failed", None, True),
    ({"status": "processing"}, "running", None, False),
    ({}, "running", None, False)])
def test_status_is_mapped_to_the_common_vocabulary(adapter, answer, mapped, url, has_message):
    seen = adapter(lambda request: httpx.Response(200, headers={"Retry-After": "3"}, json=answer))
    result = run(fashn.FashnProvider("tryon-v1.6").status("pred_9"))
    assert result["status"] == mapped and result["output_url"] == url and bool(result["message"]) is has_message and result["retry_after_seconds"] == 3.0
    assert seen[0].url.path == "/v1/status/pred_9" and seen[0].headers["Authorization"] == "Bearer offline-test-value"
