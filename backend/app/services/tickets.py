"""Ticket read and mutation services.

Mutation rules mirror the existing frontend `DemoTicketService` unless noted:

- status: `resolved` clears `due_at`; terminal statuses stay terminal for SLA
  purposes; status events use `resolved`, `review_flagged` or `status_changed`;
- priority: active urgent/high tickets get an 8-hour target from now, other
  priorities clear it; terminal tickets keep their existing `due_at`;
- category: the category→team mapping is authoritative and updates
  `assigned_team`, but an explicit agent assignment is preserved;
- assignment: any existing agent is assignable; changing the agent does not
  rewrite the team (team remains category-derived);
- unchanged requests are no-ops: no audit event and no `updated_at` change.

Each successful mutation commits the ticket change and its activity event in
one transaction. Failures roll both back.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.labels import (
    CATEGORY_LABELS,
    CATEGORY_TEAM,
    PRIORITY_LABELS,
    STATUS_LABELS,
    TEAM_LABELS,
)
from app.models.common import utcnow
from app.models.enums import (
    ActivityAction,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.models.ticket import Ticket
from app.repositories import activities as activity_repo
from app.repositories import agents as agent_repo
from app.repositories import tickets as ticket_repo
from app.repositories.tickets import TicketFilters
from app.schemas.common import PageMeta
from app.schemas.tickets import (
    RequesterSummary,
    SortDirection,
    TicketDetail,
    TicketListResponse,
    TicketSortField,
    TicketSummary,
)
from app.services.agents import resolve_actor
from app.services.common import get_ticket_or_404, reload_ticket, transaction

_TERMINAL_STATUSES = (TicketStatus.RESOLVED, TicketStatus.CLOSED)
_SLA_TARGET = timedelta(hours=8)


# ---------------------------------------------------------------------------
# Read mapping
# ---------------------------------------------------------------------------


def to_summary(ticket: Ticket) -> TicketSummary:
    """Map a ticket row to the queue/list contract.

    Requester email and message body are deliberately omitted here: they are
    only exposed by the detail endpoint.
    """
    agent = ticket.assigned_agent
    return TicketSummary(
        id=ticket.public_id,
        subject=ticket.subject,
        requester_name=ticket.requester.name,
        channel=ticket.channel,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        assigned_team=ticket.assigned_team,
        assigned_agent_id=agent.id if agent else None,
        assigned_agent_name=agent.name if agent else None,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def to_detail(ticket: Ticket) -> TicketDetail:
    summary = to_summary(ticket)
    return TicketDetail(
        **summary.model_dump(),
        description=ticket.description,
        requester=RequesterSummary(
            id=str(ticket.requester.id),
            name=ticket.requester.name,
            email=ticket.requester.email,
        ),
        due_at=ticket.due_at,
        suggested_category=ticket.suggested_category,
        suggested_priority=ticket.suggested_priority,
        review_note=ticket.review_note,
    )


def list_tickets(
    db: Session,
    filters: TicketFilters,
    *,
    sort_by: TicketSortField,
    sort_dir: SortDirection,
    page: int,
    page_size: int,
) -> TicketListResponse:
    items, total = ticket_repo.list_tickets(
        db,
        filters,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    page_count = (total + page_size - 1) // page_size if total else 0
    return TicketListResponse(
        items=[to_summary(ticket) for ticket in items],
        pagination=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            page_count=page_count,
        ),
    )


def get_ticket(db: Session, ticket_id: str) -> TicketDetail:
    return to_detail(get_ticket_or_404(db, ticket_id))


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def update_status(
    db: Session,
    ticket_id: str,
    new_status: TicketStatus,
    *,
    actor_id: str | None = None,
) -> TicketDetail:
    ticket = get_ticket_or_404(db, ticket_id)
    actor = resolve_actor(db, actor_id)

    if ticket.status is new_status:
        return to_detail(ticket)

    previous = ticket.status
    ticket.status = new_status
    ticket.updated_at = utcnow()
    if new_status in _TERMINAL_STATUSES:
        ticket.due_at = None

    if new_status is TicketStatus.RESOLVED:
        action = ActivityAction.RESOLVED
    elif new_status is TicketStatus.NEEDS_REVIEW:
        action = ActivityAction.REVIEW_FLAGGED
    else:
        action = ActivityAction.STATUS_CHANGED

    with transaction(db):
        activity_repo.add_activity(
            db,
            ticket=ticket,
            actor=actor,
            action=action,
            detail=(
                f"Status changed from {STATUS_LABELS[previous]} "
                f"to {STATUS_LABELS[new_status]}."
            ),
        )
    return to_detail(reload_ticket(db, ticket.public_id))


def update_priority(
    db: Session,
    ticket_id: str,
    new_priority: TicketPriority,
    *,
    actor_id: str | None = None,
) -> TicketDetail:
    ticket = get_ticket_or_404(db, ticket_id)
    actor = resolve_actor(db, actor_id)

    if ticket.priority is new_priority:
        return to_detail(ticket)

    previous = ticket.priority
    now = utcnow()
    ticket.priority = new_priority
    ticket.updated_at = now
    if ticket.status not in _TERMINAL_STATUSES:
        ticket.due_at = (
            now + _SLA_TARGET
            if new_priority in (TicketPriority.URGENT, TicketPriority.HIGH)
            else None
        )

    with transaction(db):
        activity_repo.add_activity(
            db,
            ticket=ticket,
            actor=actor,
            action=ActivityAction.PRIORITY_CHANGED,
            detail=(
                f"Priority changed from {PRIORITY_LABELS[previous]} "
                f"to {PRIORITY_LABELS[new_priority]}."
            ),
        )
    return to_detail(reload_ticket(db, ticket.public_id))


def update_category(
    db: Session,
    ticket_id: str,
    new_category: TicketCategory,
    *,
    actor_id: str | None = None,
) -> TicketDetail:
    ticket = get_ticket_or_404(db, ticket_id)
    actor = resolve_actor(db, actor_id)

    if ticket.category is new_category:
        return to_detail(ticket)

    previous = ticket.category
    team = CATEGORY_TEAM[new_category]
    ticket.category = new_category
    # Team routing is category-derived. An explicit agent assignment is kept;
    # the operator must reassign the agent separately if that is desired.
    ticket.assigned_team = team
    ticket.updated_at = utcnow()

    with transaction(db):
        activity_repo.add_activity(
            db,
            ticket=ticket,
            actor=actor,
            action=ActivityAction.CATEGORIZED,
            detail=(
                f"Category changed from {CATEGORY_LABELS[previous]} "
                f"to {CATEGORY_LABELS[new_category]} "
                f"(routed to {TEAM_LABELS[team]})."
            ),
        )
    return to_detail(reload_ticket(db, ticket.public_id))


def update_assignment(
    db: Session,
    ticket_id: str,
    agent_id: str | None,
    *,
    actor_id: str | None = None,
) -> TicketDetail:
    ticket = get_ticket_or_404(db, ticket_id)
    actor = resolve_actor(db, actor_id)

    new_agent = None
    if agent_id:
        normalized = agent_id.strip().upper()
        new_agent = agent_repo.get_agent(db, normalized)
        if new_agent is None:
            raise ApiError(
                status_code=422,
                code="invalid_agent",
                message=f"Agent {normalized} does not exist.",
            )

    target_id = new_agent.id if new_agent else None
    if ticket.assigned_agent_id == target_id:
        return to_detail(ticket)

    previous_agent = ticket.assigned_agent
    if new_agent is not None:
        detail = (
            f"Reassigned from {previous_agent.name} to {new_agent.name}."
            if previous_agent
            else f"Assigned to {new_agent.name}."
        )
    else:
        detail = (
            f"Unassigned (previously assigned to "
            f"{previous_agent.name if previous_agent else 'unknown'})."
        )

    ticket.assigned_agent_id = target_id
    ticket.updated_at = utcnow()

    with transaction(db):
        activity_repo.add_activity(
            db,
            ticket=ticket,
            actor=actor,
            action=ActivityAction.ASSIGNED,
            detail=detail,
        )
    return to_detail(reload_ticket(db, ticket.public_id))
