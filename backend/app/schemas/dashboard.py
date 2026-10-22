"""Ticket dashboard summary contract.

All values are SQL aggregates over persisted tickets. Reply-approval counts and
SLA/CSAT metrics are deliberately absent: the reply workflow and any SLA
tracking are not implemented, so claiming those numbers would be misleading.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.schemas.common import UtcDatetime


class StatusCount(BaseModel):
    status: TicketStatus
    count: int


class CategoryCount(BaseModel):
    category: TicketCategory
    count: int


class PriorityCount(BaseModel):
    priority: TicketPriority
    count: int


class DashboardSummary(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "generated_at": "2026-10-21T18:00:00.000Z",
                "total_tickets": 24,
                "active_tickets": 17,
                "unassigned_tickets": 5,
                "urgent_high_tickets": 7,
                "needs_review_tickets": 2,
                "status_counts": [{"status": "new", "count": 4}],
                "category_counts": [{"category": "billing", "count": 6}],
                "priority_counts": [{"priority": "urgent", "count": 4}],
            }
        }
    )

    generated_at: UtcDatetime = Field(
        description="Server time when the aggregates were computed (UTC)."
    )
    total_tickets: int = Field(description="All persisted tickets.")
    active_tickets: int = Field(
        description="Tickets with status `new`, `open` or `pending`."
    )
    unassigned_tickets: int = Field(
        description="Active tickets with no assigned agent."
    )
    urgent_high_tickets: int = Field(
        description="Active tickets with priority `urgent` or `high`."
    )
    needs_review_tickets: int = Field(
        description=(
            "All tickets whose ticket-level status is `needs_review`. "
            "Unrelated to customer reply approvals."
        )
    )
    status_counts: list[StatusCount] = Field(
        description="All tickets grouped by status, including zero-count values."
    )
    category_counts: list[CategoryCount] = Field(
        description="All tickets grouped by category, in domain order."
    )
    priority_counts: list[PriorityCount] = Field(
        description="All tickets grouped by priority, in domain order."
    )
