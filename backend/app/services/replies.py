"""Customer reply workflow services.

Business rules (authoritative here, not in the UI):

- Saving a draft never submits, approves or sends.
- Submitting never approves.
- Approving never sends and never changes the ticket status.
- Only an explicit demo-send may move a reply to ``sent``, and only when the
  *current* revision carries a recorded human approval.
- Any body change creates a new immutable ``ReplyRevision``; it also clears
  pending/approved/changes-requested state so stale approval metadata can never
  authorize the new text.
- Sent replies are immutable.

Every transition writes its audit event in the same transaction and commits
once. The reply row is locked with ``SELECT ... FOR UPDATE`` for each
transition, so concurrent edits, reviews and demo sends serialize on PostgreSQL.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.labels import STATUS_LABELS
from app.models.common import utcnow
from app.models.enums import (
    ActivityAction,
    ReplyReviewDecision,
    ReplyState,
    TicketStatus,
)
from app.models.reply import CustomerReply, ReplyReview, ReplyRevision
from app.repositories import activities as activity_repo
from app.repositories import replies as reply_repo
from app.repositories.replies import ReplyFilters
from app.schemas.common import PageMeta
from app.schemas.replies import (
    ReplyActor,
    ReplyAllListResponse,
    ReplyApprove,
    ReplyCreate,
    ReplyDetail,
    ReplyListResponse,
    ReplyQueueItem,
    ReplyQueueResponse,
    ReplyRecipient,
    ReplyRequestChanges,
    ReplyReviewResponse,
    ReplyRevisionResponse,
    ReplySendDemo,
    ReplySendResult,
    ReplySubmit,
    ReplySummary,
    ReplyTicketRef,
    ReplyUpdate,
    ReplyWithTicketItem,
)
from app.schemas.tickets import SortDirection
from app.services.auth import Principal
from app.services.common import get_ticket_or_404, transaction

REPLY_PREVIEW_LENGTH = 180


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


def _reply_not_found(public_id: str) -> ApiError:
    normalized = public_id.strip().upper()
    return not_found(
        "reply_not_found",
        f"Reply {normalized or public_id} was not found.",
    )


def _conflict(code: str, message: str, **details: str) -> ApiError:
    return ApiError(
        status_code=409,
        code=code,
        message=message,
        details=[{"field": key, "message": value} for key, value in details.items()]
        or None,
    )


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------


def _actor(actor_id: str, name: str) -> ReplyActor:
    return ReplyActor(id=actor_id, name=name)


def _preview(body: str) -> str:
    collapsed = " ".join(body.split())
    if len(collapsed) <= REPLY_PREVIEW_LENGTH:
        return collapsed
    return collapsed[: REPLY_PREVIEW_LENGTH - 1].rstrip() + "…"


def _to_summary(reply: CustomerReply) -> ReplySummary:
    requester = reply.ticket.requester
    return ReplySummary(
        id=reply.public_id,
        ticket_id=reply.ticket.public_id,
        author=_actor(reply.author.id, reply.author.name),
        recipient=ReplyRecipient(name=requester.name, email=requester.email),
        body=reply.body,
        state=reply.state,
        version=reply.version,
        submitted_at=reply.submitted_at,
        submitted_version=reply.submitted_version,
        reviewed_at=reply.reviewed_at,
        reviewer_id=reply.reviewer_id,
        reviewer_name=reply.reviewer_name,
        reviewer_feedback=reply.reviewer_feedback,
        approved_version=reply.approved_version,
        sent_at=reply.sent_at,
        sent_by_actor_name=reply.sent_by_actor_name,
        created_at=reply.created_at,
        updated_at=reply.updated_at,
    )


def _revision_response(revision: ReplyRevision) -> ReplyRevisionResponse:
    return ReplyRevisionResponse(
        id=str(revision.id),
        version=revision.version,
        body=revision.body,
        author=_actor(revision.author_id, revision.author.name),
        created_at=revision.created_at,
    )


def _review_response(review: ReplyReview) -> ReplyReviewResponse:
    return ReplyReviewResponse(
        id=str(review.id),
        decision=review.decision,
        version=review.version,
        reviewer_id=review.reviewer_id,
        reviewer_name=review.reviewer_name,
        comment=review.comment,
        created_at=review.created_at,
    )


def _to_detail(
    reply: CustomerReply,
    revisions: list[ReplyRevision],
    reviews: list[ReplyReview],
) -> ReplyDetail:
    summary = _to_summary(reply)
    return ReplyDetail(
        **summary.model_dump(),
        revisions=[_revision_response(item) for item in revisions],
        reviews=[_review_response(item) for item in reviews],
    )


def _load_detail(db: Session, public_id: str) -> ReplyDetail:
    reply = reply_repo.get_reply(db, public_id)
    if reply is None:  # pragma: no cover - only on a concurrent delete
        raise _reply_not_found(public_id)
    return _to_detail(
        reply,
        reply_repo.list_revisions(db, reply.id),
        reply_repo.list_reviews(db, reply.id),
    )


def _lock_or_404(db: Session, reply_id: str) -> CustomerReply:
    normalized = reply_id.strip().upper()
    reply = reply_repo.lock_reply(db, normalized)
    if reply is None:
        raise _reply_not_found(normalized)
    return reply


# ---------------------------------------------------------------------------
# Drafts and revisions
# ---------------------------------------------------------------------------


def create_draft(
    db: Session,
    ticket_id: str,
    payload: ReplyCreate,
    *,
    principal: Principal,
) -> ReplyDetail:
    """Create the ticket's single active draft and revision 1 atomically."""
    ticket = get_ticket_or_404(db, ticket_id)
    actor = principal.agent

    existing = reply_repo.get_active_reply(db, ticket.id)
    if existing is not None:
        raise _conflict(
            "reply_already_exists",
            (
                f"Ticket {ticket.public_id} already has an active reply "
                f"({existing.public_id}). Edit that reply instead of creating "
                "another draft."
            ),
            reply_id=existing.public_id,
        )

    reply = reply_repo.add_reply(
        db,
        ticket_id=ticket.id,
        author_id=actor.id,
        body=payload.body,
        author_account_id=principal.account_id,
    )
    try:
        with transaction(db):
            # Flush assigns the UUID and surfaces the one-active-reply unique
            # index before dependent rows are written.
            db.flush()
            reply_repo.add_revision(
                db,
                reply=reply,
                body=payload.body,
                author_id=actor.id,
                version=1,
                author_account_id=principal.account_id,
            )
            ticket.updated_at = utcnow()
            db.flush()
            activity_repo.add_activity(
                db,
                ticket=ticket,
                actor=actor,
                action=ActivityAction.REPLIED_DRAFT,
                detail=f"Customer reply draft started by {actor.name}.",
                reply=reply,
                reply_version=1,
                actor_account_id=principal.account_id,
            )
    except IntegrityError as exc:
        # A concurrent create won the partial unique index. Translate it into
        # the same predictable conflict instead of a 500.
        db.rollback()
        winner = reply_repo.get_active_reply(db, ticket.id)
        if winner is not None:
            raise _conflict(
                "reply_already_exists",
                (
                    f"Ticket {ticket.public_id} already has an active reply "
                    f"({winner.public_id})."
                ),
                reply_id=winner.public_id,
            ) from exc
        raise

    return _load_detail(db, reply.public_id)


