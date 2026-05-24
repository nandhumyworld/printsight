"""X-API-Key dependency for headless ingest endpoints."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_ingest_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Validate the inbound X-API-Key header against settings.ingest_api_key.

    - 503 if no key is configured server-side (refuse to silently allow).
    - 401 if the header is missing or does not match.
    """
    configured = get_settings().ingest_api_key
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "error_code": "INTERNAL",
                "message": "Ingest API key is not configured on the server",
                "details": [],
            },
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'ApiKey realm="ingest"'},
            detail={
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Invalid or missing X-API-Key header",
                "details": [],
            },
        )
