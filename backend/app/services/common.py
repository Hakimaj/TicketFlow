"""Shared service helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.models.ticket import Ticket
from app.repositories import tickets as ticket_repo
from app.schemas.common import serialize_utc_datetime


def ticket_version_conflict(ticket: Ticket, expected_version: int) -> ApiError:
    """409 for a stale optimistic-concurrency precondition.

    The response carries the current version and timestamp so the client can
    explain what happened without another round-trip; it never carries
    authorization information and the caller is not retried automatically.
    """
    return ApiError(
        status_code=409,
        code="ticket_version_conflict",
        message=(
            f"Ticket {ticket.public_id} changed since you loaded it. "
            "Reload the ticket and apply your change again."
        ),
        details=[
            {
                "field": "expected_version",
                "message": (
                    f"Expected version {expected_version} but the ticket is "
                    f"already at version {ticket.version}."
                ),
                "expected_version": expected_version,
                "current_version": ticket.version,
                "updated_at": serialize_utc_datetime(ticket.updated_at),
            }
        ],
    )


def get_ticket_or_404(
    db: Session,
    ticket_id: str,
    *,
    expected_version: int | None = None,
    for_update: bool = False,
) -> Ticket:
    """Load a ticket, optionally locking it and enforcing its version.

    ``for_update`` takes a row lock so the version comparison and the write
    that follows are atomic: a second operator waits, then sees the committed
    version and is rejected with 409 instead of overwriting the first change.
    """
    normalized = ticket_id.strip().upper()
    if for_update:
        ticket = ticket_repo.get_ticket_for_update(db, normalized)
    else:
        ticket = ticket_repo.get_ticket_by_public_id(db, normalized)
    if ticket is None:
        raise not_found(
            "ticket_not_found",
            f"Ticket {normalized or ticket_id} was not found.",
        )
    if expected_version is not None and ticket.version != expected_version:
        raise ticket_version_conflict(ticket, expected_version)
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
