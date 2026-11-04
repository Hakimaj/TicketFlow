"""Authentication endpoints.

The access token is returned to the client and held in memory. The refresh token
is an opaque random value stored only as a SHA-256 hash in PostgreSQL and sent
to browsers as an HttpOnly cookie scoped to `/api/v1/auth`.

Cookie-authenticated POSTs additionally require `X-Requested-With: ticketflow`
and an allowed `Origin` when one is present. Together with SameSite this blocks
cross-site request forgery; it is not a substitute for TLS in production.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    CurrentAccount,
    DbSession,
    OptionalAccount,
    get_current_account,
)
from app.core.config import get_settings
from app.core.errors import ApiError
from app.schemas.auth import (
    AccountProfile,
    AuthResponse,
    LoginRequest,
    LogoutResponse,
    PasswordChangeRequest,
)
from app.schemas.common import ErrorResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Invalid credentials or session."},
    403: {"model": ErrorResponse, "description": "Origin/CSRF check failed."},
    422: {"model": ErrorResponse, "description": "Invalid request body."},
    429: {"model": ErrorResponse, "description": "Too many failed sign-in attempts."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


def verify_browser_request(request: Request) -> None:
    """CSRF/origin guard for cookie-authenticated POST endpoints."""
    settings = get_settings()
    if request.headers.get("x-requested-with", "").lower() != "ticketflow":
        raise ApiError(
            status_code=403,
            code="csrf_rejected",
            message="The request could not be verified. Refresh and try again.",
        )
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in settings.cors_origin_list:
        raise ApiError(
            status_code=403,
            code="origin_rejected",
            message="The request origin is not allowed.",
        )


BrowserRequest = Annotated[None, Depends(verify_browser_request)]


def _cookie_seconds() -> int:
    return get_settings().refresh_token_ttl_days * 24 * 60 * 60


def _no_store(response: Response) -> None:
    """Prevent browsers/proxies from caching token-bearing responses."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=_cookie_seconds(),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/api/v1/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rejected_refresh_headers() -> dict[str, str]:
    """Headers the browser needs when a refresh cookie is rejected.

    A rejected, expired or replayed cookie is useless, so the browser must be
    told to drop it. Starlette discards headers written to the injected
    ``Response`` once a route raises, so the clearing header is computed here
    and attached to the error response instead.
    """
    scratch = Response()
    _clear_refresh_cookie(scratch)
    headers = {"cache-control": "no-store"}
    cleared = scratch.headers.get("set-cookie")
    if cleared:
        headers["set-cookie"] = cleared
    return headers


@router.post(
    "/login",
    response_model=AuthResponse,
    responses=_ERROR_RESPONSES,
    summary="Sign in",
    description=(
        "Verifies the account credentials with Argon2id and returns a "
        "short-lived access token plus an HttpOnly rotating refresh cookie. "
        "Failures are generic and do not reveal whether the account exists. "
        "Inactive accounts are rejected with the same generic error."
    ),
)
def login(
    request: Request,
    response: Response,
    db: DbSession,
    _: BrowserRequest,
    payload: LoginRequest,
) -> AuthResponse:
    result, refresh_token = auth_service.login(
        db, payload, client_key=_client_key(request)
    )
    _set_refresh_cookie(response, refresh_token)
    _no_store(response)
    return result


@router.post(
    "/refresh",
    response_model=AuthResponse,
    responses=_ERROR_RESPONSES,
    summary="Rotate the refresh session",
    description=(
        "Reads the HttpOnly refresh cookie, validates its stored hash, rotates "
        "it under a row lock (the previous token becomes unusable), and "
        "returns a new access token. Replaying an old token revokes every "
        "active session for the account and clears the cookie."
    ),
)
def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    _: BrowserRequest,
) -> AuthResponse:
    settings = get_settings()
    try:
        result, refresh_token = auth_service.rotate_refresh(
            db, request.cookies.get(settings.refresh_cookie_name)
        )
    except ApiError as exc:
        # A rejected/expired/replayed cookie is useless; clear it so the
        # browser does not keep sending it on every startup.
        exc.headers = _rejected_refresh_headers()
        raise
    _set_refresh_cookie(response, refresh_token)
    _no_store(response)
    return result


@router.post(
    "/logout",
    response_model=LogoutResponse,
    responses=_ERROR_RESPONSES,
    summary="Sign out",
    description=(
        "Revokes the refresh session from the cookie and all active sessions "
        "for the authenticated account, then clears the cookie. Safe to call "
        "with an expired access token."
    ),
)
def logout(
    request: Request,
    response: Response,
    db: DbSession,
    _: BrowserRequest,
    account: OptionalAccount,
) -> LogoutResponse:
    settings = get_settings()
    auth_service.logout(
        db,
        refresh_token=request.cookies.get(settings.refresh_cookie_name),
        account=account,
    )
    _clear_refresh_cookie(response)
    _no_store(response)
    return LogoutResponse()


@router.post(
    "/password",
    response_model=AuthResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "The current password is incorrect.",
        },
        401: _ERROR_RESPONSES[401],
        403: _ERROR_RESPONSES[403],
        422: _ERROR_RESPONSES[422],
        500: _ERROR_RESPONSES[500],
        503: _ERROR_RESPONSES[503],
    },
    summary="Change the signed-in account password",
    description=(
        "Verifies the current password with Argon2id, hashes the new one, "
        "revokes every existing refresh session and issues a fresh rotated "
        "session. This is also how a provisioned account clears the forced "
        "password change that blocks operational endpoints."
    ),
)
def change_password(
    response: Response,
    db: DbSession,
    account: CurrentAccount,
    _: BrowserRequest,
    payload: PasswordChangeRequest,
) -> AuthResponse:
    result, refresh_token = auth_service.change_password(db, account, payload)
    _set_refresh_cookie(response, refresh_token)
    _no_store(response)
    return result


@router.get(
    "/me",
    response_model=AccountProfile,
    responses={
        401: _ERROR_RESPONSES[401],
        500: _ERROR_RESPONSES[500],
        503: _ERROR_RESPONSES[503],
    },
    summary="Current verified account",
    description=(
        "Returns the account and role loaded from PostgreSQL for this access "
        "token. Password and refresh-token material are never included."
    ),
)
def me(response: Response, account: CurrentAccount) -> AccountProfile:
    _no_store(response)
    return auth_service.to_profile(account)


@router.get(
    "/permissions",
    response_model=list[str],
    include_in_schema=False,
    dependencies=[Depends(get_current_account)],
)
def permissions(account: CurrentAccount) -> list[str]:
    """Compatibility helper; `/auth/me` already includes permissions."""
    return auth_service.permissions_for(account.role)