def list_replies(
    db: Session, ticket_id: str, *, page: int, page_size: int
) -> ReplyListResponse:
    ticket = get_ticket_or_404(db, ticket_id)
    replies, total = reply_repo.list_replies(
        db, ticket.id, page=page, page_size=page_size
    )
    page_count = (total + page_size - 1) // page_size if total else 0
    return ReplyListResponse(
        items=[_to_summary(reply) for reply in replies],
        pagination=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            page_count=page_count,
        ),
    )


def get_reply(db: Session, reply_id: str) -> ReplyDetail:
    normalized = reply_id.strip().upper()
    reply = reply_repo.get_reply(db, normalized)
    if reply is None:
        raise _reply_not_found(normalized)
    return _to_detail(
        reply,
        reply_repo.list_revisions(db, reply.id),
        reply_repo.list_reviews(db, reply.id),
    )


def update_reply(
    db: Session,
    reply_id: str,
    payload: ReplyUpdate,
    *,
    principal: Principal,
) -> ReplyDetail:
    """Save content, creating a new revision only when the body changed."""
    reply = _lock_or_404(db, reply_id)

    if reply.state is ReplyState.SENT:
        raise _conflict(
            "reply_immutable",
            (
                f"Reply {reply.public_id} was marked as sent in demo mode and "
                "can no longer be edited. Start a new reply draft instead."
            ),
        )

    if reply.body == payload.body:
        # True no-op: no revision, no audit event, no timestamp churn.
        return _load_detail(db, reply.public_id)

    actor = principal.agent
    previous_state = reply.state
    now = utcnow()
    reply.body = payload.body
    reply.version += 1
    reply.updated_at = now

    if previous_state in (
        ReplyState.PENDING_APPROVAL,
        ReplyState.APPROVED,
        ReplyState.CHANGES_REQUESTED,
    ):
        reply.state = ReplyState.DRAFT
        reply.submitted_at = None
        reply.submitted_version = None
        reply.reviewed_at = None
        reply.reviewer_id = None
        reply.reviewer_name = None
        reply.reviewer_feedback = None
        reply.approved_version = None
        reason = {
            ReplyState.APPROVED: (
                "The previous supervisor approval was invalidated"
            ),
            ReplyState.PENDING_APPROVAL: (
                "The reply was withdrawn from the approval queue"
            ),
            ReplyState.CHANGES_REQUESTED: (
                "The reply was revised after reviewer feedback"
            ),
        }[previous_state]
        detail = (
            f"Customer reply revised to v{reply.version} by {actor.name}. "
            f"{reason}; it must be resubmitted for approval before it can be "
            "sent."
        )
    else:
        detail = (
            f"Customer reply draft (v{reply.version}) updated by {actor.name}."
        )

    with transaction(db):
        reply_repo.add_revision(
            db,
            reply=reply,
            body=reply.body,
            author_id=actor.id,
            author_account_id=principal.account_id,
        )
        db.flush()
        activity_repo.add_activity(
            db,
            ticket=reply.ticket,
            actor=actor,
            action=ActivityAction.REPLIED_DRAFT,
            detail=detail,
            reply=reply,
            reply_version=reply.version,
            actor_account_id=principal.account_id,
        )

    return _load_detail(db, reply.public_id)


