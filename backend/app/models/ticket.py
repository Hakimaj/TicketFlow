"""Tickets: the central support record."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, enum_type
from app.models.enums import (
    SupportTeam,
    TicketCategory,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)

if TYPE_CHECKING:
    from app.models.activity import TicketActivity
    from app.models.agent import Agent
    from app.models.note import TicketNote
    from app.models.reply import CustomerReply
    from app.models.requester import Requester


class Ticket(TimestampMixin, Base):
    """A support ticket.

    ``id`` is the internal UUID primary key; ``public_id`` is the stable
    human-facing identifier (``TF-1051``) used by the frontend routes and API
    paths. Keeping them separate lets identifiers survive future renumbering
    rules without changing foreign keys.
    """

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    public_id: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True
    )
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requesters.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    channel: Mapped[TicketChannel] = mapped_column(
        enum_type(TicketChannel, "ticket_channel"), nullable=False
    )
    category: Mapped[TicketCategory] = mapped_column(
        enum_type(TicketCategory, "ticket_category"), nullable=False, index=True
    )
    priority: Mapped[TicketPriority] = mapped_column(
        enum_type(TicketPriority, "ticket_priority"), nullable=False, index=True
    )
    status: Mapped[TicketStatus] = mapped_column(
        enum_type(TicketStatus, "ticket_status"), nullable=False, index=True
    )

    assigned_team: Mapped[SupportTeam | None] = mapped_column(
        enum_type(SupportTeam, "support_team"), nullable=True
    )
    assigned_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suggested_category: Mapped[TicketCategory | None] = mapped_column(
        enum_type(TicketCategory, "ticket_category"), nullable=True
    )
    suggested_priority: Mapped[TicketPriority | None] = mapped_column(
        enum_type(TicketPriority, "ticket_priority"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    requester: Mapped["Requester"] = relationship(back_populates="tickets")
    assigned_agent: Mapped["Agent | None"] = relationship(
        back_populates="assigned_tickets",
        foreign_keys=[assigned_agent_id],
    )
    replies: Mapped[list["CustomerReply"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notes: Mapped[list["TicketNote"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    activities: Mapped[list["TicketActivity"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("length(btrim(subject)) > 0", name="subject_not_blank"),
        CheckConstraint("public_id LIKE 'TF-%'", name="public_id_prefixed"),
        Index("ix_tickets_status_created_at", "status", "created_at"),
        Index("ix_tickets_assigned_agent_status", "assigned_agent_id", "status"),
        Index("ix_tickets_created_at", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Ticket(public_id={self.public_id!r}, status={self.status!r})"
