"""Application configuration for PrintSight.

Centralises environment-driven settings behind a Pydantic ``BaseSettings``
object. All modules import ``settings`` from here — never read environment
variables directly elsewhere.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_env_file = Path(__file__).parents[2] / ".env"


class Settings(BaseSettings):
    """Typed application settings loaded from environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=str(_env_file) if _env_file.exists() else None,
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_name: str = "PrintSight"
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql://printsight:password@localhost:5432/printsight"

    # Auth
    secret_key: str = "change-me-in-production-256-bit-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    emails_from_name: str = "PrintSight"

    # Telegram
    telegram_bot_token: str = ""

    # CORS
    allowed_origins: str = "http://localhost:5173"

    # Upload
    max_csv_upload_size_mb: int = 10

    @property
    def cors_origins(self) -> list[str]:
        """Return the configured CORS origins as a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()


settings = get_settings()
