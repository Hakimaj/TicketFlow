"""Account administration endpoints (admin permission only).

Authorization is enforced by :data:`app.authorization.CanManageAccounts`
(`accounts:manage`, granted to the admin role); the route handlers only add the
verified acting account needed for self-management guards. Every response is a
safe projection — no password hash, refresh-token hash or session identifier is
ever returned.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.authorization import CanManageAccounts, CurrentAccount
from app.models.enums import AccountRole
from app.schemas.accounts import (
    AccountCreate,
    AccountListResponse,
    AccountUpdate,
    AdminAccountSummary,
)
from app.schemas.common import ErrorResponse
from app.services import accounts as account_service

router = APIRouter(prefix="/accounts", tags=["accounts"])

_ERROR_RESPONSES = {
    403: {
        "model": ErrorResponse,
        "description": "Only an account with `accounts:manage` may do this.",
    },
    404: {"model": ErrorResponse, "description": "Unknown account."},
    409: {"model": ErrorResponse, "description": "Conflicting account state."},
    422: {"model": ErrorResponse, "description": "Invalid body or reference."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.get(
    "",
    response_model=AccountListResponse,
    responses=_ERROR_RESPONSES,
    dependencies=[CanManageAccounts],
    summary="List accounts",
    description=(
        "Paginated account list for administrators. Includes activation state, "
        "role, agent link and the forced-password-change flag, but never any "
        "credential material."
    ),
)
def list_accounts(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[
        str | None,
        Query(
            max_length=120,
            description="Match on email, display name or agent ID.",
        ),
    ] = None,
    role: Annotated[
        AccountRole | None, Query(description="Filter by account role.")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="Filter by activation state.")
    ] = None,
) -> AccountListResponse:
    return account_service.list_accounts(
        db,
        search=search,
        role=role,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    status_code=201,
    response_model=AdminAccountSummary,
    responses=_ERROR_RESPONSES,
    dependencies=[CanManageAccounts],
    summary="Provision an account",
    description=(
        "Creates an account with an initial password (hashed with Argon2id and "
        "never returned). The account must change that password before using "
        "operational endpoints. Emails are unique and one support agent can "
        "back at most one account."
    ),
)
def create_account(
    db: DbSession,
    actor: CurrentAccount,
    payload: AccountCreate,
) -> AdminAccountSummary:
    return account_service.create_account(db, payload, actor=actor)


@router.patch(
    "/{account_id}",
    response_model=AdminAccountSummary,
    responses=_ERROR_RESPONSES,
    dependencies=[CanManageAccounts],
    summary="Update an account",
    description=(
        "Updates display name, role, agent link or activation. Omitted fields "
        "stay untouched; send `agent_id: null` explicitly to unlink. "
        "Deactivating revokes the account's refresh sessions immediately. "
        "Administrators cannot change their own role or activation state, and "
        "the last active administrator cannot be demoted or deactivated."
    ),
)
def update_account(
    db: DbSession,
    actor: CurrentAccount,
    account_id: uuid.UUID,
    payload: AccountUpdate,
) -> AdminAccountSummary:
    return account_service.update_account(
        db, account_id, payload, actor=actor
    )
