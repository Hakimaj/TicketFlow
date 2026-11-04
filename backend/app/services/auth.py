"""Authentication service.

Security notes:

- Passwords are verified with Argon2id; unknown emails still perform a password
  check so timing does not obviously reveal account existence.
- Failed logins are rate-limited in process memory (documented limitation; a
  multi-process deployment needs a shared store or edge limiter).
- Refresh tokens are session-bound and rotate on every use. Rotation locks the
  session row; replaying a previous token is treated as compromise and revokes
  every active session for that account. Logout also revokes all sessions.
"""

from __future__ import annotations

import hmac
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_token_session_id,
    verify_password,
)
from app.models.agent import Agent
from app.models.auth import RefreshSession, UserAccount
from app.models.common import utcnow
from app.models.enums import AccountRole
from app.repositories import auth as auth_repo
from app.schemas.auth import (
    AccountProfile,
    AuthResponse,
    LoginRequest,
    PasswordChangeRequest,
)
from app.services.common import transaction

_BASE_PERMISSIONS = (
    "tickets:read",
    "tickets:write",
    "notes:write",
    "replies:write",
    "replies:send",
    "analytics:read",
)
_REVIEW_PERMISSIONS = ("replies:review",)

ROLE_PERMISSIONS: dict[AccountRole, tuple[str, ...]] = {
    AccountRole.AGENT: _BASE_PERMISSIONS,
    AccountRole.REVIEWER: _BASE_PERMISSIONS + _REVIEW_PERMISSIONS,
    AccountRole.ADMIN: _BASE_PERMISSIONS
    + _REVIEW_PERMISSIONS
    + ("accounts:manage",),
}

_failed_logins: dict[str, list[float]] = {}
_failed_lock = threading.Lock()


def _rate_key(email: str, client_key: str) -> str:
    return f"{email.lower()}|{client_key}"


def _check_rate_limit(key: str) -> None:
    settings = get_settings()
    now = time.monotonic()
    with _failed_lock:
        attempts = [
            value
            for value in _failed_logins.get(key, [])
            if now - value < settings.login_window_seconds
        ]
        _failed_logins[key] = attempts
    if len(attempts) >= settings.login_max_attempts:
        raise ApiError(
            status_code=429,
            code="too_many_attempts",
            message="Too many failed sign-in attempts. Try again later.",
        )


def _record_failure(key: str) -> None:
    with _failed_lock:
        _failed_logins.setdefault(key, []).append(time.monotonic())


def _clear_failures(key: str) -> None:
    with _failed_lock:
        _failed_logins.pop(key, None)


def permissions_for(role: AccountRole) -> list[str]:
    return list(ROLE_PERMISSIONS[role])


def to_profile(account: UserAccount) -> AccountProfile:
    return AccountProfile(
        id=str(account.id),
        email=account.email,
        display_name=account.display_name,
        role=account.role,
        agent_id=account.agent_id,
        agent_name=account.agent.name if account.agent else None,
        must_change_password=account.must_change_password,
        permissions=permissions_for(account.role),
    )


def account_agent(account: UserAccount) -> Agent:
    """The linked support agent required for operational attribution."""
    if account.agent is None:
        raise ApiError(
            status_code=403,
            code="agent_profile_required",
            message=(
                "This action requires an account linked to a support agent. "
                "Ask an administrator to link your account."
            ),
        )
    return account.agent


@dataclass(frozen=True)
class Principal:
    """Verified acting identity for one request.

    ``agent`` supplies the historical agent-based attribution used by the
    existing ticket/assignment model; ``account_id`` is the trusted account
    identity written to audit rows.
    """

    account_id: uuid.UUID
    agent: Agent


def principal_for(account: UserAccount) -> Principal:
    """Build the acting principal from the database-backed account."""
    return Principal(account_id=account.id, agent=account_agent(account))


def _auth_response(
    account: UserAccount, session_id: uuid.UUID | None = None
) -> tuple[AuthResponse, str, uuid.UUID]:
    refresh_session_id, refresh_token = new_refresh_token(session_id)
    access_token, expires_in = create_access_token(
        account_id=account.id,
        role=account.role.value,
        session_id=refresh_session_id,
    )
    response = AuthResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=to_profile(account),
    )
    return response, refresh_token, refresh_session_id


def _new_session(
    db: Session,
    account: UserAccount,
    refresh_token: str,
    session_id: uuid.UUID,
) -> None:
    settings = get_settings()
    now = utcnow()
    auth_repo.add_session(
        db,
        user_id=account.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
        session_id=session_id,
    )


def _find_session_for_token(
    db: Session, refresh_token: str, *, for_update: bool = False
) -> tuple[RefreshSession | None, bool]:
    """Return the session row and whether the presented token matches it.

    Current tokens carry a session id, so an old token can be distinguished
    from an unknown token and treated as replay. Legacy opaque tokens fall back
    to a hash lookup and are migrated to the new format on rotation.
    """
    session_id = refresh_token_session_id(refresh_token)
    if session_id is not None:
        session = auth_repo.get_session_by_id(
            db, session_id, for_update=for_update
        )
        if session is None:
            return None, False
        matches = hmac.compare_digest(
            session.token_hash, hash_refresh_token(refresh_token)
        )
        return session, matches

    session = auth_repo.get_session_by_hash(
        db, hash_refresh_token(refresh_token), for_update=for_update
    )
    return session, session is not None


