"""Customer replies and their approval workflow metadata."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, enum_type
from app.models.enums import ReplyState

if TYPE_CHECKING:
    from app.models.activity import TicketActivity
    from app.models.agent import Agent
    from app.models.ticket import Ticket


class CustomerReply(TimestampMixin, Base):
    """A customer-visible reply draft and its review/send metadata.

    Reply state transitions are **not** implemented as API operations in this
    phase; the schema stores the full information the later workflow API needs.
    ``reviewer_feedback`` is internal and must never be projected into a
    customer-visible response.
    """

    __tablename__ = "customer_replies"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    public_id: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[ReplyState] = mapped_column(
        enum_type(ReplyState, "reply_state"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewer_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Snapshot of the reviewer's display name for historical audit display.
    reviewer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reviewer_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_by_actor_name: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="replies")
    author: Mapped["Agent"] = relationship(
        back_populates="authored_replies", foreign_keys=[author_id]
    )
    reviewer: Mapped["Agent | None"] = relationship(
        back_populates="reviewed_replies", foreign_keys=[reviewer_id]
    )
    activities: Mapped[list["TicketActivity"]] = relationship(
        back_populates="reply", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "state <> 'sent' OR (reviewed_at IS NOT NULL AND sent_at IS NOT NULL)",
            name="sent_requires_review",
        ),
        CheckConstraint(
            "sent_at IS NULL OR state = 'sent'", name="sent_state_matches"
        ),
        CheckConstraint("public_id LIKE 'REP-%'", name="public_id_prefixed"),
        # One in-flight reply per ticket; sent replies are immutable history and
        # a new reply record starts afterwards (matches the frontend workflow).
        Index(
            "uq_customer_replies_one_active_per_ticket",
            "ticket_id",
            unique=True,
            postgresql_where=text("state <> 'sent'"),
        ),
        Index("ix_customer_replies_ticket_state", "ticket_id", "state"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"CustomerReply(public_id={self.public_id!r}, state={self.state!r})"
