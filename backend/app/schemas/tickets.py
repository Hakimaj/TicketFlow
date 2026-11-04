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
    version: int = Field(
        ge=1,
        description=(
            "Concurrency token. Triaging mutations must send the version they "
            "last read as `expected_version`."
        ),
    )
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
# Intake (Phase 10)
# ---------------------------------------------------------------------------


class TicketCreate(BaseModel):
    """Staff intake payload.

    Deliberately small: a support request needs a requester, a subject, the
    message body, a category and a priority. No marketing or profile fields are
    collected, and there is no actor/role/status field — the creator comes from
    the access token and new tickets always start as ``new``.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Refund not received for order #ET-88412",
                "description": (
                    "The order was returned two weeks ago and the refund has "
                    "not appeared on my statement."
                ),
                "category": "billing",
                "priority": "normal",
                "channel": "web_form",
                "requester_name": "Marta Alemu",
                "requester_email": "marta.alemu@example.com",
            }
        }
    )

    subject: str = Field(
        min_length=3,
        max_length=300,
        description="Concise summary of the request.",
    )
    description: str = Field(
        min_length=10,
        max_length=5000,
        description="The customer's message, as received.",
    )
    category: TicketCategory = Field(description="Triage category for the request.")
    priority: TicketPriority = Field(
        default=TicketPriority.NORMAL,
        description="Defaults to `normal` when the intake channel has no signal.",
    )
    channel: TicketChannel = Field(
        default=TicketChannel.WEB_FORM,
        description="Where the request arrived. Defaults to `web_form`.",
    )
    requester_name: str = Field(
        min_length=2,
        max_length=160,
        description="Name of the customer who reported the issue.",
    )
    requester_email: str = Field(
        min_length=3,
        max_length=254,
        description=(
            "Customer email. Reused when it already exists, so one customer "
            "can own several tickets."
        ),
    )

    @field_validator("subject", "description", "requester_name")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("This field cannot be blank.")
        return trimmed

    @field_validator("requester_email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        # Stored lower-case so an existing requester is reused instead of
        # duplicated by casing.
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("A valid customer email address is required.")
        return normalized


# ---------------------------------------------------------------------------
# Mutation request bodies (Phase 6)
# ---------------------------------------------------------------------------


# Mutation bodies intentionally carry no actor/role fields: the acting account
# is derived from the access token. Unknown extra fields are ignored by
# Pydantic, so a caller-supplied `actor_id` cannot influence attribution.


class TicketMutation(BaseModel):
    """Shared optimistic-concurrency precondition for triage mutations.

    The version is a precondition only; authorization always comes from the
    verified account. A stale value is rejected with ``409`` so two operators
    cannot silently overwrite each other's work.
    """

    expected_version: int = Field(
        ge=1,
        description=(
            "`version` of the ticket the client last read. Omit-proof: the "
            "server rejects stale versions and never retries on the caller's "
            "behalf."
        ),
    )


class TicketStatusUpdate(TicketMutation):
    status: TicketStatus = Field(description="New ticket status.")


class TicketPriorityUpdate(TicketMutation):
    priority: TicketPriority = Field(description="New ticket priority.")


class TicketCategoryUpdate(TicketMutation):
    category: TicketCategory = Field(description="New ticket category.")


class TicketAssignmentUpdate(TicketMutation):
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