# ---------------------------------------------------------------------------
# Submission and human review
# ---------------------------------------------------------------------------


def submit_for_approval(
    db: Session,
    reply_id: str,
    payload: ReplySubmit,
    *,
    principal: Principal,
) -> ReplyDetail:
    reply = _lock_or_404(db, reply_id)

    if reply.state is ReplyState.SENT:
        raise _conflict(
            "reply_already_sent",
            f"Reply {reply.public_id} has already been marked as sent.",
        )
    if reply.state is ReplyState.PENDING_APPROVAL:
        raise _conflict(
            "reply_already_pending",
            f"Reply {reply.public_id} is already awaiting approval.",
        )
    if reply.state is ReplyState.APPROVED:
        raise _conflict(
            "reply_already_approved",
            (
                f"Reply {reply.public_id} is already approved. Revise it before "
                "resubmitting."
            ),
        )
    if reply.state not in (ReplyState.DRAFT, ReplyState.CHANGES_REQUESTED):
        # Defensive: only the two author-editable states may be submitted.
        raise _conflict(
            "reply_state_conflict",
            f"Reply {reply.public_id} cannot be submitted from {reply.state.value}.",
        )
    if not reply.body.strip():
        raise ApiError(
            status_code=422,
            code="reply_empty",
            message="Cannot submit an empty reply for approval.",
        )

    actor = principal.agent
    was_revised = reply.state is ReplyState.CHANGES_REQUESTED
    now = utcnow()
    reply.state = ReplyState.PENDING_APPROVAL
    reply.submitted_at = now
    reply.submitted_version = reply.version
    reply.reviewed_at = None
    reply.reviewer_id = None
    reply.reviewer_name = None
    reply.reviewer_feedback = None
    reply.approved_version = None
    reply.updated_at = now

    detail = (
        f"Revised customer reply (v{reply.version}) resubmitted for approval "
        f"by {actor.name}."
        if was_revised
        else (
            f"Customer reply (v{reply.version}) submitted for supervisor "
            f"approval by {actor.name}."
        )
    )

    with transaction(db):
        activity_repo.add_activity(
            db,
            ticket=reply.ticket,
            actor=actor,
            action=ActivityAction.REPLY_SUBMITTED,
            detail=detail,
            reply=reply,
            reply_version=reply.version,
            actor_account_id=principal.account_id,
        )

    return _load_detail(db, reply.public_id)