def login(
    db: Session, payload: LoginRequest, *, client_key: str
) -> tuple[AuthResponse, str]:
    key = _rate_key(payload.email, client_key)
    _check_rate_limit(key)

    account = auth_repo.get_user_by_email(db, payload.email)
    if account is None:
        burn_password_check(payload.password)
        _record_failure(key)
        raise ApiError(
            status_code=401,
            code="invalid_credentials",
            message="Invalid email or password.",
        )

    if not verify_password(payload.password, account.password_hash):
        _record_failure(key)
        raise ApiError(
            status_code=401,
            code="invalid_credentials",
            message="Invalid email or password.",
        )

    if not account.is_active:
        # Same generic response as bad credentials: do not reveal account state.
        _record_failure(key)
        raise ApiError(
            status_code=401,
            code="invalid_credentials",
            message="Invalid email or password.",
        )

    _clear_failures(key)
    response, refresh_token, session_id = _auth_response(account)
    with transaction(db):
        _new_session(db, account, refresh_token, session_id)
    return response, refresh_token


def rotate_refresh(
    db: Session, refresh_token: str | None
) -> tuple[AuthResponse, str]:
    if not refresh_token:
        raise ApiError(
            status_code=401,
            code="refresh_invalid",
            message="The session has expired. Sign in again.",
        )
    settings = get_settings()
    now = utcnow()
    reuse_detected = False
    inactive_detected = False
    response: AuthResponse | None = None
    new_token: str | None = None

    # Lock the session row before comparing/rotating. Two simultaneous
    # refreshes serialize; the second sees the rotated hash (a replay) rather
    # than both writing different token hashes.
    with transaction(db):
        session, matches = _find_session_for_token(
            db, refresh_token, for_update=True
        )
        if (
            session is None
            or session.expires_at <= now
            or session.revoked_at is not None
        ):
            raise ApiError(
                status_code=401,
                code="refresh_invalid",
                message="The session has expired. Sign in again.",
            )
        if not session.user.is_active:
            auth_repo.revoke_all_for_user(db, session.user_id, now)
            inactive_detected = True
        elif not matches:
            # A previously rotated token was replayed. Treat the session family
            # as compromised and revoke every active session for this account.
            auth_repo.revoke_all_for_user(db, session.user_id, now)
            reuse_detected = True
        else:
            response, new_token, _ = _auth_response(
                session.user, session_id=session.id
            )
            session.token_hash = hash_refresh_token(new_token)
            session.last_used_at = now
            session.expires_at = now + timedelta(
                days=settings.refresh_token_ttl_days
            )

    if (
        reuse_detected
        or inactive_detected
        or response is None
        or new_token is None
    ):
        raise ApiError(
            status_code=401,
            code="refresh_invalid",
            message="The session has expired. Sign in again.",
        )
    return response, new_token


def logout(
    db: Session,
    *,
    refresh_token: str | None,
    account: UserAccount | None,
) -> None:
    now = utcnow()
    with transaction(db):
        if refresh_token:
            session, matches = _find_session_for_token(db, refresh_token)
            if (
                session is not None
                and matches
                and session.revoked_at is None
            ):
                auth_repo.revoke_session(db, session, now)
        if account is not None:
            auth_repo.revoke_all_for_user(db, account.id, now)


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------


def create_account(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str,
    role: AccountRole,
    agent_id: str | None,
    is_active: bool = True,
    must_change_password: bool = False,
) -> UserAccount:
    account = UserAccount(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
        agent_id=agent_id,
        is_active=is_active,
        must_change_password=must_change_password,
    )
    db.add(account)
    return account


def change_password(
    db: Session, account: UserAccount, payload: PasswordChangeRequest
) -> tuple[AuthResponse, str]:
    """Replace the account's own password.

    The current password is verified with Argon2id, then every existing refresh
    session is revoked and a fresh session is issued, so a password change ends
    other devices' sessions. Used by provisioned accounts to clear the forced
    change before they can use operational endpoints.
    """
    if not verify_password(payload.current_password, account.password_hash):
        raise ApiError(
            status_code=400,
            code="invalid_current_password",
            message="The current password is incorrect.",
        )
    if payload.new_password == payload.current_password:
        raise ApiError(
            status_code=422,
            code="password_unchanged",
            message="Choose a password different from the current one.",
        )

    now = utcnow()
    with transaction(db):
        account.password_hash = hash_password(payload.new_password)
        account.must_change_password = False
        # Build the response after clearing the flag so the returned profile
        # reflects the account's new state.
        response, refresh_token, session_id = _auth_response(account)
        # Revoke before staging the replacement session so the new row (still
        # pending) is not caught by the bulk update.
        auth_repo.revoke_all_for_user(db, account.id, now)
        _new_session(db, account, refresh_token, session_id)
    return response, refresh_token
