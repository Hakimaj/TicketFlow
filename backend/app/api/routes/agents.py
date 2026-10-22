"""Agent roster endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models.enums import AgentRole, SupportTeam
from app.schemas.agents import AgentListResponse
from app.schemas.common import ErrorResponse
from app.services import agents as agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get(
    "",
    response_model=AgentListResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid filter value."},
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
        503: {"model": ErrorResponse, "description": "Database unavailable."},
    },
    summary="List support agents",
    description=(
        "Returns the small operational roster from PostgreSQL, ordered by "
        "agent ID. All seeded agents are assignable; there is no active flag "
        "in the current domain. Work emails and any account/credential data "
        "are not exposed. No pagination is needed for this roster."
    ),
)
def list_agents(
    db: DbSession,
    team: Annotated[
        SupportTeam | None, Query(description="Filter by owning team.")
    ] = None,
    role: Annotated[
        AgentRole | None, Query(description="Filter by operational role.")
    ] = None,
) -> AgentListResponse:
    return agent_service.list_agents(db, team=team, role=role)
