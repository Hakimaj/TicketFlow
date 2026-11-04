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

Every triage mutation takes a row lock and requires the `expected_version` the
operator last read. A stale version is rejected with 409 before anything is
written, so two agents can never silently overwrite each other.

Each successful mutation commits the ticket change, its `version` increment and
its activity event in one transaction. Failures roll all of them back.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.labels import (
    CATEGORY_LABELS,
    CATEGORY_TEAM,
    CHANNEL_LABELS,
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
from app.models.requester import Requester
from app.models.ticket import Ticket
from app.repositories import activities as activity_repo
from app.repositories import agents as agent_repo
from app.repositories import tickets as ticket_repo
from app.repositories.tickets import TicketFilters
from app.schemas.common import PageMeta
from app.schemas.tickets import (
    RequesterSummary,
    SortDirection,
    TicketCreate,
    TicketDetail,
    TicketListResponse,
    TicketSortField,
    TicketSummary,
)
from app.services.auth import Principal
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
        version=ticket.version,
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
# Intake
# ---------------------------------------------------------------------------


def create_ticket(
    db: Session, payload: TicketCreate, *, principal: Principal
) -> TicketDetail:
    """Create a ticket, its requester link and its initial audit event.

    One transaction covers requester reuse/creation, the ticket insert, the
    version default and the ``created`` audit event; a failure anywhere rolls
    all of it back so no half-created ticket or orphan event can persist.

    Defaults applied here (documented for the API contract):

    - ``status`` starts as ``new`` and is never taken from the request;
    - ``assigned_team`` is derived from the category (the same authoritative
      mapping triage uses); no agent is guessed;
    - ``due_at`` uses the same 8-hour SLA target as urgent/high triage and is
      empty for other priorities;
    - an existing requester with the same normalized email is reused.
    """
    email = payload.requester_email
    now = utcnow()

    def _create() -> Ticket:
        with transaction(db):
            requester = db.scalar(
                select(Requester).where(Requester.email == email)
            )
            if requester is None:
                requester = Requester(name=payload.requester_name, email=email)
                db.add(requester)
                db.flush()

            created = Ticket(
                public_id=ticket_repo.next_public_id(db),
                subject=payload.subject,
                description=payload.description,
                requester_id=requester.id,
                channel=payload.channel,
                category=payload.category,
                priority=payload.priority,
                status=TicketStatus.NEW,
                assigned_team=CATEGORY_TEAM[payload.category],
                assigned_agent_id=None,
                due_at=(
                    now + _SLA_TARGET
                    if payload.priority
                    in (TicketPriority.URGENT, TicketPriority.HIGH)
                    else None
                ),
                version=1,
            )
            db.add(created)
            # Flush so the internal UUID exists for the audit row's foreign key.
            db.flush()

            activity_repo.add_activity(
                db,
                ticket=created,
                actor=principal.agent,
                action=ActivityAction.CREATED,
                detail=(
                    "Ticket created via "
                    f"{CHANNEL_LABELS[payload.channel].lower()} intake."
                ),
                actor_account_id=principal.account_id,
            )
        return created

    for attempt in (1, 2):
        try:
            ticket = _create()
            break
        except IntegrityError as exc:
            # A concurrent transaction inserted the same requester email between
            # our lookup and insert (ticket numbers are serialised by an
            # advisory lock, so this is the only reachable unique conflict).
            # Retry once and reuse the now-committed requester; a second
            # failure is reported as a conflict instead of a 500. Nothing from
            # the rolled-back attempt survives.
            if attempt == 2:
                raise ApiError(
                    status_code=409,
                    code="ticket_conflict",
                    message=(
                        "The ticket could not be created because of a "
                        "concurrent change. Please submit again."
                    ),
                ) from exc

    return to_detail(reload_ticket(db, ticket.public_id))


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def update_status(
    db: Session,
    ticket_id: str,
    new_status: TicketStatus,
    *,
    expected_version: int,
    principal: Principal,
) -> TicketDetail:
    ticket = get_ticket_or_404(
        db, ticket_id, expected_version=expected_version, for_update=True
    )
    actor = principal.agent

    if ticket.status is new_status:
        return to_detail(ticket)

    previous = ticket.status
    ticket.status = new_status
    ticket.version += 1
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
            actor_account_id=principal.account_id,
        )
    return to_detail(reload_ticket(db, ticket.public_id))


def update_priority(
    db: Session,
    ticket_id: str,
    new_priority: TicketPriority,
    *,
    expected_version: int,
    principal: Principal,
) -> TicketDetail:
    ticket = get_ticket_or_404(
        db, ticket_id, expected_version=expected_version, for_update=True
    )
    actor = principal.agent

    if ticket.priority is new_priority:
        return to_detail(ticket)

    previous = ticket.priority
    now = utcnow()
    ticket.priority = new_priority
    ticket.version += 1
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
            actor_account_id=principal.account_id,
        )
    return to_detail(reload_ticket(db, ticket.public_id))


def update_category(
    db: Session,
    ticket_id: str,
    new_category: TicketCategory,
    *,
    expected_version: int,
    principal: Principal,
) -> TicketDetail:
    ticket = get_ticket_or_404(
        db, ticket_id, expected_version=expected_version, for_update=True
    )
    actor = principal.agent

    if ticket.category is new_category:
        return to_detail(ticket)

    previous = ticket.category
    team = CATEGORY_TEAM[new_category]
    ticket.category = new_category
    # Team routing is category-derived. An explicit agent assignment is kept;
    # the operator must reassign the agent separately if that is desired.
    ticket.assigned_team = team
    ticket.version += 1
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
            actor_account_id=principal.account_id,
        )
    return to_detail(reload_ticket(db, ticket.public_id))


def update_assignment(
    db: Session,
    ticket_id: str,
    agent_id: str | None,
    *,
    expected_version: int,
    principal: Principal,
) -> TicketDetail:
    ticket = get_ticket_or_404(
        db, ticket_id, expected_version=expected_version, for_update=True
    )
    actor = principal.agent

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
    ticket.version += 1
    ticket.updated_at = utcnow()

    with transaction(db):
        activity_repo.add_activity(
            db,
            ticket=ticket,
            actor=actor,
            action=ActivityAction.ASSIGNED,
            detail=detail,
            actor_account_id=principal.account_id,
        )
    return to_detail(reload_ticket(db, ticket.public_id))
