"""Internal note endpoints (staff-only; not customer replies)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession
from app.api.params import TicketIdPath
from app.schemas.common import ErrorResponse
from app.schemas.notes import NoteCreate, NoteListResponse, NoteResponse
from app.services import notes as note_service

router = APIRouter(prefix="/tickets/{ticket_id}/notes", tags=["notes"])

_ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Unknown ticket ID."},
    422: {"model": ErrorResponse, "description": "Invalid note or pagination."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES,
    summary="Add an internal note",
    description=(
        "Creates a dedicated note record and its audit event atomically. The "
        "audit summary never contains the note body; the event links to the "
        "note via `note_id`. Notes are not customer replies and are never "
        "sent.\n\n"
        "`actor_id` is development-only metadata and is not an authenticated "
        "identity; it defaults to the seeded demo agent."
    ),
)
def create_note(
    db: DbSession, ticket_id: TicketIdPath, payload: NoteCreate
) -> NoteResponse:
    return note_service.create_note(db, ticket_id, payload)


@router.get(
    "",
    response_model=NoteListResponse,
    responses=_ERROR_RESPONSES,
    summary="List internal notes",
    description=(
        "Returns notes for this ticket only, oldest first, with stable "
        "pagination. Customer replies are a separate resource and are never "
        "returned here."
    ),
)
def list_notes(
    db: DbSession,
    ticket_id: TicketIdPath,
    page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Notes per page (1–100).")
    ] = 20,
) -> NoteListResponse:
    return note_service.list_notes(
        db, ticket_id, page=page, page_size=page_size
    )
