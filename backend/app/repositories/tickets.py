"""Database access for tickets.

Filtering, ordering and pagination happen in SQL. Sort fields are resolved
through an allow-list mapping, so no client string ever reaches an ``ORDER BY``
expression.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Integer,
    Select,
    case,
    cast,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.orm import Session, joinedload

from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.models.requester import Requester
from app.models.ticket import Ticket
from app.schemas.tickets import SortDirection, TicketSortField

# Domain order, not alphabetical, matching the frontend's sort behaviour.
_PRIORITY_RANK = {
    TicketPriority.URGENT: 0,
    TicketPriority.HIGH: 1,
    TicketPriority.NORMAL: 2,
    TicketPriority.LOW: 3,
}
_STATUS_RANK = {
    TicketStatus.NEW: 0,
    TicketStatus.OPEN: 1,
    TicketStatus.PENDING: 2,
    TicketStatus.NEEDS_REVIEW: 3,
    TicketStatus.RESOLVED: 4,
    TicketStatus.CLOSED: 5,
}

# Transaction-scoped advisory lock key serialising ticket-number allocation.
# It is not a secret; it only keeps concurrent intake transactions from
# generating the same ``TF-####`` identifier.
_PUBLIC_ID_LOCK_KEY = 771_042_001

_SORT_EXPRESSIONS: dict[TicketSortField, Any] = {
    TicketSortField.CREATED_AT: Ticket.created_at,
    TicketSortField.UPDATED_AT: Ticket.updated_at,
    TicketSortField.SUBJECT: Ticket.subject,
    TicketSortField.CATEGORY: Ticket.category,
    TicketSortField.PRIORITY: case(
        _PRIORITY_RANK, value=Ticket.priority, else_=len(_PRIORITY_RANK)
    ),
    TicketSortField.STATUS: case(
        _STATUS_RANK, value=Ticket.status, else_=len(_STATUS_RANK)
    ),
}


@dataclass(frozen=True)
class TicketFilters:
    """Validated filters passed from the API layer."""

    search: str | None = None
    statuses: tuple[TicketStatus, ...] = field(default_factory=tuple)
    categories: tuple[TicketCategory, ...] = field(default_factory=tuple)
    priorities: tuple[TicketPriority, ...] = field(default_factory=tuple)
    assigned_agent_id: str | None = None
    unassigned_only: bool = False


def _escape_like(term: str) -> str:
    """Escape LIKE wildcards so user input is matched literally."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters(stmt: Select[Any], filters: TicketFilters) -> Select[Any]:
    if filters.search:
        pattern = f"%{_escape_like(filters.search.strip())}%"
        stmt = stmt.where(
            or_(
                Ticket.public_id.ilike(pattern, escape="\\"),
                Ticket.subject.ilike(pattern, escape="\\"),
                Requester.name.ilike(pattern, escape="\\"),
            )
        )
    if filters.statuses:
        stmt = stmt.where(Ticket.status.in_(filters.statuses))
    if filters.categories:
        stmt = stmt.where(Ticket.category.in_(filters.categories))
    if filters.priorities:
        stmt = stmt.where(Ticket.priority.in_(filters.priorities))
    if filters.unassigned_only:
        stmt = stmt.where(Ticket.assigned_agent_id.is_(None))
    elif filters.assigned_agent_id:
        stmt = stmt.where(Ticket.assigned_agent_id == filters.assigned_agent_id)
    return stmt


def _base_select() -> Select[Any]:
    # The join also makes requester search possible in both list and count.
    return select(Ticket).join(Ticket.requester)


def list_tickets(
    db: Session,
    filters: TicketFilters,
    *,
    sort_by: TicketSortField,
    sort_dir: SortDirection,
    page: int,
    page_size: int,
) -> tuple[list[Ticket], int]:
    """Return one page of tickets plus the total number of matches."""
    count_stmt = _apply_filters(
        select(func.count()).select_from(Ticket).join(Ticket.requester), filters
    )
    total = int(db.scalar(count_stmt) or 0)

    sort_expression: ColumnElement[Any] = _SORT_EXPRESSIONS[sort_by]
    ordering = (
        sort_expression.asc()
        if sort_dir is SortDirection.ASC
        else sort_expression.desc()
    )

    stmt = (
        _apply_filters(_base_select(), filters)
        .options(
            joinedload(Ticket.requester),
            joinedload(Ticket.assigned_agent),
        )
        .order_by(ordering, Ticket.public_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.scalars(stmt).unique().all())
    return items, total


def get_ticket_by_public_id(
    db: Session, public_id: str, *, populate_existing: bool = False
) -> Ticket | None:
    stmt = (
        select(Ticket)
        .options(
            joinedload(Ticket.requester),
            joinedload(Ticket.assigned_agent),
        )
        .where(Ticket.public_id == public_id)
    )
    if populate_existing:
        # Mutations change scalar columns and relationships; force the
        # identity-mapped instance and eager loads to be refreshed.
        stmt = stmt.execution_options(populate_existing=True)
    return db.scalars(stmt).unique().one_or_none()


def get_ticket_for_update(db: Session, public_id: str) -> Ticket | None:
    """Load a ticket and lock its row for the current transaction.

    The lock is taken without eager joins (PostgreSQL cannot apply
    ``FOR UPDATE`` to the nullable side of an outer join) and reloads the row
    so a version read after a concurrent commit is never served from a stale
    identity-map instance. Requester/assignee load lazily inside the same
    transaction.
    """
    stmt = (
        select(Ticket)
        .where(Ticket.public_id == public_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).one_or_none()


def next_public_id(db: Session) -> str:
    """Allocate the next sequential ``TF-####`` identifier.

    The advisory lock is held until the transaction ends, so two concurrent
    intakes cannot compute the same maximum. Identifiers stay short, readable
    and ordered, matching the existing seeded convention.
    """
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _PUBLIC_ID_LOCK_KEY})
    highest = db.scalar(
        select(func.max(cast(func.substr(Ticket.public_id, 4), Integer)))
    )
    return f"TF-{(int(highest) if highest is not None else 1000) + 1}"
