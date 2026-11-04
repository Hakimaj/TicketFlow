"""Activity/audit response contracts.

``summary`` is a short operational description. It never contains customer
message bodies, customer email addresses or internal note text; note events
reference the note through ``note_id`` instead.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActivityAction, ActivityActorType
from app.schemas.common import PageMeta, UtcDatetime


class ActivityResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "ACT-040",
                "ticket_id": "TF-1051",
                "reply_id": None,
                "reply_version": None,
                "note_id": None,
                "actor_id": "AG-02",
                "actor_account_id": "0d4f0b6e-8a51-4c47-9d2b-1f0a2c3d4e5f",
                "actor_name": "Hana Tesfaye",
                "actor_type": "agent",
                "action": "assigned",
                "summary": "Claimed for Billing triage; duplicate-charge form sent to requester.",
                "is_internal_note": False,
                "created_at": "2026-10-21T11:36:00.000Z",
            }
        }
    )

    id: str = Field(description="Public activity identifier, e.g. `ACT-040`.")
    ticket_id: str = Field(description="Public ticket identifier.")
    reply_id: str | None = Field(
        default=None, description="Public reply identifier when reply-related."
    )
    reply_version: int | None = Field(
        default=None,
        description=(
            "Exact reply revision this event refers to, when applicable."
        ),
    )
    note_id: str | None = Field(
        default=None, description="Note UUID when the event was a note addition."
    )
    actor_id: str | None = Field(
        default=None,
        description="Agent identifier when the actor is a known agent.",
    )
    actor_account_id: str | None = Field(
        default=None,
        description=(
            "Verified account that performed the action. Null for historical "
            "events recorded before authentication existed."
        ),
    )
    actor_name: str = Field(description="Actor display label snapshot.")
    actor_type: ActivityActorType
    action: ActivityAction
    summary: str = Field(description="Privacy-safe operational description.")
    is_internal_note: bool
    created_at: UtcDatetime


class ActivityListResponse(BaseModel):
    items: list[ActivityResponse]
    pagination: PageMeta
