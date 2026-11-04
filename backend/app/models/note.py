"""Internal staff notes.

Notes are **not** customer replies: they are never sent, never visible to
customers, and have their own record. The corresponding audit event stores only
a safe summary plus ``note_id`` so note bodies stay out of general operational
metadata.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:
    from app.models.activity import TicketActivity
    from app.models.agent import Agent
    from app.models.ticket import Ticket

NOTE_MAX_LENGTH = 4000


class TicketNote(TimestampMixin, Base):
    """A persisted internal note attached to one ticket."""

    __tablename__ = "ticket_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    author_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="notes")
    author: Mapped["Agent"] = relationship()
    activities: Mapped[list["TicketActivity"]] = relationship(
        back_populates="note", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("length(btrim(content)) > 0", name="content_not_blank"),
        CheckConstraint(
            f"length(content) <= {NOTE_MAX_LENGTH}", name="content_max_length"
        ),
        Index("ix_ticket_notes_ticket_created", "ticket_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"TicketNote(id={self.id!r}, ticket_id={self.ticket_id!r})"


__all__ = ["NOTE_MAX_LENGTH", "TicketNote"]
