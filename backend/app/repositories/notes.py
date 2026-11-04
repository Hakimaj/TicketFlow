"""Database access for internal notes."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.note import TicketNote


def add_note(
    db: Session,
    *,
    ticket_id: uuid.UUID,
    author_id: str,
    content: str,
    author_account_id: uuid.UUID | None = None,
) -> TicketNote:
    note = TicketNote(
        ticket_id=ticket_id,
        author_id=author_id,
        author_account_id=author_account_id,
        content=content,
    )
    db.add(note)
    return note


def get_note(db: Session, note_id: uuid.UUID) -> TicketNote | None:
    return db.scalars(
        select(TicketNote)
        .options(joinedload(TicketNote.author))
        .where(TicketNote.id == note_id)
    ).one_or_none()


def list_notes(
    db: Session, ticket_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[TicketNote], int]:
    total = int(
        db.scalar(
            select(func.count())
            .select_from(TicketNote)
            .where(TicketNote.ticket_id == ticket_id)
        )
        or 0
    )
    stmt = (
        select(TicketNote)
        .options(joinedload(TicketNote.author))
        .where(TicketNote.ticket_id == ticket_id)
        .order_by(TicketNote.created_at.asc(), TicketNote.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).all()), total