def _current_revision_or_conflict(
    db: Session, reply: CustomerReply, version: int
) -> ReplyRevision:
    revision = reply_repo.get_revision(db, reply.id, version)
    if revision is None:
        raise _conflict(
            "reply_version_conflict",
            (
                f"Version {version} of reply {reply.public_id} does not exist. "
                f"The current version is {reply.version}."
            ),
            version=f"The current version is {reply.version}.",
        )
    return revision


def _assert_not_author(reply: CustomerReply, principal: Principal) -> None:
    """Reject any review decision by the reply's own author.

    New replies store the verified account that authored them. Historical rows
    created before accounts existed only carry ``author_id`` (an agent), so that
    is used as the fallback identity. No role — including ``admin`` — is exempt.
    """
    same_account = (
        reply.author_account_id is not None
        and reply.author_account_id == principal.account_id
    )
    same_agent = reply.author_id == principal.agent.id
    if same_account or same_agent:
        raise ApiError(
            status_code=403,
            code="self_approval_forbidden",
            message=(
                "You authored this reply, so you cannot approve it or request "
                "changes. Another reviewer must make the decision."
            ),
        )


def approve_reply(
    db: Session,
    reply_id: str,
    payload: ReplyApprove,
    *,
    principal: Principal,
) -> ReplyDetail:
    """Record a human approval for the exact submitted revision.

    Approval is a review decision only: it does not send anything and does not
    change the ticket status. The reviewer is the authenticated account; an
    author can never approve their own reply.
    """
    reply = _lock_or_404(db, reply_id)

    if reply.state is not ReplyState.PENDING_APPROVAL:
        raise _conflict(
            "reply_not_pending",
            (
                f"Only replies awaiting approval can be approved. Reply "
                f"{reply.public_id} is currently {reply.state.value}."
            ),
        )
    if (
        reply.submitted_version is None
        or reply.submitted_version != reply.version
        or payload.version != reply.submitted_version
    ):
        raise _conflict(
            "reply_version_conflict",
            (
                f"Version {payload.version} is not the version currently "
                f"awaiting approval for reply {reply.public_id}."
            ),
            version=(
                "The submitted version is "
                f"{reply.submitted_version if reply.submitted_version is not None else 'unknown'}."
            ),
        )

    revision = _current_revision_or_conflict(db, reply, payload.version)
    # Re-checked inside the locked transaction that performs the approval.
    _assert_not_author(reply, principal)
    reviewer = principal.agent
    now = utcnow()

    reply.state = ReplyState.APPROVED
    reply.reviewed_at = now
    reply.reviewer_id = reviewer.id
    reply.reviewer_name = reviewer.name
    reply.reviewer_feedback = None
    reply.approved_version = revision.version
    reply.updated_at = now

    with transaction(db):
        reply_repo.add_review(
            db,
            reply=reply,
            revision=revision,
            decision=ReplyReviewDecision.APPROVED,
            reviewer=reviewer,
            comment=payload.comment,
            reviewer_account_id=principal.account_id,
        )
        db.flush()
        activity_repo.add_activity(
            db,
            ticket=reply.ticket,
            actor=reviewer,
            action=ActivityAction.REPLY_APPROVED,
            detail=(
                f"Customer reply (v{revision.version}) approved by "
                f"{reviewer.name}. It can now be explicitly marked as sent in "
                "demo mode; no message is delivered by approval."
            ),
            reply=reply,
            reply_version=revision.version,
            actor_account_id=principal.account_id,
        )

    return _load_detail(db, reply.public_id)


