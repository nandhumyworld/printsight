"""Tests for the X-API-Key ingest auth dependency."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.auth.api_key import require_ingest_api_key
from app.config import get_settings


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


def test_503_when_server_not_configured(mini_app, monkeypatch):
    monkeypatch.delenv("INGEST_API_KEY", raising=False)
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected", headers={"X-API-Key": "anything"})
    assert r.status_code == 503
    assert r.json()["detail"]["error_code"] == "INTERNAL"
