"""Human-readable labels for domain values.

These mirror the frontend's `lib/ticket-config.ts` and
`lib/activity-config.ts`. They are used when composing concise, privacy-safe
audit descriptions; API payloads always use the raw enum values.
"""

from __future__ import annotations

from app.models.enums import (
    ActivityAction,
    SupportTeam,
    TicketCategory,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)

STATUS_LABELS: dict[TicketStatus, str] = {
    TicketStatus.NEW: "New",
    TicketStatus.OPEN: "Open",
    TicketStatus.PENDING: "Pending",
    TicketStatus.NEEDS_REVIEW: "Needs Review",
    TicketStatus.RESOLVED: "Resolved",
    TicketStatus.CLOSED: "Closed",
}

PRIORITY_LABELS: dict[TicketPriority, str] = {
    TicketPriority.URGENT: "Urgent",
    TicketPriority.HIGH: "High",
    TicketPriority.NORMAL: "Normal",
    TicketPriority.LOW: "Low",
}

CATEGORY_LABELS: dict[TicketCategory, str] = {
    TicketCategory.BILLING: "Billing",
    TicketCategory.DELIVERY: "Delivery",
    TicketCategory.TECHNICAL: "Technical",
    TicketCategory.RETURNS: "Returns",
    TicketCategory.GENERAL: "General",
}

TEAM_LABELS: dict[SupportTeam, str] = {
    SupportTeam.CUSTOMER_SUPPORT: "Customer Support",
    SupportTeam.BILLING_TEAM: "Billing Team",
    SupportTeam.LOGISTICS_TEAM: "Logistics Team",
    SupportTeam.TECHNICAL_SUPPORT: "Technical Support",
    SupportTeam.RETURNS_TEAM: "Returns Team",
}

# Authoritative category → owning-team routing used by triage and seeding.
# Statuses that count as active work (not terminal), matching the frontend.
ACTIVE_STATUSES: tuple[TicketStatus, ...] = (
    TicketStatus.NEW,
    TicketStatus.OPEN,
    TicketStatus.PENDING,
)

CATEGORY_TEAM: dict[TicketCategory, SupportTeam] = {
    TicketCategory.BILLING: SupportTeam.BILLING_TEAM,
    TicketCategory.DELIVERY: SupportTeam.LOGISTICS_TEAM,
    TicketCategory.TECHNICAL: SupportTeam.TECHNICAL_SUPPORT,
    TicketCategory.RETURNS: SupportTeam.RETURNS_TEAM,
    TicketCategory.GENERAL: SupportTeam.CUSTOMER_SUPPORT,
}

CHANNEL_LABELS: dict[TicketChannel, str] = {
    TicketChannel.WEB_FORM: "Web form",
    TicketChannel.EMAIL: "Email",
    TicketChannel.PHONE: "Phone",
    TicketChannel.CHAT: "Chat",
}

ACTIVITY_ACTION_LABELS: dict[ActivityAction, str] = {
    ActivityAction.CREATED: "Ticket created",
    ActivityAction.CATEGORIZED: "Category changed",
    ActivityAction.ASSIGNED: "Assignment changed",
    ActivityAction.REPLIED_DRAFT: "Reply draft saved",
    ActivityAction.REPLIED_SENT: "Reply sent (demo)",
    ActivityAction.STATUS_CHANGED: "Status changed",
    ActivityAction.ESCALATED: "Escalated",
    ActivityAction.REVIEW_FLAGGED: "Flagged for review",
    ActivityAction.MERGED: "Tickets merged",
    ActivityAction.RESOLVED: "Resolved",
    ActivityAction.PRIORITY_CHANGED: "Priority changed",
    ActivityAction.NOTE_ADDED: "Internal note added",
    ActivityAction.REPLY_SUBMITTED: "Reply submitted for approval",
    ActivityAction.REPLY_APPROVED: "Reply approved",
    ActivityAction.REPLY_CHANGES_REQUESTED: "Reply changes requested",
}
