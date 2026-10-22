"""Support agents and operational actors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, enum_type
from app.models.enums import AgentRole, SupportTeam

if TYPE_CHECKING:
    from app.models.activity import TicketActivity
    from app.models.reply import CustomerReply
    from app.models.ticket import Ticket


class Agent(TimestampMixin, Base):
    """A support agent or operational user.

    Phase 5 does **not** add authentication. These rows describe the actors
    that appear in assignment and audit records; they are not credentials and
    do not imply production access control.
    """

    __tablename__ = "agents"

    # Stable, human-readable identifier used by the frontend fixtures (AG-01).
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[AgentRole] = mapped_column(
        enum_type(AgentRole, "agent_role"), nullable=False
    )
    team: Mapped[SupportTeam | None] = mapped_column(
        enum_type(SupportTeam, "support_team"), nullable=True
    )
    is_demo_user: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="assigned_agent",
        foreign_keys="Ticket.assigned_agent_id",
    )
    authored_replies: Mapped[list["CustomerReply"]] = relationship(
        back_populates="author",
        foreign_keys="CustomerReply.author_id",
    )
    reviewed_replies: Mapped[list["CustomerReply"]] = relationship(
        back_populates="reviewer",
        foreign_keys="CustomerReply.reviewer_id",
    )
    activities: Mapped[list["TicketActivity"]] = relationship(
        back_populates="actor",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Agent(id={self.id!r}, name={self.name!r})"
