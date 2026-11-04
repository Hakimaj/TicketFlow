"""Structured ticket and reply activity / audit events."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_type
from app.models.enums import ActivityAction, ActivityActorType

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.note import TicketNote
    from app.models.reply import CustomerReply
    from app.models.ticket import Ticket


class TicketActivity(Base):
    """An audit record for one domain operation.

    ``detail`` is a short operational description for the ticket workspace. It
    must not contain customer message bodies, customer email addresses or the
    body of an internal note. ``note_added`` events store a fixed summary and
    point at the note via ``note_id``; the note text lives only in
    ``ticket_notes``. ``is_internal_note`` marks the event for sanitized
    projections.

    Activity rows are append-only by convention; no update/delete API exists.
    """

    __tablename__ = "ticket_activities"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    public_id: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reply_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customer_replies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Exact reply revision the event refers to, when applicable. Together with
    # ``reply_id`` this ties an audit event to immutable revision history.
    reply_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ticket_notes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Verified account that performed the action. Null for historical events.
    actor_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Snapshot of the actor label, including non-agent actors such as the
    # classification service. Never stores credentials or customer PII.
    actor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    actor_type: Mapped[ActivityActorType] = mapped_column(
        enum_type(ActivityActorType, "activity_actor_type"), nullable=False
    )
    action: Mapped[ActivityAction] = mapped_column(
        enum_type(ActivityAction, "activity_action"), nullable=False, index=True
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_internal_note: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="activities")
    reply: Mapped["CustomerReply | None"] = relationship(
        back_populates="activities"
    )
    note: Mapped["TicketNote | None"] = relationship(back_populates="activities")
    actor: Mapped["Agent | None"] = relationship(back_populates="activities")

    __table_args__ = (
        CheckConstraint(
            "public_id LIKE 'ACT-%'", name="public_id_prefixed"
        ),
        Index("ix_ticket_activities_ticket_created", "ticket_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"TicketActivity(public_id={self.public_id!r}, action={self.action!r})"
