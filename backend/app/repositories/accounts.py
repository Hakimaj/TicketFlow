"""Database access for account administration.

Queries return ``UserAccount`` rows; response projections live in the service
so no route ever serializes an ORM object directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.auth import UserAccount
from app.models.enums import AccountRole


@dataclass(frozen=True)
class AccountFilters:
    search: str | None = None
    role: AccountRole | None = None
    is_active: bool | None = None


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters(stmt: Select[object], filters: AccountFilters) -> Select[object]:
    if filters.search:
        pattern = f"%{_escape_like(filters.search.strip())}%"
        stmt = stmt.where(
            or_(
                UserAccount.email.ilike(pattern, escape="\\"),
                UserAccount.display_name.ilike(pattern, escape="\\"),
                UserAccount.agent_id.ilike(pattern, escape="\\"),
            )
        )
    if filters.role is not None:
        stmt = stmt.where(UserAccount.role == filters.role)
    if filters.is_active is not None:
        stmt = stmt.where(UserAccount.is_active.is_(filters.is_active))
    return stmt


def list_accounts(
    db: Session,
    filters: AccountFilters,
    *,
    page: int,
    page_size: int,
) -> tuple[list[UserAccount], int]:
    count_stmt = _apply_filters(
        select(func.count()).select_from(UserAccount), filters
    )
    total = int(db.scalar(count_stmt) or 0)
    stmt = (
        _apply_filters(select(UserAccount), filters)
        .options(joinedload(UserAccount.agent))
        .order_by(UserAccount.email.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique().all()), total


def get_account(db: Session, account_id: uuid.UUID) -> UserAccount | None:
    return db.scalars(
        select(UserAccount)
        .options(joinedload(UserAccount.agent))
        .where(UserAccount.id == account_id)
    ).one_or_none()


def get_account_by_agent(
    db: Session, agent_id: str
) -> UserAccount | None:
    return db.scalars(
        select(UserAccount).where(UserAccount.agent_id == agent_id)
    ).one_or_none()


def count_active_admins(db: Session, *, exclude_id: uuid.UUID | None = None) -> int:
    stmt = select(func.count()).select_from(UserAccount).where(
        UserAccount.role == AccountRole.ADMIN,
        UserAccount.is_active.is_(True),
    )
    if exclude_id is not None:
        stmt = stmt.where(UserAccount.id != exclude_id)
    return int(db.scalar(stmt) or 0)
