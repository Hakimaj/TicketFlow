"""Shared service helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.models.ticket import Ticket
from app.repositories import tickets as ticket_repo


def get_ticket_or_404(db: Session, ticket_id: str) -> Ticket:
    normalized = ticket_id.strip().upper()
    ticket = ticket_repo.get_ticket_by_public_id(db, normalized)
    if ticket is None:
        raise not_found(
            "ticket_not_found",
            f"Ticket {normalized or ticket_id} was not found.",
        )
    return ticket


def reload_ticket(db: Session, public_id: str) -> Ticket:
    """Re-fetch with requester/assignee eagerly loaded after a commit."""
    ticket = ticket_repo.get_ticket_by_public_id(
        db, public_id, populate_existing=True
    )
    if ticket is None:  # pragma: no cover - only if deleted concurrently
        raise not_found(
            "ticket_not_found", f"Ticket {public_id} was not found."
        )
    return ticket


@contextmanager
def transaction(db: Session) -> Iterator[None]:
    """Commit the unit of work, rolling back every change on any failure.

    The body must stage both the entity change and its required audit event;
    only the successful exit commits, so a failure can never leave one without
    the other.
    """
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise
