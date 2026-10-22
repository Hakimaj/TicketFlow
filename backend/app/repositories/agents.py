"""Database access for the agent roster."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.enums import AgentRole, SupportTeam


def list_agents(
    db: Session,
    *,
    team: SupportTeam | None = None,
    role: AgentRole | None = None,
) -> list[Agent]:
    stmt = select(Agent)
    if team is not None:
        stmt = stmt.where(Agent.team == team)
    if role is not None:
        stmt = stmt.where(Agent.role == role)
    return list(db.scalars(stmt.order_by(Agent.id.asc())).all())


def get_agent(db: Session, agent_id: str) -> Agent | None:
    return db.get(Agent, agent_id)


def get_demo_agent(db: Session) -> Agent | None:
    """The seeded demo identity used when no actor is supplied.

    This is convenience metadata for local development, not authentication.
    """
    return db.scalars(
        select(Agent)
        .where(Agent.is_demo_user.is_(True))
        .order_by(Agent.id.asc())
        .limit(1)
    ).first()
