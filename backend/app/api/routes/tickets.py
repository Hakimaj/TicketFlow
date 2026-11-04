"""Read-only ticket endpoints (Phase 5)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.api.params import TicketIdPath
from app.authorization import (
    CanCreateTickets,
    CanReadOperations,
    CanTriage,
    CurrentAccount,
)
from app.core.errors import ApiError
from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.repositories.tickets import TicketFilters
from app.schemas.common import ErrorResponse
from app.schemas.tickets import (
    SortDirection,
    TicketAssignmentUpdate,
    TicketCategoryUpdate,
    TicketCreate,
    TicketDetail,
    TicketListResponse,
    TicketPriorityUpdate,
    TicketSortField,
    TicketStatusUpdate,
)
from app.services import tickets as ticket_service
from app.services.auth import principal_for

router = APIRouter(prefix="/tickets", tags=["tickets"])

_LIST_ERROR_RESPONSES = {
    422: {"model": ErrorResponse, "description": "Invalid query parameters."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.get(
    "",
    response_model=TicketListResponse,
    responses=_LIST_ERROR_RESPONSES,
    dependencies=[CanReadOperations],
    summary="List tickets",
    description=(
        "Server-side search, filtering, sorting and pagination over persisted "
        "tickets. All filters are optional and combine with AND.\n\n"
        "Multi-value filters accept repeated parameters, e.g. "
        "`?status=open&status=pending`."
    ),
)
def list_tickets(
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Items per page (1–100).")
    ] = 20,
    search: Annotated[
        str | None,
        Query(
            max_length=120,
            description=(
                "Case-insensitive match on ticket ID, subject or requester name."
            ),
        ),
    ] = None,
    status: Annotated[
        list[TicketStatus] | None,
        Query(description="Filter by one or more ticket statuses."),
    ] = None,
    priority: Annotated[
        list[TicketPriority] | None,
        Query(description="Filter by one or more priorities."),
    ] = None,
    category: Annotated[
        list[TicketCategory] | None,
        Query(description="Filter by one or more categories."),
    ] = None,
    assigned_agent_id: Annotated[
        str | None,
        Query(
            max_length=16,
            description="Assigned agent identifier, e.g. `AG-02`.",
        ),
    ] = None,
    unassigned: Annotated[
        bool,
        Query(
            description=(
                "When true, return only tickets with no assigned agent. "
                "Cannot be combined with `assigned_agent_id`."
            )
        ),
    ] = False,
    sort_by: Annotated[
        TicketSortField, Query(description="Permitted sort field.")
    ] = TicketSortField.CREATED_AT,
    sort_dir: Annotated[
        SortDirection, Query(description="Sort direction.")
    ] = SortDirection.DESC,
) -> TicketListResponse:
    if unassigned and assigned_agent_id:
        raise ApiError(
            status_code=422,
            code="invalid_query",
            message="`unassigned` and `assigned_agent_id` cannot be combined.",
        )

    filters = TicketFilters(
        search=search,
        statuses=tuple(status or ()),
        categories=tuple(category or ()),
        priorities=tuple(priority or ()),
        assigned_agent_id=assigned_agent_id.strip() if assigned_agent_id else None,
        unassigned_only=unassigned,
    )
    return ticket_service.list_tickets(
        db,
        filters,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketDetail,
    responses={
        404: {"model": ErrorResponse, "description": "Unknown ticket ID."},
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
        503: {"model": ErrorResponse, "description": "Database unavailable."},
    },
    dependencies=[CanReadOperations],
    summary="Get one ticket",
    description=(
        "Returns the persisted ticket, its requester summary and triage "
        "metadata. Replies and activity are not embedded in this phase."
    ),
)
def get_ticket(db: DbSession, ticket_id: TicketIdPath) -> TicketDetail:
    return ticket_service.get_ticket(db, ticket_id)


# ---------------------------------------------------------------------------
# Intake (Phase 10)
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=201,
    response_model=TicketDetail,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "The account may not create tickets.",
        },
        409: {
            "model": ErrorResponse,
            "description": "A concurrent write prevented creation; retry.",
        },
        422: {"model": ErrorResponse, "description": "Invalid request body."},
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
        503: {"model": ErrorResponse, "description": "Database unavailable."},
    },
    dependencies=[CanCreateTickets],
    summary="Create a ticket",
    description=(
        "Creates a persisted ticket, reusing an existing requester with the "
        "same email, and writes its `created` audit event in the same "
        "transaction.\n\n"
        "The creator is taken from the access token; the body has no actor, "
        "status or version field. A new ticket starts as `new`, is routed to "
        "the category's owning team and gets an 8-hour target only for "
        "`urgent`/`high` priority.\n\n"
        "Returns `201` with the created ticket, including the `version` the "
        "next triage mutation must send as `expected_version`."
    ),
)
def create_ticket(
    db: DbSession, account: CurrentAccount, payload: TicketCreate
) -> TicketDetail:
    return ticket_service.create_ticket(
        db, payload, principal=principal_for(account)
    )


# ---------------------------------------------------------------------------
# Persisted triage mutations (Phase 6)
# ---------------------------------------------------------------------------

_MUTATION_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Unknown ticket ID."},
    409: {
        "model": ErrorResponse,
        "description": (
            "`expected_version` is stale; reload the ticket and reapply."
        ),
    },
    422: {"model": ErrorResponse, "description": "Invalid field or reference."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.patch(
    "/{ticket_id}/status",
    response_model=TicketDetail,
    responses=_MUTATION_RESPONSES,
    dependencies=[CanTriage],
    summary="Update ticket status",
    description=(
        "Persists a new status and writes one audit event in the same "
        "transaction. `expected_version` is required: a stale version returns "
        "`409 ticket_version_conflict` and nothing is written. Repeating the "
        "current status is a no-op: no event, no version bump and no "
        "`updated_at` change. Moving to `resolved`/`closed` clears `due_at`. "
        "The acting account is derived from the access token, never the body."
    ),
)
def update_ticket_status(
    db: DbSession,
    account: CurrentAccount,
    ticket_id: TicketIdPath,
    payload: TicketStatusUpdate,
) -> TicketDetail:
    return ticket_service.update_status(
        db,
        ticket_id,
        payload.status,
        expected_version=payload.expected_version,
        principal=principal_for(account),
    )


@router.patch(
    "/{ticket_id}/priority",
    response_model=TicketDetail,
    responses=_MUTATION_RESPONSES,
    dependencies=[CanTriage],
    summary="Update ticket priority",
    description=(
        "Active `urgent`/`high` tickets receive an 8-hour target from now; "
        "other priorities clear it. Terminal tickets keep their existing "
        "`due_at`. Unchanged priority is a no-op. `expected_version` is "
        "required and a stale value returns `409`."
    ),
)
def update_ticket_priority(
    db: DbSession,
    account: CurrentAccount,
    ticket_id: TicketIdPath,
    payload: TicketPriorityUpdate,
) -> TicketDetail:
    return ticket_service.update_priority(
        db,
        ticket_id,
        payload.priority,
        expected_version=payload.expected_version,
        principal=principal_for(account),
    )


@router.patch(
    "/{ticket_id}/category",
    response_model=TicketDetail,
    responses=_MUTATION_RESPONSES,
    dependencies=[CanTriage],
    summary="Update ticket category",
    description=(
        "Re-routes `assigned_team` using the authoritative category→team "
        "mapping. An existing agent assignment is preserved; reassign the "
        "agent separately if needed. Unchanged category is a no-op. "
        "`expected_version` is required and a stale value returns `409`."
    ),
)
def update_ticket_category(
    db: DbSession,
    account: CurrentAccount,
    ticket_id: TicketIdPath,
    payload: TicketCategoryUpdate,
) -> TicketDetail:
    return ticket_service.update_category(
        db,
        ticket_id,
        payload.category,
        expected_version=payload.expected_version,
        principal=principal_for(account),
    )


@router.patch(
    "/{ticket_id}/assignment",
    response_model=TicketDetail,
    responses=_MUTATION_RESPONSES,
    dependencies=[CanTriage],
    summary="Assign or unassign a ticket",
    description=(
        "Assigns any existing agent. `agent_id` is required and nullable: "
        "send `null` to unassign explicitly. The category-derived team is not "
        "changed by assignment. Repeating the current assignee is a no-op. "
        "`expected_version` is required and a stale value returns `409`."
    ),
)
def update_ticket_assignment(
    db: DbSession,
    account: CurrentAccount,
    ticket_id: TicketIdPath,
    payload: TicketAssignmentUpdate,
) -> TicketDetail:
    return ticket_service.update_assignment(
        db,
        ticket_id,
        payload.agent_id,
        expected_version=payload.expected_version,
        principal=principal_for(account),
    )
