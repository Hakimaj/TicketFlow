"""Domain enums.

The string values are the exact values used by the frontend TypeScript types,
so API payloads, database rows and the existing `TicketService` contract all
speak the same vocabulary. Do not rename values without a frontend migration.
"""

from __future__ import annotations

from enum import StrEnum


class TicketStatus(StrEnum):
    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    NEEDS_REVIEW = "needs_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TicketCategory(StrEnum):
    BILLING = "billing"
    DELIVERY = "delivery"
    TECHNICAL = "technical"
    RETURNS = "returns"
    GENERAL = "general"


class TicketChannel(StrEnum):
    WEB_FORM = "web_form"
    EMAIL = "email"
    PHONE = "phone"
    CHAT = "chat"


class SupportTeam(StrEnum):
    CUSTOMER_SUPPORT = "customer_support"
    BILLING_TEAM = "billing_team"
    LOGISTICS_TEAM = "logistics_team"
    TECHNICAL_SUPPORT = "technical_support"
    RETURNS_TEAM = "returns_team"


class AgentRole(StrEnum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    AGENT = "agent"


class AccountRole(StrEnum):
    """Authenticated application role (separate from the HR-style agent role)."""

    AGENT = "agent"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class ReplyState(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    SENT = "sent"


class ReplyReviewDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


class ActivityActorType(StrEnum):
    AGENT = "agent"
    SYSTEM = "system"
    AUTOMATION = "automation"


class ActivityAction(StrEnum):
    CREATED = "created"
    CATEGORIZED = "categorized"
    ASSIGNED = "assigned"
    REPLIED_DRAFT = "replied_draft"
    REPLIED_SENT = "replied_sent"
    STATUS_CHANGED = "status_changed"
    ESCALATED = "escalated"
    REVIEW_FLAGGED = "review_flagged"
    MERGED = "merged"
    RESOLVED = "resolved"
    PRIORITY_CHANGED = "priority_changed"
    NOTE_ADDED = "note_added"
    REPLY_SUBMITTED = "reply_submitted"
    REPLY_APPROVED = "reply_approved"
    REPLY_CHANGES_REQUESTED = "reply_changes_requested"
