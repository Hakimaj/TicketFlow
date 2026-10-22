"""Internal note services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.common import utcnow
from app.models.enums import ActivityAction
from app.models.note import TicketNote
from app.repositories import activities as activity_repo
from app.repositories import notes as note_repo
from app.schemas.common import PageMeta
from app.schemas.notes import NoteAuthor, NoteCreate, NoteListResponse, NoteResponse
from app.services.agents import resolve_actor
from app.services.common import get_ticket_or_404, transaction


def _to_response(note: TicketNote, ticket_public_id: str) -> NoteResponse:
    return NoteResponse(
        id=str(note.id),
        ticket_id=ticket_public_id,
        content=note.content,
        author=NoteAuthor(id=note.author_id, name=note.author.name),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def create_note(
    db: Session, ticket_id: str, payload: NoteCreate
) -> NoteResponse:
    """Create a note and its required audit event atomically.

    Both rows (plus the ticket's ``updated_at`` touch) are committed together;
    any failure rolls all of them back. The activity stores a fixed summary and
    ``note_id`` only, never the note body.
    """
    ticket = get_ticket_or_404(db, ticket_id)
    actor = resolve_actor(db, payload.actor_id)

    note = note_repo.add_note(
        db, ticket_id=ticket.id, author_id=actor.id, content=payload.content
    )
    ticket.updated_at = utcnow()

    with transaction(db):
        # Flush assigns the UUID and enforces DB constraints before the audit
        # event references it.
        db.flush()
        activity_repo.add_activity(
            db,
            ticket=ticket,
            actor=actor,
            action=ActivityAction.NOTE_ADDED,
            detail="Internal note added.",
            note_id=note.id,
            is_internal_note=True,
        )

    stored = note_repo.get_note(db, note.id)
    if stored is None:  # pragma: no cover - only on a concurrent delete
        raise RuntimeError("The note disappeared immediately after creation.")
    return _to_response(stored, ticket.public_id)


def list_notes(
    db: Session, ticket_id: str, *, page: int, page_size: int
) -> NoteListResponse:
    ticket = get_ticket_or_404(db, ticket_id)
    notes, total = note_repo.list_notes(
        db, ticket.id, page=page, page_size=page_size
    )
    page_count = (total + page_size - 1) // page_size if total else 0
    return NoteListResponse(
        items=[_to_response(note, ticket.public_id) for note in notes],
        pagination=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            page_count=page_count,
        ),
    )
