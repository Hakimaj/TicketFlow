"""Database access for activity/audit events.

Activities are written only by the mutation/note services and are never
updated. Every query eager-loads the ticket and reply labels needed for the
response, so list endpoints do not issue per-row queries.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.labels import ACTIVITY_ACTION_LABELS
from app.models.activity import TicketActivity
from app.models.agent import Agent
from app.models.enums import ActivityAction, ActivityActorType
from app.models.reply import CustomerReply
from app.models.ticket import Ticket
from app.models.common import utcnow
from app.schemas.tickets import SortDirection


@dataclass(frozen=True)
class ActivityFilters:
    ticket_public_id: str | None = None
    actions: tuple[ActivityAction, ...] = field(default_factory=tuple)
    actor_id: str | None = None
    search: str | None = None
    start: datetime | None = None
    end: datetime | None = None


def new_public_id() -> str:
    """Stable-format, collision-resistant public activity ID (fits 16 chars)."""
    return f"ACT-{uuid.uuid4().hex[:12].upper()}"


def add_activity(
    db: Session,
    *,
    ticket: Ticket,
    actor: Agent,
    action: ActivityAction,
    detail: str,
    note_id: uuid.UUID | None = None,
    reply: CustomerReply | None = None,
    reply_version: int | None = None,
    is_internal_note: bool = False,
    actor_account_id: uuid.UUID | None = None,
) -> TicketActivity:
    """Stage an activity event in the caller's transaction (no commit).

    ``reply``/``reply_version`` link the event to the logical reply and the
    exact immutable revision it describes. The detail stays a short, safe
    summary; reply bodies and reviewer comments are never copied into it.
    """
    activity = TicketActivity(
        public_id=new_public_id(),
        ticket_id=ticket.id,
        reply_id=reply.id if reply is not None else None,
        reply_version=reply_version,
        note_id=note_id,
        actor_id=actor.id,
        actor_account_id=actor_account_id,
        actor_name=actor.name,
        actor_type=ActivityActorType.AGENT,
        action=action,
        detail=detail,
        is_internal_note=is_internal_note,
        created_at=utcnow(),
    )
    db.add(activity)
    return activity


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters(
    stmt: Select[Any], filters: ActivityFilters
) -> Select[Any]:
    if filters.ticket_public_id:
        stmt = stmt.where(Ticket.public_id == filters.ticket_public_id)
    if filters.actions:
        stmt = stmt.where(TicketActivity.action.in_(filters.actions))
    if filters.actor_id:
        stmt = stmt.where(TicketActivity.actor_id == filters.actor_id)
    if filters.start is not None:
        stmt = stmt.where(TicketActivity.created_at >= filters.start)
    if filters.end is not None:
        # End is exclusive, so adjacent windows never double-count an event.
        stmt = stmt.where(TicketActivity.created_at < filters.end)
    if filters.search:
        needle = filters.search.strip()
        pattern = f"%{_escape_like(needle)}%"
        matching_actions = [
            action
            for action, label in ACTIVITY_ACTION_LABELS.items()
            if needle.lower() in label.lower()
        ]
        conditions = [
            Ticket.public_id.ilike(pattern, escape="\\"),
            TicketActivity.actor_name.ilike(pattern, escape="\\"),
            TicketActivity.detail.ilike(pattern, escape="\\"),
            cast(TicketActivity.action, String).ilike(pattern, escape="\\"),
        ]
        if matching_actions:
            conditions.append(TicketActivity.action.in_(matching_actions))
        stmt = stmt.where(or_(*conditions))
    return stmt


def _base_select() -> Select[Any]:
    return select(TicketActivity).join(TicketActivity.ticket)


def _with_labels(stmt: Select[Any]) -> Select[Any]:
    return stmt.options(
        joinedload(TicketActivity.ticket),
        selectinload(TicketActivity.reply),
    )


def list_activities(
    db: Session,
    filters: ActivityFilters,
    *,
    sort_dir: SortDirection,
    page: int,
    page_size: int,
) -> tuple[list[TicketActivity], int]:
    count_stmt = _apply_filters(
        select(func.count()).select_from(TicketActivity).join(TicketActivity.ticket),
        filters,
    )
    total = int(db.scalar(count_stmt) or 0)

    order = (
        TicketActivity.created_at.asc()
        if sort_dir is SortDirection.ASC
        else TicketActivity.created_at.desc()
    )
    stmt = (
        _apply_filters(_base_select(), filters)
        .options(
            joinedload(TicketActivity.ticket),
            selectinload(TicketActivity.reply),
        )
        .order_by(order, TicketActivity.public_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique().all()), total


def list_for_ticket(db: Session, ticket_id: uuid.UUID) -> list[TicketActivity]:
    stmt = (
        _with_labels(select(TicketActivity))
        .where(TicketActivity.ticket_id == ticket_id)
        .order_by(
            TicketActivity.created_at.asc(), TicketActivity.public_id.asc()
        )
    )
    return list(db.scalars(stmt).unique().all())
