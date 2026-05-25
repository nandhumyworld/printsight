"""Tests for the X-API-Key ingest auth dependency."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.auth.api_key import require_ingest_api_key
from app.config import get_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Ensure each test sees fresh Settings (and doesn't leak the override)."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mini_app():
    app = FastAPI()

    @app.get("/protected")
    def protected(_: None = Depends(require_ingest_api_key)):
        return {"ok": True}

    return app


def test_rejects_missing_header(mini_app, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "configured")
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected")
    assert r.status_code == 401
    assert r.json()["detail"]["error_code"] == "UNAUTHORIZED"


def test_rejects_wrong_header(mini_app, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "configured")
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_accepts_correct_header(mini_app, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "configured")
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected", headers={"X-API-Key": "configured"})
    assert r.status_code == 200


def test_rejects_empty_header(mini_app, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "configured")
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected", headers={"X-API-Key": ""})
    assert r.status_code == 401


def test_503_when_server_not_configured(mini_app, monkeypatch):
    # Use empty string (env vars take precedence over .env file values in
    # pydantic-settings, so this masks any INGEST_API_KEY in the repo .env).
    monkeypatch.setenv("INGEST_API_KEY", "")
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected", headers={"X-API-Key": "anything"})
    assert r.status_code == 503
    assert r.json()["detail"]["error_code"] == "INTERNAL"


def test_401_includes_www_authenticate_header(mini_app, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "configured")
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers
    assert "ApiKey" in r.headers["WWW-Authenticate"]
