"""Typed, centralized application configuration.

All settings come from environment variables (optionally loaded from
``backend/.env``). Nothing secret is committed; see ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Local development defaults. These are intentionally non-secret placeholders,
# but production must never silently inherit them.
DEV_DATABASE_URL = (
    "postgresql+psycopg://ticketflow:ticketflow_local_dev_only"
    "@127.0.0.1:5432/ticketflow"
)
DEV_CORS_ORIGINS = "http://localhost:5173"


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

    database_url: str = DEV_DATABASE_URL
    database_echo: bool = False
    database_connect_timeout_seconds: int = 5

    # --- Authentication (Phase 8) -------------------------------------
    # No default secret: production-like environments must supply a strong
    # value. Tests set a fixed secret before importing Settings.
    jwt_secret: str = ""
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "ticketflow"
    jwt_audience: str = "ticketflow-web"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    refresh_cookie_name: str = "ticketflow_refresh"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    login_max_attempts: int = 5
    login_window_seconds: int = 300
    # Explicit, environment-provided bootstrap credentials. Never defaults.
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    # Development-only demo accounts are created only when this is true.
    demo_accounts_enabled: bool = False

    # Comma-separated browser origins. Restrictive by default; "*" is rejected
    # so a misconfiguration cannot silently allow arbitrary origins.
    cors_origins: str = DEV_CORS_ORIGINS

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

    @model_validator(mode="after")
    def _validate_auth_settings(self) -> "Settings":
        secret = self.jwt_secret.strip()
        if not secret:
            if self.app_env != "test":
                raise ValueError(
                    "JWT_SECRET is required. Provide a random value of at least "
                    "32 characters (see .env.example)."
                )
            secret = "test-only-jwt-secret-not-for-production-0000"
            self.jwt_secret = secret
        elif len(secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long.")
        if self.access_token_ttl_minutes < 1 or self.access_token_ttl_minutes > 120:
            raise ValueError(
                "ACCESS_TOKEN_TTL_MINUTES must be between 1 and 120."
            )
        if self.refresh_token_ttl_days < 1 or self.refresh_token_ttl_days > 90:
            raise ValueError("REFRESH_TOKEN_TTL_DAYS must be between 1 and 90.")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError(
                "COOKIE_SAMESITE=none requires COOKIE_SECURE=true; browsers "
                "reject insecure SameSite=None cookies."
            )
        if self.app_env == "production":
            # Production must opt in explicitly instead of inheriting any
            # development convenience from the defaults or template.
            if not self.cookie_secure:
                raise ValueError(
                    "COOKIE_SECURE must be true in production; the refresh "
                    "cookie must never travel over plain HTTP."
                )
            if self.demo_accounts_enabled:
                raise ValueError(
                    "DEMO_ACCOUNTS_ENABLED must be false in production."
                )
            if self.database_url == DEV_DATABASE_URL:
                raise ValueError(
                    "DATABASE_URL must be set explicitly in production; the "
                    "local development default is not allowed."
                )
            insecure_origins = [
                origin
                for origin in self.cors_origin_list
                if not origin.startswith("https://")
            ]
            if insecure_origins:
                raise ValueError(
                    "CORS_ORIGINS must contain only https:// origins in "
                    "production (found: "
                    + ", ".join(insecure_origins)
                    + ")."
                )
            if secret.startswith(("test-only-", "replace-with-", "e2e-only-")):
                raise ValueError(
                    "JWT_SECRET still looks like a test/example value; "
                    "generate a production secret."
                )
        return self

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor; tests can call ``get_settings.cache_clear()``."""
    return Settings()
