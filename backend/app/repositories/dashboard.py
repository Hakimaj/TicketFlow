"""SQL aggregates for the ticket dashboard summary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import and_, func, literal_column, select
from sqlalchemy.orm import Session

from app.core.labels import ACTIVE_STATUSES
from app.models.agent import Agent
from app.models.enums import (
    ReplyState,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.models.reply import CustomerReply
from app.models.ticket import Ticket


@dataclass(frozen=True)
class DashboardCounts:
    total: int
    active: int
    unassigned: int
    urgent_high: int
    needs_review: int
    status_counts: dict[TicketStatus, int]
    category_counts: dict[TicketCategory, int]
    priority_counts: dict[TicketPriority, int]
    reply_state_counts: dict[ReplyState, int]


def _grouped_counts(db: Session, column) -> dict:
    rows = db.execute(
        select(column, func.count(Ticket.id)).group_by(column)
    ).all()
    return {value: int(count) for value, count in rows}


def get_dashboard_counts(db: Session) -> DashboardCounts:
    """Compute all dashboard figures in SQL, not by loading ticket rows."""
    active = Ticket.status.in_(ACTIVE_STATUSES)
    row = db.execute(
        select(
            func.count(Ticket.id).label("total"),
            func.count(Ticket.id).filter(active).label("active"),
            func.count(Ticket.id)
            .filter(and_(active, Ticket.assigned_agent_id.is_(None)))
            .label("unassigned"),
            func.count(Ticket.id)
            .filter(
                and_(
                    active,
                    Ticket.priority.in_(
                        (TicketPriority.URGENT, TicketPriority.HIGH)
                    ),
                )
            )
            .label("urgent_high"),
            func.count(Ticket.id)
            .filter(Ticket.status == TicketStatus.NEEDS_REVIEW)
            .label("needs_review"),
        )
    ).one()

    status_counts = {status: 0 for status in TicketStatus}
    status_counts.update(_grouped_counts(db, Ticket.status))
    category_counts = {category: 0 for category in TicketCategory}
    category_counts.update(_grouped_counts(db, Ticket.category))
    priority_counts = {priority: 0 for priority in TicketPriority}
    priority_counts.update(_grouped_counts(db, Ticket.priority))

    # One row per logical reply (not per revision), grouped in SQL. Sentinel
    # replies convert on demo send and a new reply record starts afterwards, so
    # this never double-counts revisions of the same reply.
    reply_rows = db.execute(
        select(CustomerReply.state, func.count(CustomerReply.id)).group_by(
            CustomerReply.state
        )
    ).all()
    reply_state_counts: dict[ReplyState, int] = {
        state: 0 for state in ReplyState
    }
    reply_state_counts.update(
        {value: int(count) for value, count in reply_rows}
    )

    return DashboardCounts(
        total=int(row.total),
        active=int(row.active),
        unassigned=int(row.unassigned),
        urgent_high=int(row.urgent_high),
        needs_review=int(row.needs_review),
        status_counts=status_counts,
        category_counts=category_counts,
        priority_counts=priority_counts,
        reply_state_counts=reply_state_counts,
    )


def _day_bucket(column):
    """`date_trunc('day', column)` with a literal unit so psycopg keeps the
    text argument inlined (a bound parameter is type-ambiguous for
    PostgreSQL's overloaded `date_trunc`)."""
    return func.date_trunc(literal_column("'day'"), column)


def get_daily_created_counts(
    db: Session, *, since: datetime
) -> dict[date, int]:
    """Tickets created per UTC day bucket since ``since`` (inclusive)."""
    bucket = _day_bucket(Ticket.created_at)
    rows = db.execute(
        select(bucket, func.count(Ticket.id))
        .where(Ticket.created_at >= since)
        .group_by(bucket)
    ).all()
    return {value.date(): int(count) for value, count in rows}


def get_daily_resolved_counts(
    db: Session, *, since: datetime
) -> dict[date, int]:
    """Terminal-status tickets per UTC day, keyed by `updated_at` (proxy)."""
    bucket = _day_bucket(Ticket.updated_at)
    rows = db.execute(
        select(bucket, func.count(Ticket.id))
        .where(
            Ticket.updated_at >= since,
            Ticket.status.in_((TicketStatus.RESOLVED, TicketStatus.CLOSED)),
        )
        .group_by(bucket)
    ).all()
    return {value.date(): int(count) for value, count in rows}


def get_priority_status_matrix(
    db: Session,
) -> dict[TicketPriority, dict[TicketStatus, int]]:
    """Ticket counts per (priority, status) pair, grouped in SQL."""
    rows = db.execute(
        select(
            Ticket.priority,
            Ticket.status,
            func.count(Ticket.id),
        ).group_by(Ticket.priority, Ticket.status)
    ).all()
    matrix: dict[TicketPriority, dict[TicketStatus, int]] = {
        priority: {status: 0 for status in TicketStatus}
        for priority in TicketPriority
    }
    for priority, status, count in rows:
        matrix[priority][status] = int(count)
    return matrix


def get_agent_workload(
    db: Session,
) -> list[tuple[str | None, str | None, int]]:
    """Active tickets per assignee; unassigned appears as ``(None, None, n)``."""
    rows = db.execute(
        select(
            Ticket.assigned_agent_id,
            Agent.name,
            func.count(Ticket.id),
        )
        .outerjoin(Agent, Agent.id == Ticket.assigned_agent_id)
        .where(Ticket.status.in_(ACTIVE_STATUSES))
        .group_by(Ticket.assigned_agent_id, Agent.name)
        .order_by(func.count(Ticket.id).desc())
    ).all()
    return [
        (
            agent_id if agent_id is not None else None,
            name,
            int(count),
        )
        for agent_id, name, count in rows
    ]
