"""FastAPI dependencies: request-scoped DB session and authentication."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import decode_access_token
from app.models.auth import UserAccount
from app.models.common import utcnow
from app.repositories import auth as auth_repo
from app.services.auth import permissions_for


def get_db(request: Request) -> Iterator[Session]:
    """Yield a request-scoped session and always close it."""
    session_factory = request.app.state.session_factory
    db: Session = session_factory()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


def _resolve_bearer(
    db: Session, credentials: HTTPAuthorizationCredentials | None
) -> UserAccount:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=401,
            code="not_authenticated",
            message="Authentication required.",
        )
    claims = decode_access_token(credentials.credentials)
    if claims.get("typ") != "access":
        raise ApiError(
            status_code=401,
            code="invalid_token",
            message="The session is invalid or has expired.",
        )
    try:
        account_id = uuid.UUID(str(claims.get("sub")))
    except (ValueError, TypeError) as exc:
        raise ApiError(
            status_code=401,
            code="invalid_token",
            message="The session is invalid or has expired.",
        ) from exc

    account = auth_repo.get_user_by_id(db, account_id)
    if account is None or not account.is_active:
        raise ApiError(
            status_code=401,
            code="invalid_token",
            message="The session is invalid or has expired.",
        )

    # Access tokens issued in this application carry their refresh-session id.
    # Checking it here makes logout and replay-triggered family revocation take
    # effect immediately instead of waiting for the access-token TTL. Tokens
    # minted directly by tests/older builds without `sid` are still bounded by
    # their own expiry.
    session_claim = claims.get("sid")
    if session_claim is not None:
        try:
            session_id = uuid.UUID(str(session_claim))
        except (ValueError, TypeError) as exc:
            raise ApiError(
                status_code=401,
                code="invalid_token",
                message="The session is invalid or has expired.",
            ) from exc
        refresh_session = auth_repo.get_session_by_id(db, session_id)
        if (
            refresh_session is None
            or refresh_session.user_id != account_id
            or refresh_session.revoked_at is not None
            or refresh_session.expires_at <= utcnow()
        ):
            raise ApiError(
                status_code=401,
                code="invalid_token",
                message="The session is invalid or has expired.",
            )

    # Role always comes from the database, never from the token or client.
    return account


def get_current_account(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> UserAccount:
    return _resolve_bearer(db, credentials)


def get_optional_account(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> UserAccount | None:
    if credentials is None:
        return None
    try:
        return _resolve_bearer(db, credentials)
    except ApiError:
        # Logout must still work with an expired access token as long as the
        # refresh cookie is present.
        return None


def get_password_current_account(account: CurrentAccount) -> UserAccount:
    """Reject accounts that still use an administrator-issued password.

    Applied to every operational router. ``/auth/*`` is registered separately,
    so such an account can still read its profile, change the password and log
    out. The flag is read from PostgreSQL, never from the token.
    """
    if account.must_change_password:
        raise ApiError(
            status_code=403,
            code="password_change_required",
            message=(
                "Set a new password before using the workspace. "
                "See POST /api/v1/auth/password."
            ),
        )
    return account


CurrentAccount = Annotated[UserAccount, Depends(get_current_account)]
PasswordCurrentAccount = Annotated[
    UserAccount, Depends(get_password_current_account)
]
OptionalAccount = Annotated[
    UserAccount | None, Depends(get_optional_account)
]


def require_permission(permission: str):
    """Dependency factory enforcing a server-side permission."""

    def _dependency(account: CurrentAccount) -> UserAccount:
        if permission not in permissions_for(account.role):
            raise ApiError(
                status_code=403,
                code="forbidden",
                message="You do not have permission to perform this action.",
            )
        return account

    return _dependency
