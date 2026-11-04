"""Activity history services."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.labels import ACTIVITY_ACTION_LABELS
from app.models.activity import TicketActivity
from app.models.enums import ActivityAction
from app.repositories import activities as activity_repo
from app.repositories.activities import ActivityFilters
from app.schemas.activities import ActivityListResponse, ActivityResponse
from app.schemas.common import PageMeta
from app.schemas.tickets import SortDirection
from app.services.common import get_ticket_or_404


def to_response(activity: TicketActivity) -> ActivityResponse:
    """Privacy-safe projection.

    ``summary`` is the stored concise detail (or the action label when absent).
    Note bodies are never in ``detail``; note events expose only ``note_id``.
    """
    return ActivityResponse(
        id=activity.public_id,
        ticket_id=activity.ticket.public_id,
        reply_id=activity.reply.public_id if activity.reply else None,
        reply_version=activity.reply_version,
        note_id=str(activity.note_id) if activity.note_id else None,
        actor_id=activity.actor_id,
        actor_account_id=(
            str(activity.actor_account_id)
            if activity.actor_account_id
            else None
        ),
        actor_name=activity.actor_name,
        actor_type=activity.actor_type,
        action=activity.action,
        summary=activity.detail or ACTIVITY_ACTION_LABELS[activity.action],
        is_internal_note=activity.is_internal_note,
        created_at=activity.created_at,
    )


def list_ticket_activities(db: Session, ticket_id: str) -> list[ActivityResponse]:
    ticket = get_ticket_or_404(db, ticket_id)
    return [
        to_response(activity)
        for activity in activity_repo.list_for_ticket(db, ticket.id)
    ]


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def list_activities(
    db: Session,
    *,
    ticket_id: str | None,
    actions: tuple[ActivityAction, ...],
    actor_id: str | None,
    search: str | None,
    start: datetime | None,
    end: datetime | None,
    sort_dir: SortDirection,
    page: int,
    page_size: int,
) -> ActivityListResponse:
    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    if start_utc is not None and end_utc is not None and start_utc > end_utc:
        raise ApiError(
            status_code=422,
            code="invalid_query",
            message="`start` must not be after `end`.",
        )

    filters = ActivityFilters(
        ticket_public_id=ticket_id.strip().upper() if ticket_id else None,
        actions=actions,
        actor_id=actor_id.strip().upper() if actor_id else None,
        search=search,
        start=start_utc,
        end=end_utc,
    )
    items, total = activity_repo.list_activities(
        db,
        filters,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    page_count = (total + page_size - 1) // page_size if total else 0
    return ActivityListResponse(
        items=[to_response(activity) for activity in items],
        pagination=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            page_count=page_count,
        ),
    )
