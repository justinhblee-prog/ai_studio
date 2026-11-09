"""Pytest plugin that records successful JSON responses during the full suite."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx


_SEEN: list[dict[str, object]] = []
_ORIGINAL_REQUEST = httpx.Client.request


def _capture_request(self, method, url, *args, **kwargs):
    response = _ORIGINAL_REQUEST(self, method, url, *args, **kwargs)
    _SEEN.append({
        "method": str(method).lower(),
        "path": urlsplit(str(url)).path,
        "status": response.status_code,
        "content_type": response.headers.get("content-type", "").split(";", 1)[0].lower(),
    })
    return response


def pytest_configure(config):
    httpx.Client.request = _capture_request


def pytest_unconfigure(config):
    httpx.Client.request = _ORIGINAL_REQUEST


def pytest_sessionfinish(session, exitstatus):
    output = os.environ.get("ACS_VIEWER_RUNTIME_COVERAGE_OUTPUT")
    if output:
        Path(output).write_text(json.dumps(_SEEN, indent=2) + "\n", encoding="utf-8")
