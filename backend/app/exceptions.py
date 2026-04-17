"""Custom exception hierarchy for PrintSight.

These exceptions are translated to HTTP responses by handlers registered in
``app.main``. Services and routers should raise these instead of
``HTTPException`` whenever a domain error (not found, conflict, forbidden,
validation) occurs.
"""


class PrintSightError(Exception):
    """Base exception for PrintSight."""


class NotFoundError(PrintSightError):
    """Resource not found."""


class ConflictError(PrintSightError):
    """Resource conflict (e.g., duplicate)."""


class ForbiddenError(PrintSightError):
    """User not authorized for this action."""


class ValidationError(PrintSightError):
    """Validation failed."""


class AuthenticationError(PrintSightError):
    """Authentication failed."""
