"""Customer reply workflow contracts.

Serialized enum values match the frontend `ReplyState` union exactly. Reviewer
comments are internal: they are returned on staff-facing reply detail/review
history only, never merged into the reply body and never exposed as
customer-facing content.

Field names are snake_case in HTTP; the camelCase frontend mapping is documented
in ``docs/frontend-backend-integration.md``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    ReplyReviewDecision,
    ReplyState,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.models.reply import REPLY_MAX_LENGTH, REVIEW_COMMENT_MAX_LENGTH
from app.schemas.common import PageMeta, UtcDatetime


class ReplyActor(BaseModel):
    id: str
    name: str


class ReplyRecipient(BaseModel):
    """Customer context derived from the ticket's requester.

    The caller cannot supply a recipient; it always comes from the associated
    ticket, so a reply can never be addressed to a different customer.
    """

    name: str
    email: str


# Request bodies never accept an actor, reviewer or role: attribution always
# comes from the verified access token. Extra client fields are ignored.


class _BodyPayload(BaseModel):
    body: str = Field(
        min_length=1,
        max_length=REPLY_MAX_LENGTH,
        description=(
            "Reply text. Surrounding whitespace is trimmed. Empty or "
            "whitespace-only bodies are rejected (matching the frontend "
            "demo service)."
        ),
    )

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Reply text cannot be empty.")
        if len(trimmed) > REPLY_MAX_LENGTH:
            raise ValueError(
                f"Reply text must be at most {REPLY_MAX_LENGTH} characters."
            )
        return trimmed


class ReplyCreate(_BodyPayload):
    """Create the ticket's single active reply draft."""


class ReplyUpdate(_BodyPayload):
    """Edit the current reply, creating a new revision when the body changes."""


class ReplySubmit(BaseModel):
    """Submit the current revision for human approval.

    Intentionally empty: the submitter is the authenticated account.
    """


class ReplyReviewRequest(BaseModel):
    version: int = Field(
        ge=1,
        description=(
            "Exact revision version being reviewed. A stale value is rejected "
            "with a 409 `reply_version_conflict`."
        ),
    )


class ReplyApprove(ReplyReviewRequest):
    comment: str | None = Field(
        default=None,
        max_length=REVIEW_COMMENT_MAX_LENGTH,
        description="Optional internal approval note. Never customer-visible.",
    )

    @field_validator("comment")
    @classmethod
    def _normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ReplyRequestChanges(ReplyReviewRequest):
    comment: str = Field(
        min_length=1,
        max_length=REVIEW_COMMENT_MAX_LENGTH,
        description=(
            "Required internal reviewer feedback explaining the requested "
            "revisions. Stored with the review decision; never sent to the "
            "customer."
        ),
    )

    @field_validator("comment")
    @classmethod
    def _validate_comment(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError(
                "Internal reviewer feedback explaining the requested revisions "
                "is required."
            )
        if len(trimmed) > REVIEW_COMMENT_MAX_LENGTH:
            raise ValueError(
                "Internal reviewer feedback must be at most "
                f"{REVIEW_COMMENT_MAX_LENGTH} characters."
            )
        return trimmed


class ReplySendDemo(BaseModel):
    """Explicitly mark an approved revision as sent in demo mode.

    Intentionally empty: the acting account is the authenticated principal.
    """


class ReplyRevisionResponse(BaseModel):
    id: str = Field(description="Opaque revision UUID.")
    version: int
    body: str
    author: ReplyActor
    created_at: UtcDatetime


class ReplyReviewResponse(BaseModel):
    id: str = Field(description="Opaque review-decision UUID.")
    decision: ReplyReviewDecision
    version: int = Field(description="Exact revision version reviewed.")
    reviewer_id: str | None
    reviewer_name: str
    comment: str | None = Field(
        default=None,
        description=(
            "Internal reviewer feedback. Never customer-visible and never "
            "included in general activity summaries."
        ),
    )
    created_at: UtcDatetime


class ReplySummary(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "REP-4F2A9C1B7D3E",
                "ticket_id": "TF-1051",
                "author": {"id": "AG-02", "name": "Hana Tesfaye"},
                "recipient": {
                    "name": "Marta Alemu",
                    "email": "marta.alemu@myetmail.example",
                },
                "body": "Dear Marta, ...",
                "state": "pending_approval",
                "version": 1,
                "submitted_at": "2026-10-21T11:36:00.000Z",
                "submitted_version": 1,
                "reviewed_at": None,
                "reviewer_id": None,
                "reviewer_name": None,
                "reviewer_feedback": None,
                "approved_version": None,
                "sent_at": None,
                "sent_by_actor_name": None,
                "created_at": "2026-10-21T11:06:00.000Z",
                "updated_at": "2026-10-21T11:36:00.000Z",
            }
        }
    )

    id: str = Field(description="Public reply identifier, e.g. `REP-101`.")
    ticket_id: str = Field(description="Public ticket identifier.")
    author: ReplyActor
    recipient: ReplyRecipient
    body: str = Field(description="Current revision body.")
    state: ReplyState
    version: int = Field(description="Current revision version.")
    submitted_at: UtcDatetime | None
    submitted_version: int | None = Field(
        default=None,
        description="Version explicitly submitted for review, when applicable.",
    )
    reviewed_at: UtcDatetime | None
    reviewer_id: str | None
    reviewer_name: str | None
    reviewer_feedback: str | None = Field(
        default=None,
        description=(
            "Current internal reviewer feedback, if changes were requested. "
            "Never customer-visible."
        ),
    )
    approved_version: int | None = Field(
        default=None,
        description=(
            "Exact version a human approved. Only this version may be marked "
            "as sent in demo mode."
        ),
    )
    sent_at: UtcDatetime | None
    sent_by_actor_name: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class ReplyDetail(ReplySummary):
    revisions: list[ReplyRevisionResponse] = Field(
        description="Immutable revision history, oldest version first."
    )
    reviews: list[ReplyReviewResponse] = Field(
        description="Append-only human review decisions, oldest first."
    )