def request_changes(
    db: Session,
    reply_id: str,
    payload: ReplyRequestChanges,
    *,
    principal: Principal,
) -> ReplyDetail:
    """Send an internal change request for the exact submitted revision."""
    reply = _lock_or_404(db, reply_id)

    if reply.state is not ReplyState.PENDING_APPROVAL:
        raise _conflict(
            "reply_not_pending",
            (
                "Changes can only be requested on replies awaiting approval. "
                f"Reply {reply.public_id} is currently {reply.state.value}."
            ),
        )
    if (
        reply.submitted_version is None
        or reply.submitted_version != reply.version
        or payload.version != reply.submitted_version
    ):
        raise _conflict(
            "reply_version_conflict",
            (
                f"Version {payload.version} is not the version currently "
                f"awaiting approval for reply {reply.public_id}."
            ),
            version=(
                "The submitted version is "
                f"{reply.submitted_version if reply.submitted_version is not None else 'unknown'}."
            ),
        )

    revision = _current_revision_or_conflict(db, reply, payload.version)
    _assert_not_author(reply, principal)
    reviewer = principal.agent
    now = utcnow()

    reply.state = ReplyState.CHANGES_REQUESTED
    reply.reviewed_at = now
    reply.reviewer_id = reviewer.id
    reply.reviewer_name = reviewer.name
    reply.reviewer_feedback = payload.comment
    reply.approved_version = None
    reply.updated_at = now

    with transaction(db):
        reply_repo.add_review(
            db,
            reply=reply,
            revision=revision,
            decision=ReplyReviewDecision.CHANGES_REQUESTED,
            reviewer=reviewer,
            comment=payload.comment,
            reviewer_account_id=principal.account_id,
        )
        db.flush()
        activity_repo.add_activity(
            db,
            ticket=reply.ticket,
            actor=reviewer,
            action=ActivityAction.REPLY_CHANGES_REQUESTED,
            detail=(
                f"Changes requested on customer reply (v{revision.version}) by "
                f"{reviewer.name}. The internal feedback is stored with the "
                "review decision and is not customer-visible."
            ),
            reply=reply,
            reply_version=revision.version,
            actor_account_id=principal.account_id,
        )

    return _load_detail(db, reply.public_id)


# ---------------------------------------------------------------------------
# Approval queue
# ---------------------------------------------------------------------------


def list_pending_approvals(
    db: Session,
    *,
    search: str | None,
    categories: tuple,
    priorities: tuple,
    sort_dir: SortDirection,
    page: int,
    page_size: int,
) -> ReplyQueueResponse:
    filters = ReplyFilters(
        search=search,
        categories=categories,
        priorities=priorities,
    )
    replies, total = reply_repo.list_pending_approvals(
        db,
        filters,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    page_count = (total + page_size - 1) // page_size if total else 0
    return ReplyQueueResponse(
        items=[
            ReplyQueueItem(
                reply_id=reply.public_id,
                ticket_id=reply.ticket.public_id,
                ticket_subject=reply.ticket.subject,
                ticket_category=reply.ticket.category,
                ticket_priority=reply.ticket.priority,
                ticket_status=reply.ticket.status,
                requester_name=reply.ticket.requester.name,
                author=_actor(reply.author.id, reply.author.name),
                version=reply.version,
                submitted_version=reply.submitted_version,
                submitted_at=reply.submitted_at,
                preview=_preview(reply.body),
                state=reply.state,
            )
            for reply in replies
        ],
        pagination=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            page_count=page_count,
        ),
    )


# ---------------------------------------------------------------------------
# Demo send (approval gate)
# ---------------------------------------------------------------------------


def list_all_replies(
    db: Session,
    *,
    search: str | None,
    sort_dir: SortDirection,
    page: int,
    page_size: int,
) -> ReplyAllListResponse:
    """Every logical reply paired with its joined parent ticket.

    Powers the approvals workspace where the reviewer moves between draft,
    pending, approved, changes-requested and sent views.
    """
    replies, total = reply_repo.list_all_replies(
        db,
        search=search,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    page_count = (total + page_size - 1) // page_size if total else 0
    return ReplyAllListResponse(
        items=[
            ReplyWithTicketItem(
                reply=_to_summary(reply),
                ticket=ReplyTicketRef(
                    id=reply.ticket.public_id,
                    subject=reply.ticket.subject,
                    category=reply.ticket.category,
                    priority=reply.ticket.priority,
                    status=reply.ticket.status,
                    requester_name=reply.ticket.requester.name,
                    created_at=reply.ticket.created_at,
                ),
            )
            for reply in replies
        ],
        pagination=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            page_count=page_count,
        ),
    )


