"""Ticket dashboard summary service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.common import utcnow
from app.models.enums import (
    ReplyState,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.repositories import dashboard as dashboard_repo
from app.schemas.dashboard import (
    AgentWorkloadRow,
    CategoryCount,
    DashboardSummary,
    PriorityCount,
    PriorityStatusRow,
    StatusCount,
    TrendPoint,
)


def get_summary(db: Session, *, trend_days: int | None = None) -> DashboardSummary:
    counts = dashboard_repo.get_dashboard_counts(db)
    base = dict(
        generated_at=utcnow(),
        total_tickets=counts.total,
        active_tickets=counts.active,
        unassigned_tickets=counts.unassigned,
        urgent_high_tickets=counts.urgent_high,
        needs_review_tickets=counts.needs_review,
        pending_reply_approvals=counts.reply_state_counts[
            ReplyState.PENDING_APPROVAL
        ],
        draft_replies=counts.reply_state_counts[ReplyState.DRAFT],
        approved_replies_awaiting_send=counts.reply_state_counts[
            ReplyState.APPROVED
        ],
        sent_replies_demo=counts.reply_state_counts[ReplyState.SENT],
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

    if trend_days is not None:
        base.update(_extended_breakdowns(db, trend_days))

    return DashboardSummary(**base)


def _extended_breakdowns(db: Session, trend_days: int) -> dict[str, list]:
    """Trend, priority/status matrix and agent workload for charts.

    Everything derives from persisted timestamps in SQL: counts per UTC day
    and current-state groupings. Nothing invents historical data.
    """
    now = utcnow()
    # Anchor the window to the start of today's UTC day so buckets line up
    # with the displayed dates; `days` includes today.
    since = datetime.combine(
        now.astimezone(UTC).date(), datetime.min.time(), tzinfo=UTC
    ) - timedelta(days=trend_days - 1)

    created = dashboard_repo.get_daily_created_counts(db, since=since)
    resolved = dashboard_repo.get_daily_resolved_counts(db, since=since)

    first_day = since.date()
    trend: list[TrendPoint] = []
    for index in range(trend_days):
        day = first_day + timedelta(days=index)
        trend.append(
            TrendPoint(
                date=day.isoformat(),
                received=created.get(day, 0),
                resolved=resolved.get(day, 0),
            )
        )

    matrix = dashboard_repo.get_priority_status_matrix(db)
    priority_summary = [
        PriorityStatusRow(
            priority=priority,
            open=matrix[priority][TicketStatus.NEW]
            + matrix[priority][TicketStatus.OPEN],
            pending=matrix[priority][TicketStatus.PENDING],
            needs_review=matrix[priority][TicketStatus.NEEDS_REVIEW],
            total=sum(matrix[priority].values()),
        )
        for priority in TicketPriority
    ]

    workload = [
        AgentWorkloadRow(agent_id=agent_id, agent_name=name, count=count)
        for agent_id, name, count in dashboard_repo.get_agent_workload(db)
    ]

    return {
        "received_trend": trend,
        "priority_summary": priority_summary,
        "agent_workload": workload,
    }
