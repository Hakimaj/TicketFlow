"""Ticket dashboard summary service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.common import utcnow
from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.repositories import dashboard as dashboard_repo
from app.schemas.dashboard import (
    CategoryCount,
    DashboardSummary,
    PriorityCount,
    StatusCount,
)


def get_summary(db: Session) -> DashboardSummary:
    counts = dashboard_repo.get_dashboard_counts(db)
    return DashboardSummary(
        generated_at=utcnow(),
        total_tickets=counts.total,
        active_tickets=counts.active,
        unassigned_tickets=counts.unassigned,
        urgent_high_tickets=counts.urgent_high,
        needs_review_tickets=counts.needs_review,
        status_counts=[
            StatusCount(status=status, count=counts.status_counts[status])
            for status in TicketStatus
        ],
        category_counts=[
            CategoryCount(category=category, count=counts.category_counts[category])
            for category in TicketCategory
        ],
        priority_counts=[
            PriorityCount(priority=priority, count=counts.priority_counts[priority])
            for priority in TicketPriority
        ],
    )
