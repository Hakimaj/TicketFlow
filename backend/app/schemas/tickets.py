"""Ticket list/detail API contracts.

Field names are snake_case for Python/HTTP consistency; the mapping to the
frontend's camelCase `Ticket` type is documented in
``docs/backend-api-contract.md``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    SupportTeam,
    TicketCategory,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)
from app.schemas.common import PageMeta, UtcDatetime


class TicketSortField(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PRIORITY = "priority"
    STATUS = "status"
    SUBJECT = "subject"
    CATEGORY = "category"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class RequesterSummary(BaseModel):
    """Customer details, only returned by the ticket detail endpoint."""

    id: str = Field(description="Opaque requester identifier (UUID).")
    name: str
    email: str = Field(description="Fictional demonstration address in seed data.")


class TicketSummary(BaseModel):
    """Ticket row as shown in queues and tables."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "TF-1051",
                "subject": "Charged twice from Telebirr for order #ET-88412",
                "requester_name": "Marta Alemu",
                "channel": "web_form",
                "category": "billing",
                "priority": "urgent",
                "status": "open",
                "assigned_team": "billing_team",
                "assigned_agent_id": "AG-02",
                "assigned_agent_name": "Hana Tesfaye",
                "created_at": "2026-10-21T16:33:00.000Z",
                "updated_at": "2026-10-21T17:09:00.000Z",
            }
        }
    )

    id: str = Field(description="Public ticket identifier, e.g. `TF-1051`.")
    subject: str
    requester_name: str = Field(
        description="Customer display name only; email is detail-only."
    )
    channel: TicketChannel
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    assigned_team: SupportTeam | None
    assigned_agent_id: str | None
    assigned_agent_name: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class TicketDetail(TicketSummary):
    """Full ticket record for the ticket workspace.

    Related replies and activity are intentionally **not** embedded yet; see
    the API contract document for the planned endpoints.
    """

    description: str = Field(description="Original customer message.")
    requester: RequesterSummary
    due_at: UtcDatetime | None
    suggested_category: TicketCategory | None
    suggested_priority: TicketPriority | None
    review_note: str | None


class TicketListResponse(BaseModel):
    items: list[TicketSummary]
    pagination: PageMeta


# ---------------------------------------------------------------------------
# Mutation request bodies (Phase 6)
# ---------------------------------------------------------------------------


class ActorContext(BaseModel):
    """Development-only actor metadata.

    There is no authentication yet. ``actor_id`` selects which seeded agent is
    recorded in the audit event and is therefore **untrusted**: any caller can
    claim any agent. It defaults to the seeded demo agent.
    """

    actor_id: str | None = Field(
        default=None,
        max_length=16,
        description=(
            "Development-only actor identifier. Untrusted until server-side "
            "authentication exists; defaults to the demo agent."
        ),
    )

    @field_validator("actor_id")
    @classmethod
    def _normalize_actor_id(cls, value: str | None) -> str | None:
        return value.strip().upper() if value and value.strip() else None


class TicketStatusUpdate(ActorContext):
    status: TicketStatus = Field(description="New ticket status.")


class TicketPriorityUpdate(ActorContext):
    priority: TicketPriority = Field(description="New ticket priority.")


class TicketCategoryUpdate(ActorContext):
    category: TicketCategory = Field(description="New ticket category.")


class TicketAssignmentUpdate(ActorContext):
    # Required but nullable: omitting the field is a validation error, while an
    # explicit null deliberately unassigns the ticket.
    agent_id: str | None = Field(
        description=(
            "Agent identifier to assign. Send `null` to unassign explicitly; "
            "the field is required."
        )
    )

    @field_validator("agent_id")
    @classmethod
    def _normalize_agent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            # Force an explicit `null` for unassignment instead of accepting
            # an accidental empty form value.
            raise ValueError(
                "agent_id must be null to unassign, or a non-empty agent ID."
            )
        return trimmed.upper()
