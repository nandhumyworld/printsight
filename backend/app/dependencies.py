"""Shared FastAPI dependencies.

Phase 1 only exposes the typed ``DbSession`` alias and an auth stub so that
other modules can import a stable symbol. The real auth dependencies land in
Phase 2 inside ``app.auth.deps``.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

# Typed alias other modules can import for DB-backed endpoints.
DbSession = Annotated[Session, Depends(get_db)]


async def get_current_user_stub() -> None:
    """Placeholder auth dependency — replaced in Phase 2."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Auth not yet implemented - Phase 2 work",
    )
