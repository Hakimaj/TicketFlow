"""Typed, centralized application configuration.

All settings come from environment variables (optionally loaded from
``backend/.env``). Nothing secret is committed; see ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the TicketFlow API.

    Validation happens at startup: an invalid database URL or a wildcard CORS
    origin fails fast instead of surfacing later as a confusing runtime error.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "TicketFlow API"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "production"] = "development"

    api_v1_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+psycopg://ticketflow:ticketflow_local_dev_only"
        "@localhost:5432/ticketflow"
    )
    database_echo: bool = False
    database_connect_timeout_seconds: int = 5

    # Comma-separated browser origins. Restrictive by default; "*" is rejected
    # so a misconfiguration cannot silently allow arbitrary origins.
    cors_origins: str = "http://localhost:5173"

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("DATABASE_URL must not be empty.")
        if not value.startswith(("postgresql+psycopg://", "postgresql://")):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL "
                "(expected postgresql+psycopg://...)."
            )
        return value

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must list at least one origin.")
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS must not contain '*'; list explicit origins."
            )
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        """Configured origins, cleaned and de-duplicated (order preserved)."""
        seen: dict[str, None] = {}
        for origin in self.cors_origins.split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned:
                seen.setdefault(cleaned, None)
        return list(seen)

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor; tests can call ``get_settings.cache_clear()``."""
    return Settings()
