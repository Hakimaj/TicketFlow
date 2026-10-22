"""Agent lookup and development-only actor resolution."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.agent import Agent
from app.models.enums import AgentRole, SupportTeam
from app.repositories import agents as agent_repo
from app.schemas.agents import AgentListResponse, AgentSummary


def to_summary(agent: Agent) -> AgentSummary:
    return AgentSummary(
        id=agent.id,
        name=agent.name,
        role=agent.role,
        team=agent.team,
        is_demo_user=agent.is_demo_user,
    )


def list_agents(
    db: Session,
    *,
    team: SupportTeam | None = None,
    role: AgentRole | None = None,
) -> AgentListResponse:
    agents = agent_repo.list_agents(db, team=team, role=role)
    return AgentListResponse(items=[to_summary(agent) for agent in agents])


def resolve_actor(db: Session, actor_id: str | None) -> Agent:
    """Resolve the actor recorded in an audit event.

    Without authentication this is **not** a verified identity: the caller can
    supply any existing agent ID. An omitted ID falls back to the seeded demo
    agent. Both paths are documented as development-only.
    """
    if actor_id:
        normalized = actor_id.strip().upper()
        agent = agent_repo.get_agent(db, normalized)
        if agent is None:
            raise ApiError(
                status_code=422,
                code="invalid_actor",
                message=f"Actor {normalized} does not exist.",
            )
        return agent

    demo_agent = agent_repo.get_demo_agent(db)
    if demo_agent is None:
        raise ApiError(
            status_code=422,
            code="actor_unavailable",
            message=(
                "No demo actor is configured. Supply actor_id or seed the "
                "development agents."
            ),
        )
    return demo_agent
