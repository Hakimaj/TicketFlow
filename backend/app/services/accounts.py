"""Account administration service.

Rules enforced here (the route layer only adds the permission check):

- only an admin-permission account may manage accounts;
- roles and activation always come from persisted rows, never from client
  claims; the acting identity is the verified account;
- an administrator cannot change their own role or activation state, so a
  request body cannot escalate or lock out the caller;
- the last active administrator cannot be demoted or deactivated;
- emails are unique and one support agent can back at most one account;
- deactivating an account immediately revokes its refresh sessions, and an
  inactive account can never sign in or rotate a session (see
  ``app.services.auth``);
- no password hash, refresh-token hash or session identifier is exposed.
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.models.auth import UserAccount
from app.models.common import utcnow
from app.models.enums import AccountRole
from app.repositories import accounts as account_repo
from app.repositories import agents as agent_repo
from app.repositories import auth as auth_repo
from app.schemas.accounts import (
    AccountCreate,
    AccountListResponse,
    AccountUpdate,
    AdminAccountSummary,
)
from app.schemas.common import PageMeta
from app.services import auth as auth_service
from app.services.common import transaction


def to_summary(account: UserAccount) -> AdminAccountSummary:
    return AdminAccountSummary(
        id=str(account.id),
        email=account.email,
        display_name=account.display_name,
        role=account.role,
        is_active=account.is_active,
        must_change_password=account.must_change_password,
        agent_id=account.agent_id,
        agent_name=account.agent.name if account.agent else None,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def _fresh(db: Session, account: UserAccount) -> UserAccount:
    """Reload columns and expire relationships after a commit.

    Sessions are configured with ``expire_on_commit=False``, so without this
    an updated ``agent_id`` would still render the previously loaded agent.
    """
    db.refresh(account)
    return account


def _account_or_404(db: Session, account_id: uuid.UUID) -> UserAccount:
    account = account_repo.get_account(db, account_id)
    if account is None:
        raise not_found(
            "account_not_found", "That account no longer exists."
        )
    return account


def _validated_agent_id(db: Session, agent_id: str | None) -> str | None:
    if agent_id is None:
        return None
    agent = agent_repo.get_agent(db, agent_id)
    if agent is None:
        raise ApiError(
            status_code=422,
            code="invalid_agent",
            message=f"Agent {agent_id} does not exist.",
        )
    return agent.id


def _ensure_agent_free(
    db: Session, agent_id: str | None, *, allow_account_id: uuid.UUID | None = None
) -> None:
    if agent_id is None:
        return
    existing = account_repo.get_account_by_agent(db, agent_id)
    if existing is not None and existing.id != allow_account_id:
        raise ApiError(
            status_code=409,
            code="agent_already_linked",
            message=(
                f"Agent {agent_id} is already linked to another account. "
                "Unlink it first."
            ),
        )


def list_accounts(
    db: Session,
    *,
    search: str | None,
    role: AccountRole | None,
    is_active: bool | None,
    page: int,
    page_size: int,
) -> AccountListResponse:
    from app.repositories.accounts import AccountFilters

    items, total = account_repo.list_accounts(
        db,
        AccountFilters(search=search, role=role, is_active=is_active),
        page=page,
        page_size=page_size,
    )
    page_count = (total + page_size - 1) // page_size if total else 0
    return AccountListResponse(
        items=[to_summary(account) for account in items],
        pagination=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            page_count=page_count,
        ),
    )


def create_account(
    db: Session, payload: AccountCreate, *, actor: UserAccount
) -> AdminAccountSummary:
    """Provision an account with an initial password.

    The password is hashed by the shared Argon2id helper and the account is
    flagged so it must choose a new one before using the workspace.
    """
    del actor  # Authorization is enforced by the route dependency.
    if auth_repo.get_user_by_email(db, payload.email) is not None:
        raise ApiError(
            status_code=409,
            code="account_exists",
            message=f"An account with {payload.email} already exists.",
        )
    agent_id = _validated_agent_id(db, payload.agent_id)
    _ensure_agent_free(db, agent_id)

    try:
        with transaction(db):
            account = auth_service.create_account(
                db,
                email=payload.email,
                password=payload.password,
                display_name=payload.display_name,
                role=payload.role,
                agent_id=agent_id,
                is_active=payload.is_active,
                must_change_password=True,
            )
            db.flush()
    except IntegrityError as exc:
        raise ApiError(
            status_code=409,
            code="account_exists",
            message="That account or agent link was created concurrently.",
        ) from exc

    return to_summary(_fresh(db, account))


def update_account(
    db: Session,
    account_id: uuid.UUID,
    payload: AccountUpdate,
    *,
    actor: UserAccount,
) -> AdminAccountSummary:
    account = _account_or_404(db, account_id)
    provided = payload.model_fields_set
    if not provided:
        raise ApiError(
            status_code=422,
            code="empty_update",
            message="Send at least one field to update.",
        )

    role_changing = "role" in provided and payload.role != account.role
    activation_changing = (
        "is_active" in provided and payload.is_active != account.is_active
    )

    if account.id == actor.id and (role_changing or activation_changing):
        raise ApiError(
            status_code=403,
            code="self_management_forbidden",
            message=(
                "Administrators cannot change their own role or activation "
                "state. Ask another administrator."
            ),
        )

    losing_admin = (
        account.role is AccountRole.ADMIN and account.is_active
    ) and (
        (role_changing and payload.role != AccountRole.ADMIN)
        or (activation_changing and payload.is_active is False)
    )
    if losing_admin and account_repo.count_active_admins(db, exclude_id=account.id) == 0:
        raise ApiError(
            status_code=409,
            code="last_admin",
            message=(
                "This is the only active administrator. Promote or activate "
                "another administrator first."
            ),
        )

    new_agent_id = account.agent_id
    if "agent_id" in provided:
        new_agent_id = _validated_agent_id(db, payload.agent_id)
        if new_agent_id != account.agent_id:
            _ensure_agent_free(db, new_agent_id, allow_account_id=account.id)

    deactivating = activation_changing and payload.is_active is False
    now = utcnow()

    try:
        with transaction(db):
            if "display_name" in provided and payload.display_name is not None:
                account.display_name = payload.display_name
            if role_changing and payload.role is not None:
                account.role = payload.role
            if "agent_id" in provided:
                account.agent_id = new_agent_id
            if activation_changing and payload.is_active is not None:
                account.is_active = payload.is_active
            if deactivating:
                # Existing sessions die immediately: an inactive account must
                # not be able to rotate a refresh cookie into a new token.
                auth_repo.revoke_all_for_user(db, account.id, now)
    except IntegrityError as exc:
        raise ApiError(
            status_code=409,
            code="agent_already_linked",
            message="That agent is already linked to another account.",
        ) from exc

    return to_summary(_fresh(db, account))
