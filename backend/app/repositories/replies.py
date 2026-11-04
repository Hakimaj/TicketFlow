"""Database access for customer replies, revisions and review decisions.

All filtering, ordering and pagination for the approval queue happens in SQL.
Workflow mutations load the reply row with ``SELECT ... FOR UPDATE`` so two
concurrent transitions cannot both commit from the same observed state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.agent import Agent
from app.models.enums import ReplyReviewDecision, ReplyState
from app.models.reply import CustomerReply, ReplyReview, ReplyRevision
from app.models.ticket import Ticket
from app.schemas.tickets import SortDirection


@dataclass(frozen=True)
class ReplyFilters:
    """Validated filters for the pending-approval queue."""

    search: str | None = None
    categories: tuple[Any, ...] = field(default_factory=tuple)
    priorities: tuple[Any, ...] = field(default_factory=tuple)


def new_public_id() -> str:
    """Stable-format, collision-resistant public reply ID (fits 16 chars)."""
    return f"REP-{uuid.uuid4().hex[:12].upper()}"


def add_reply(
    db: Session,
    *,
    ticket_id: uuid.UUID,
    author_id: str,
    body: str,
    author_account_id: uuid.UUID | None = None,
) -> CustomerReply:
    reply = CustomerReply(
        public_id=new_public_id(),
        ticket_id=ticket_id,
        author_id=author_id,
        author_account_id=author_account_id,
        body=body,
        state=ReplyState.DRAFT,
        version=1,
    )
    db.add(reply)
    return reply


def add_revision(
    db: Session,
    *,
    reply: CustomerReply,
    body: str,
    author_id: str,
    version: int | None = None,
    author_account_id: uuid.UUID | None = None,
) -> ReplyRevision:
    revision = ReplyRevision(
        reply_id=reply.id,
        version=version if version is not None else reply.version,
        body=body,
        author_id=author_id,
        author_account_id=author_account_id,
    )
    db.add(revision)
    return revision


def add_review(
    db: Session,
    *,
    reply: CustomerReply,
    revision: ReplyRevision,
    decision: ReplyReviewDecision,
    reviewer: Agent,
    comment: str | None,
    reviewer_account_id: uuid.UUID | None = None,
) -> ReplyReview:
    review = ReplyReview(
        reply_id=reply.id,
        revision_id=revision.id,
        version=revision.version,
        decision=decision,
        reviewer_id=reviewer.id,
        reviewer_account_id=reviewer_account_id,
        reviewer_name=reviewer.name,
        comment=comment,
    )
    db.add(review)
    return review


def get_revision(
    db: Session, reply_id: uuid.UUID, version: int
) -> ReplyRevision | None:
    return db.scalars(
        select(ReplyRevision).where(
            ReplyRevision.reply_id == reply_id,
            ReplyRevision.version == version,
        )
    ).one_or_none()


def get_approved_review(
    db: Session, reply_id: uuid.UUID, version: int
) -> ReplyReview | None:
    return db.scalars(
        select(ReplyReview).where(
            ReplyReview.reply_id == reply_id,
            ReplyReview.version == version,
            ReplyReview.decision == ReplyReviewDecision.APPROVED,
        )
    ).first()


def list_revisions(db: Session, reply_id: uuid.UUID) -> list[ReplyRevision]:
    stmt = (
        select(ReplyRevision)
        .options(joinedload(ReplyRevision.author))
        .where(ReplyRevision.reply_id == reply_id)
        .order_by(ReplyRevision.version.asc())
    )
    return list(db.scalars(stmt).unique().all())


def list_reviews(db: Session, reply_id: uuid.UUID) -> list[ReplyReview]:
    stmt = (
        select(ReplyReview)
        .where(ReplyReview.reply_id == reply_id)
        .order_by(ReplyReview.created_at.asc(), ReplyReview.id.asc())
    )
    return list(db.scalars(stmt).all())


def _detail_options() -> tuple:
    return (
        joinedload(CustomerReply.author),
        joinedload(CustomerReply.ticket).joinedload(Ticket.requester),
        selectinload(CustomerReply.revisions).joinedload(ReplyRevision.author),
        selectinload(CustomerReply.reviews),
    )


def get_reply(db: Session, public_id: str) -> CustomerReply | None:
    """Load one reply with author, ticket/requester, revisions and reviews."""
    stmt = (
        select(CustomerReply)
        .options(*_detail_options())
        .where(CustomerReply.public_id == public_id)
    )
    return db.scalars(stmt).unique().one_or_none()


def lock_reply(db: Session, public_id: str) -> CustomerReply | None:
    """Load a reply and hold a row-level write lock until commit/rollback.

    No relationship eager-loading is used here: PostgreSQL cannot apply
    ``FOR UPDATE`` to the nullable side of an outer join. Scalar columns are
    enough for every state check; the full detail is reloaded after commit.
    """
    stmt = (
        select(CustomerReply)
        .where(CustomerReply.public_id == public_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).one_or_none()


def lock_ticket(db: Session, ticket_id: uuid.UUID) -> Ticket | None:
    stmt = (
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).one_or_none()


def lock_active_reply(
    db: Session, ticket_id: uuid.UUID
) -> CustomerReply | None:
    """The one non-sent reply for a ticket, locked for update if present."""
    stmt = (
        select(CustomerReply)
        .where(
            CustomerReply.ticket_id == ticket_id,
            CustomerReply.state != ReplyState.SENT,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).one_or_none()


def get_active_reply(
    db: Session, ticket_id: uuid.UUID
) -> CustomerReply | None:
    return db.scalars(
        select(CustomerReply).where(
            CustomerReply.ticket_id == ticket_id,
            CustomerReply.state != ReplyState.SENT,
        )
    ).one_or_none()


def list_replies(
    db: Session, ticket_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[CustomerReply], int]:
    total = int(
        db.scalar(
            select(func.count())
            .select_from(CustomerReply)
            .where(CustomerReply.ticket_id == ticket_id)
        )
        or 0
    )
    stmt = (
        select(CustomerReply)
        .options(
            joinedload(CustomerReply.author),
            joinedload(CustomerReply.ticket).joinedload(Ticket.requester),
        )
        .where(CustomerReply.ticket_id == ticket_id)
        .order_by(CustomerReply.created_at.desc(), CustomerReply.public_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique().all()), total


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_queue_filters(
    stmt: Select[Any], filters: ReplyFilters
) -> Select[Any]:
    stmt = stmt.where(CustomerReply.state == ReplyState.PENDING_APPROVAL)
    if filters.categories:
        stmt = stmt.where(Ticket.category.in_(filters.categories))
    if filters.priorities:
        stmt = stmt.where(Ticket.priority.in_(filters.priorities))
    if filters.search:
        pattern = f"%{_escape_like(filters.search.strip())}%"
        stmt = stmt.where(
            or_(
                Ticket.public_id.ilike(pattern, escape="\\"),
                Ticket.subject.ilike(pattern, escape="\\"),
                CustomerReply.public_id.ilike(pattern, escape="\\"),
                Agent.name.ilike(pattern, escape="\\"),
                CustomerReply.body.ilike(pattern, escape="\\"),
            )
        )
    return stmt


def _queue_select() -> Select[Any]:
    return (
        select(CustomerReply)
        .join(CustomerReply.ticket)
        .join(CustomerReply.author)
    )


def list_pending_approvals(
    db: Session,
    filters: ReplyFilters,
    *,
    sort_dir: SortDirection,
    page: int,
    page_size: int,
) -> tuple[list[CustomerReply], int]:
    """Paginated pending-approval queue, filtered and counted in SQL."""
    count_stmt = _apply_queue_filters(
        select(func.count())
        .select_from(CustomerReply)
        .join(CustomerReply.ticket)
        .join(CustomerReply.author),
        filters,
    )
    total = int(db.scalar(count_stmt) or 0)

    submitted = (
        CustomerReply.submitted_at.asc()
        if sort_dir is SortDirection.ASC
        else CustomerReply.submitted_at.desc()
    )
    stmt = (
        _apply_queue_filters(_queue_select(), filters)
        .options(
            joinedload(CustomerReply.author),
            joinedload(CustomerReply.ticket).joinedload(Ticket.requester),
        )
        .order_by(submitted, CustomerReply.public_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique().all()), total


def list_all_replies(
    db: Session,
    *,
    search: str | None = None,
    sort_dir: SortDirection,
    page: int,
    page_size: int,
) -> tuple[list[CustomerReply], int]:
    """Every logical reply with its parent ticket, filtered/paged in SQL.

    Supports the approval workspace: all states (draft, pending, approved,
    changes-requested, sent) are returned so the UI can tab across the whole
    workflow without one request per ticket.
    """
    base = _queue_select()
    if search and search.strip():
        pattern = f"%{_escape_like(search.strip())}%"
        base = base.where(
            or_(
                Ticket.public_id.ilike(pattern, escape="\\"),
                Ticket.subject.ilike(pattern, escape="\\"),
                CustomerReply.public_id.ilike(pattern, escape="\\"),
                Agent.name.ilike(pattern, escape="\\"),
                CustomerReply.body.ilike(pattern, escape="\\"),
            )
        )

    count_stmt = base.with_only_columns(func.count()).order_by(None)
    total = int(db.scalar(count_stmt) or 0)

    updated = (
        CustomerReply.updated_at.asc()
        if sort_dir is SortDirection.ASC
        else CustomerReply.updated_at.desc()
    )
    stmt = (
        base.options(
            joinedload(CustomerReply.author),
            joinedload(CustomerReply.ticket).joinedload(Ticket.requester),
        )
        .order_by(updated, CustomerReply.public_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique().all()), total


def count_by_state(db: Session) -> dict[ReplyState, int]:
    rows = db.execute(
        select(CustomerReply.state, func.count(CustomerReply.id)).group_by(
            CustomerReply.state
        )
    ).all()
    return {value: int(count) for value, count in rows}