class ReplyListResponse(BaseModel):
    items: list[ReplySummary]
    pagination: PageMeta


class ReplyQueueItem(BaseModel):
    """One logical reply awaiting human approval."""

    reply_id: str
    ticket_id: str
    ticket_subject: str
    ticket_category: TicketCategory
    ticket_priority: TicketPriority
    ticket_status: TicketStatus
    requester_name: str
    author: ReplyActor
    version: int = Field(description="Current (submitted) version.")
    submitted_version: int | None
    submitted_at: UtcDatetime | None
    preview: str = Field(
        description=(
            "Whitespace-collapsed, length-limited preview of the submitted "
            "revision. Fetch the reply detail for the full text."
        )
    )
    state: ReplyState


class ReplyQueueResponse(BaseModel):
    items: list[ReplyQueueItem]
    pagination: PageMeta


class ReplyTicketRef(BaseModel):
    """Compact parent-ticket view for cross-resource reply listings."""

    id: str
    subject: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    requester_name: str
    created_at: UtcDatetime


class ReplyWithTicketItem(BaseModel):
    """One logical reply paired with its joined parent ticket.

    Powers the approvals workspace: every reply state is included so the UI
    can show draft, pending, approved, changes-requested and sent records
    without issuing one request per ticket.
    """

    reply: ReplySummary
    ticket: ReplyTicketRef


class ReplyAllListResponse(BaseModel):
    items: list[ReplyWithTicketItem]
    pagination: PageMeta


class ReplySendResult(BaseModel):
    reply: ReplyDetail
    delivery: str = Field(
        default="demo_marked_sent",
        description=(
            "Stable machine value: the application recorded a simulated send. "
            "It is not proof of delivery."
        ),
    )
    notice: str = Field(
        default=(
            "The reply was marked as sent in demo mode. No email, SMS or other "
            "customer message was delivered."
        ),
        description="Human-readable clarification of the demo-send semantics.",
    )


__all__ = [
    "ReplyActor",
    "ReplyAllListResponse",
    "ReplyTicketRef",
    "ReplyWithTicketItem",
    "ReplyApprove",
    "ReplyCreate",
    "ReplyDetail",
    "ReplyListResponse",
    "ReplyQueueItem",
    "ReplyQueueResponse",
    "ReplyRecipient",
    "ReplyRequestChanges",
    "ReplyReviewRequest",
    "ReplyReviewResponse",
    "ReplyRevisionResponse",
    "ReplySendDemo",
    "ReplySendResult",
    "ReplySubmit",
    "ReplySummary",
    "ReplyUpdate",
]
