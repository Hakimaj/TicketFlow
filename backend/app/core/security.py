"""Password hashing, JWT access tokens and refresh-token hashing.

Argon2id is used for passwords (argon2-cffi defaults) and HS256 JWTs for
short-lived access tokens. Refresh tokens are opaque random strings; only their
SHA-256 hash is persisted, so a database leak does not expose usable tokens.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import ApiError

#: Minimum length for any account password (bootstrap, intake and admin
#: provisioning all share this one definition).
MIN_PASSWORD_LENGTH = 12

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# A pre-computed hash used to keep failed-login timing closer to a successful
# lookup for unknown emails. It is not a credential.
_DUMMY_HASH = _hasher.hash("ticketflow-dummy-password-not-a-credential")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def burn_password_check(password: str) -> None:
    """Spend comparable time when the account does not exist."""
    verify_password(password, _DUMMY_HASH)


def create_access_token(
    *,
    account_id: uuid.UUID,
    role: str,
    session_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> tuple[str, int]:
    settings = get_settings()
    issued = now or datetime.now(UTC)
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(account_id),
        "role": role,
        "typ": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(issued.timestamp()),
        "exp": int((issued + ttl).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if session_id is not None:
        # Ties the short-lived access token to the refresh-session row so
        # logout/revocation takes effect immediately on protected requests.
        payload["sid"] = str(session_id)
    token = jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={
                "require": ["exp", "iat", "sub", "aud", "iss", "typ"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
            },
        )
    except jwt.PyJWTError as exc:
        raise ApiError(
            status_code=401,
            code="invalid_token",
            message="The session is invalid or has expired.",
        ) from exc


def new_refresh_token(
    session_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, str]:
    """Return a session id and a high-entropy, session-bound refresh token.

    The id prefix lets the server lock the exact session row before rotation.
    That makes concurrent refreshes serialize and lets a replayed *old* token be
    recognized as a mismatch against the current hash, which triggers
    family-wide revocation. Only the full token's SHA-256 hash is persisted.
    """
    sid = session_id or uuid.uuid4()
    return sid, f"{sid}.{secrets.token_urlsafe(48)}"


def refresh_token_session_id(token: str) -> uuid.UUID | None:
    """Extract the session id from a current-format token.

    Tokens issued before this format are still accepted through a hash lookup
    and are upgraded on their next successful rotation.
    """
    prefix, separator, secret = token.partition(".")
    if not separator or not secret:
        return None
    try:
        return uuid.UUID(prefix)
    except (ValueError, TypeError):
        return None


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
