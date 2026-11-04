"""Dashboard summary contract.

All values are SQL aggregates over persisted tickets and logical replies. The
ticket-level ``needs_review_tickets`` metric stays separate from reply-approval
counts. SLA/CSAT and real delivery metrics are deliberately absent: no SLA
tracking exists and demo sends do not deliver messages.
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


class TrendPoint(BaseModel):
    """One UTC day bucket of ticket creation/resolution activity."""

    date: str = Field(description="UTC day bucket, e.g. `2026-10-21`.")
    received: int = Field(description="Tickets created on that UTC day.")
    resolved: int = Field(
        description=(
            "Current resolved/closed tickets whose `updated_at` falls on that "
            "day. A proxy: the schema stores no explicit resolution event "
            "time; later edits move a terminal ticket to a newer day bucket."
        )
    )


class PriorityStatusRow(BaseModel):
    """Active-workload status breakdown for one priority level."""

    priority: TicketPriority
    open: int = Field(description="Tickets with status `new` or `open`.")
    pending: int = Field(description="Tickets with status `pending`.")
    needs_review: int = Field(description="Tickets with status `needs_review`.")
    total: int = Field(description="All tickets with this priority.")


class AgentWorkloadRow(BaseModel):
    """Current active-ticket count per assignee (null = unassigned)."""

    agent_id: str | None
    agent_name: str | None = Field(
        default=None,
        description="Name of the assigned agent, absent for the unassigned bucket.",
    )
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
                "pending_reply_approvals": 2,
                "draft_replies": 0,
                "approved_replies_awaiting_send": 1,
                "sent_replies_demo": 1,
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
    pending_reply_approvals: int = Field(
        description=(
            "Logical replies currently in `pending_approval` (one per reply, "
            "never per revision)."
        )
    )
    draft_replies: int = Field(
        description="Logical replies currently in `draft`."
    )
    approved_replies_awaiting_send: int = Field(
        description=(
            "Logical replies in `approved` awaiting an explicit demo-send "
            "action. Approval does not send."
        )
    )
    sent_replies_demo: int = Field(
        description=(
            "Logical replies marked as sent in demo mode. This is not a "
            "customer-delivery count."
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
    # Optional breakdowns, included only when the caller asks for a trend
    # window (`?trend_days=N`). Charts derive from timestamps, never from
    # invented history.
    received_trend: list[TrendPoint] | None = Field(
        default=None,
        description=(
            "Per-UTC-day created (and resolved-proxy) counts. Only included "
            "when `trend_days` is supplied."
        ),
    )
    priority_summary: list[PriorityStatusRow] | None = Field(
        default=None,
        description=(
            "Status breakdown per priority. Only included when `trend_days` "
            "is supplied."
        ),
    )
    agent_workload: list[AgentWorkloadRow] | None = Field(
        default=None,
        description=(
            "Active tickets per assignee, including the unassigned bucket. "
            "Only included when `trend_days` is supplied."
        ),
    )
