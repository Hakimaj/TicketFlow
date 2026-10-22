"""Activity history endpoints (ticket-scoped and global)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.api.params import TicketIdPath
from app.models.enums import ActivityAction
from app.schemas.activities import ActivityListResponse, ActivityResponse
from app.schemas.common import ErrorResponse
from app.schemas.tickets import SortDirection
from app.services import activities as activity_service

ticket_router = APIRouter(
    prefix="/tickets/{ticket_id}/activities", tags=["activities"]
)
global_router = APIRouter(prefix="/activities", tags=["activities"])

_ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Unknown ticket ID."},
    422: {"model": ErrorResponse, "description": "Invalid query parameters."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@ticket_router.get(
    "",
    response_model=list[ActivityResponse],
    responses=_ERROR_RESPONSES,
    summary="List activity for one ticket",
    description=(
        "Returns that ticket's persisted events oldest first, with a stable "
        "`public_id` tiebreak. Internal note bodies are not included; note "
        "events expose `note_id` and a safe summary."
    ),
)
def list_ticket_activities(
    db: DbSession, ticket_id: TicketIdPath
) -> list[ActivityResponse]:
    return activity_service.list_ticket_activities(db, ticket_id)


@global_router.get(
    "",
    response_model=ActivityListResponse,
    responses=_ERROR_RESPONSES,
    summary="List activity across tickets",
    description=(
        "Server-side filtered, sorted and paginated audit log. `start` is "
        "inclusive and `end` is exclusive (UTC); both accept ISO 8601. "
        "Search matches ticket ID, actor, action value/label and the safe "
        "summary, never note bodies. Ties on `created_at` are ordered by "
        "public activity ID ascending."
    ),
)
def list_activities(
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Events per page (1–100).")
    ] = 20,
    ticket_id: Annotated[
        str | None,
        Query(max_length=32, description="Filter to one public ticket ID."),
    ] = None,
    action: Annotated[
        list[ActivityAction] | None,
        Query(description="Filter by one or more activity actions."),
    ] = None,
    actor_id: Annotated[
        str | None,
        Query(max_length=16, description="Filter by agent identifier."),
    ] = None,
    search: Annotated[
        str | None,
        Query(
            max_length=120,
            description=(
                "Case-insensitive match on ticket ID, actor, action label or "
                "safe summary."
            ),
        ),
    ] = None,
    start: Annotated[
        datetime | None,
        Query(description="Inclusive lower bound (ISO 8601, UTC assumed)."),
    ] = None,
    end: Annotated[
        datetime | None,
        Query(description="Exclusive upper bound (ISO 8601, UTC assumed)."),
    ] = None,
    sort_dir: Annotated[
        SortDirection,
        Query(description="`desc` (newest first) or `asc` (oldest first)."),
    ] = SortDirection.DESC,
) -> ActivityListResponse:
    return activity_service.list_activities(
        db,
        ticket_id=ticket_id,
        actions=tuple(action or ()),
        actor_id=actor_id,
        search=search,
        start=start,
        end=end,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
