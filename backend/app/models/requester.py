"""Support requesters (the customer side of a ticket)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class Requester(TimestampMixin, Base):
    """Customer identity for a ticket.

    Personally identifying information lives here, not in activity metadata.
    Email is unique so seeding is idempotent and one customer can own several
    tickets without duplicated records.
    """

    __tablename__ = "requesters"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="requester")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Requester(id={self.id!r}, name={self.name!r})"
