"""Agent roster response contracts.

No credentials, tokens or password data exist in the model; the roster exposes
only the operational fields the frontend uses to label assignees.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import AgentRole, SupportTeam


class AgentSummary(BaseModel):
    id: str = Field(description="Stable agent identifier, e.g. `AG-02`.")
    name: str
    role: AgentRole
    team: SupportTeam | None
    is_demo_user: bool = Field(
        description=(
            "True for the hard-coded demonstration identity. Not an "
            "authenticated user marker."
        )
    )


class AgentListResponse(BaseModel):
    items: list[AgentSummary]
