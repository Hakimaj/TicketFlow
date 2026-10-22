"""SQL aggregates for the ticket dashboard summary."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.labels import ACTIVE_STATUSES
from app.models.enums import TicketCategory, TicketPriority, TicketStatus
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

    return DashboardCounts(
        total=int(row.total),
        active=int(row.active),
        unassigned=int(row.unassigned),
        urgent_high=int(row.urgent_high),
        needs_review=int(row.needs_review),
        status_counts=status_counts,
        category_counts=category_counts,
        priority_counts=priority_counts,
    )