def _send_gate_error(reply: CustomerReply, reason: str) -> ApiError:
    return _conflict(
        "approval_required",
        (
            f"Approval gate rejected sending reply {reply.public_id}: {reason} "
            "A supervisor must approve this exact version before it can be "
            "marked as sent in demo mode."
        ),
    )


def mark_sent_demo(
    db: Session,
    reply_id: str,
    payload: ReplySendDemo | None = None,
    *,
    principal: Principal,
) -> ReplySendResult:
    """Mark an approved reply as sent in demo mode.

    No external message is sent. The gate is enforced here (and mirrored by
    database constraints), so calling this function directly with an
    unapproved or stale version fails exactly like the HTTP route.
    """
    reply = _lock_or_404(db, reply_id)

    if reply.state is ReplyState.SENT or reply.sent_at is not None:
        raise _conflict(
            "reply_already_sent",
            (
                f"Reply {reply.public_id} was already marked as sent in demo "
                "mode; it cannot be sent twice."
            ),
        )
    if reply.state is not ReplyState.APPROVED:
        raise _send_gate_error(
            reply,
            f"its current state is {reply.state.value}, not approved.",
        )
    if (
        reply.approved_version is None
        or reply.approved_version != reply.version
    ):
        raise _send_gate_error(
            reply,
            (
                "its recorded approval covers version "
                f"{reply.approved_version if reply.approved_version is not None else 'none'}"
                f" but the current version is {reply.version}."
            ),
        )
    if (
        reply.submitted_version != reply.version
        or reply.reviewer_id is None
        or reply.reviewed_at is None
    ):
        raise _send_gate_error(
            reply,
            "its approval/submission metadata is incomplete for the current version.",
        )

    revision = reply_repo.get_revision(db, reply.id, reply.version)
    if revision is None or revision.body != reply.body:
        raise _send_gate_error(
            reply,
            "the current revision history does not match the reply body.",
        )
    if reply_repo.get_approved_review(db, reply.id, reply.version) is None:
        raise _send_gate_error(
            reply,
            "no stored approval decision exists for the current version.",
        )

    actor = principal.agent
    now = utcnow()

    # Lock the ticket too so a concurrent status change is not silently lost.
    ticket = reply_repo.lock_ticket(db, reply.ticket_id)
    if ticket is None:  # pragma: no cover - FK guarantees the ticket exists
        raise not_found(
            "ticket_not_found",
            f"Ticket for reply {reply.public_id} was not found.",
        )

    reply.state = ReplyState.SENT
    reply.sent_at = now
    reply.sent_by_actor_name = actor.name
    reply.updated_at = now

    status_changed = False
    previous_status: TicketStatus | None = None
    if ticket.status in (TicketStatus.NEW, TicketStatus.OPEN):
        previous_status = ticket.status
        ticket.status = TicketStatus.PENDING
        ticket.updated_at = now
        # Demo sending changes triage state, so the concurrency token moves
        # with it; a triage mutation loaded before the send is rejected rather
        # than silently overwriting the new status.
        ticket.version += 1
        status_changed = True

    with transaction(db):
        activity_repo.add_activity(
            db,
            ticket=ticket,
            actor=actor,
            action=ActivityAction.REPLIED_SENT,
            detail=(
                f"Customer reply (v{reply.version}) marked as sent in demo mode "
                f"by {actor.name}. No external message was transmitted."
            ),
            reply=reply,
            reply_version=reply.version,
            actor_account_id=principal.account_id,
        )
        if status_changed and previous_status is not None:
            activity_repo.add_activity(
                db,
                ticket=ticket,
                actor=actor,
                action=ActivityAction.STATUS_CHANGED,
                detail=(
                    f"Status changed from {STATUS_LABELS[previous_status]} to "
                    f"{STATUS_LABELS[TicketStatus.PENDING]} after the customer "
                    "reply was marked as sent in demo mode."
                ),
                reply=reply,
                reply_version=reply.version,
                actor_account_id=principal.account_id,
            )

    return ReplySendResult(reply=_load_detail(db, reply.public_id))
