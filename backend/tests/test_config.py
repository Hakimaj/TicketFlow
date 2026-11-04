"""Production configuration guards.

These tests pin the fail-fast rules in ``app.core.config``: a misconfigured
deployment must refuse to start rather than silently serving over plain HTTP,
seeding demo accounts or signing tokens with a placeholder secret.

No real credential appears here. The values only satisfy (or deliberately
violate) the length and format rules.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import DEV_DATABASE_URL, Settings

STRONG_SECRET = "s" * 48
PRODUCTION_DATABASE_URL = (
    "postgresql+psycopg://app:local-placeholder@db.internal:5432/ticketflow"
)


def _settings(**overrides) -> Settings:
    """Build Settings from explicit values, ignoring the local ``.env`` file."""
    return Settings(_env_file=None, **overrides)


def _production(**overrides) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "jwt_secret": STRONG_SECRET,
        "database_url": PRODUCTION_DATABASE_URL,
        "cookie_secure": True,
        "cors_origins": "https://support.example.com",
        "demo_accounts_enabled": False,
    }
    values.update(overrides)
    return _settings(**values)


def test_valid_production_configuration_is_accepted() -> None:
    settings = _production()

    assert settings.app_env == "production"
    assert settings.cors_origin_list == ["https://support.example.com"]
    assert settings.is_test is False


def test_signing_secret_is_required_outside_tests() -> None:
    with pytest.raises(ValidationError):
        _settings(app_env="development", jwt_secret="")


def test_short_signing_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(app_env="development", jwt_secret="too-short")


def test_placeholder_signing_secret_is_rejected_in_production() -> None:
    for placeholder in (
        "replace-with-a-random-value-of-at-least-32-characters",
        "test-only-jwt-secret-not-for-production-0000",
        "e2e-only-jwt-secret-not-for-production-0000",
    ):
        with pytest.raises(ValidationError):
            _production(jwt_secret=placeholder)


def test_production_requires_secure_cookies() -> None:
    with pytest.raises(ValidationError):
        _production(cookie_secure=False)


def test_samesite_none_requires_secure_cookies() -> None:
    with pytest.raises(ValidationError):
        _settings(
            app_env="development",
            jwt_secret=STRONG_SECRET,
            cookie_samesite="none",
            cookie_secure=False,
        )


def test_production_rejects_demo_accounts() -> None:
    with pytest.raises(ValidationError):
        _production(demo_accounts_enabled=True)


def test_production_rejects_the_local_development_database() -> None:
    with pytest.raises(ValidationError):
        _production(database_url=DEV_DATABASE_URL)


def test_production_requires_https_origins() -> None:
    with pytest.raises(ValidationError):
        _production(
            cors_origins="https://support.example.com,http://localhost:5173"
        )


def test_wildcard_cors_origin_is_rejected_everywhere() -> None:
    for app_env in ("development", "production"):
        with pytest.raises(ValidationError):
            _settings(
                app_env=app_env,
                jwt_secret=STRONG_SECRET,
                cookie_secure=True,
                cors_origins="*",
            )


def test_empty_cors_origin_list_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(
            app_env="development",
            jwt_secret=STRONG_SECRET,
            cors_origins=" , ",
        )


def test_non_postgres_database_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(
            app_env="development",
            jwt_secret=STRONG_SECRET,
            database_url="sqlite:///./ticketflow.db",
        )


@pytest.mark.parametrize("minutes", [0, 121])
def test_access_token_ttl_bounds_are_enforced(minutes: int) -> None:
    with pytest.raises(ValidationError):
        _settings(
            app_env="development",
            jwt_secret=STRONG_SECRET,
            access_token_ttl_minutes=minutes,
        )


@pytest.mark.parametrize("days", [0, 91])
def test_refresh_token_ttl_bounds_are_enforced(days: int) -> None:
    with pytest.raises(ValidationError):
        _settings(
            app_env="development",
            jwt_secret=STRONG_SECRET,
            refresh_token_ttl_days=days,
        )


def test_origin_list_is_cleaned_and_deduplicated() -> None:
    settings = _settings(
        app_env="development",
        jwt_secret=STRONG_SECRET,
        cors_origins="http://localhost:5173/, http://localhost:5173,http://127.0.0.1:5173",
    )

    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_test_environment_may_omit_the_secret() -> None:
    settings = _settings(app_env="test", jwt_secret="")

    assert settings.is_test is True
    assert len(settings.jwt_secret) >= 32
