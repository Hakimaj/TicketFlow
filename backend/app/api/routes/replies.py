"""Persistent customer reply workflow endpoints.

Route registration order matters: the fixed ``/replies/approvals`` queue is
registered in its own router *before* the dynamic ``/replies/{reply_id}``
router so the queue path is never swallowed by the path parameter.

The acting account and reviewer always come from the verified access token;
request bodies cannot name an actor, reviewer or role. Approval is a review
decision only and an author can never review their own reply.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession
from app.api.params import ReplyIdPath, TicketIdPath
from app.authorization import (
    CanDraftReplies,
    CanReadOperations,
    CanReviewReplies,
    CanSendDemo,
    CurrentAccount,
)
from app.models.enums import TicketCategory, TicketPriority
from app.schemas.common import ErrorResponse
from app.schemas.replies import (
    ReplyAllListResponse,
    ReplyApprove,
    ReplyCreate,
    ReplyDetail,
    ReplyListResponse,
    ReplyQueueResponse,
    ReplyRequestChanges,
    ReplySendDemo,
    ReplySendResult,
    ReplySubmit,
    ReplyUpdate,
)
from app.schemas.tickets import SortDirection
from app.services import replies as reply_service
from app.services.auth import principal_for

# Ticket-scoped draft creation/list.
ticket_router = APIRouter(
    prefix="/tickets/{ticket_id}/replies", tags=["replies"]
)
# Fixed queue path: must be included before `reply_router`.
approvals_router = APIRouter(prefix="/replies", tags=["replies"])
# Single-reply operations.
reply_router = APIRouter(prefix="/replies", tags=["replies"])

_ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Unknown ticket or reply ID."},
    409: {"model": ErrorResponse, "description": "State or version conflict."},
    422: {"model": ErrorResponse, "description": "Invalid body or reference."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "Database unavailable."},
}

_REVIEW_ERROR_RESPONSES = {
    **_ERROR_RESPONSES,
    409: {
        "model": ErrorResponse,
        "description": (
            "Not pending, stale version, already sent, or approval gate "
            "rejection."
        ),
    },
}


@ticket_router.post(
    "",
    response_model=ReplyDetail,
    status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES,
    dependencies=[CanDraftReplies],
    summary="Create a reply draft",
    description=(
        "Creates the ticket's single active reply draft plus immutable "
        "revision 1 and an audit event in one transaction. The author is the "
        "authenticated account and the customer recipient is derived from the "
        "ticket's requester; neither can be supplied by the caller.\n\n"
        "A ticket may have only one non-sent reply at a time; if one already "
        "exists this returns `409 reply_already_exists`. Empty or "
        "whitespace-only drafts are rejected (`422`), matching the frontend "
        "demo service."
    ),
)
def create_draft(
    db: DbSession,
    account: CurrentAccount,
    ticket_id: TicketIdPath,
    payload: ReplyCreate,
) -> ReplyDetail:
    return reply_service.create_draft(
        db, ticket_id, payload, principal=principal_for(account)
    )


@ticket_router.get(
    "",
    response_model=ReplyListResponse,
    responses=_ERROR_RESPONSES,
    dependencies=[CanReadOperations],
    summary="List a ticket's replies",
    description=(
        "Returns only this ticket's replies, newest first, with the current "
        "version, workflow state, author and timestamps. Unknown tickets "
        "return `404 ticket_not_found`. Revision and review history is "
        "available on the single-reply endpoint."
    ),
)
def list_replies(
    db: DbSession,
    ticket_id: TicketIdPath,
    page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Replies per page (1–100).")
    ] = 20,
) -> ReplyListResponse:
    return reply_service.list_replies(
        db, ticket_id, page=page, page_size=page_size
    )


@approvals_router.get(
    "",
    response_model=ReplyAllListResponse,
    responses=_ERROR_RESPONSES,
    dependencies=[CanReadOperations],
    summary="List all replies with their tickets",
    description=(
        "Every logical reply (all workflow states) with its joined parent "
        "ticket, for reviewer workspaces that switch between draft, pending, "
        "approved, changes-requested and sent views. SQL-side search over "
        "ticket ID/subject, reply ID, author name and reply text; ordered by "
        "reply `updated_at` with a stable reply-ID tiebreak."
    ),
)
def list_all_replies(
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Replies per page (1–100).")
    ] = 100,
    search: Annotated[
        str | None,
        Query(max_length=120, description="Case-insensitive search."),
    ] = None,
    sort_dir: Annotated[
        SortDirection,
        Query(description="Reply `updated_at` order; `desc` (newest) by default."),
    ] = SortDirection.DESC,
) -> ReplyAllListResponse:
    return reply_service.list_all_replies(
        db,
        search=search,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@approvals_router.get(
    "/approvals",
    response_model=ReplyQueueResponse,
    responses=_ERROR_RESPONSES,
    dependencies=[CanReadOperations],
    summary="Pending reply approval queue",
    description=(
        "Replies currently in `pending_approval`, with ticket subject, "
        "category, priority and a safe preview of the submitted revision. "
        "Filtering, search, sorting and pagination execute in SQL. Drafts, "
        "changes-requested, approved and sent replies are never returned.\n\n"
        "Sorted by submission time (`desc` by default) with public reply ID "
        "as a stable tiebreak."
    ),
)
def list_pending_approvals(
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Replies per page (1–100).")
    ] = 20,
    search: Annotated[
        str | None,
        Query(
            max_length=120,
            description=(
                "Case-insensitive match on ticket ID/subject, reply ID, author "
                "name or reply text."
            ),
        ),
    ] = None,
    category: Annotated[
        list[TicketCategory] | None,
        Query(description="Filter by one or more ticket categories."),
    ] = None,
    priority: Annotated[
        list[TicketPriority] | None,
        Query(description="Filter by one or more ticket priorities."),
    ] = None,
    sort_dir: Annotated[
        SortDirection,
        Query(description="Submission-time order; `desc` (newest) by default."),
    ] = SortDirection.DESC,
) -> ReplyQueueResponse:
    return reply_service.list_pending_approvals(
        db,
        search=search,
        categories=tuple(category or ()),
        priorities=tuple(priority or ()),
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@reply_router.get(
    "/{reply_id}",
    response_model=ReplyDetail,
    responses=_ERROR_RESPONSES,
    dependencies=[CanReadOperations],
    summary="Get one reply with revision and review history",
    description=(
        "Returns the current workflow state, the exact submitted/approved "
        "versions, immutable text revisions and append-only review decisions. "
        "`reviewer_feedback` and review `comment` values are internal and are "
        "never part of the customer-visible body."
    ),
)
def get_reply(db: DbSession, reply_id: ReplyIdPath) -> ReplyDetail:
    return reply_service.get_reply(db, reply_id)


@reply_router.patch(
    "/{reply_id}",
    response_model=ReplyDetail,
    responses=_REVIEW_ERROR_RESPONSES,
    dependencies=[CanDraftReplies],
    summary="Edit a reply / create a revision",
    description=(
        "Saving identical text is a no-op (no revision, no event). Changed "
        "text creates a new immutable revision. Editing a pending, approved or "
        "changes-requested reply returns it to `draft` and clears the current "
        "approval/submission metadata; historical review decisions remain in "
        "the review history. A sent reply is immutable (`409 reply_immutable`)."
    ),
)
def update_reply(
    db: DbSession,
    account: CurrentAccount,
    reply_id: ReplyIdPath,
    payload: ReplyUpdate,
) -> ReplyDetail:
    return reply_service.update_reply(
        db, reply_id, payload, principal=principal_for(account)
    )


@reply_router.post(
    "/{reply_id}/submit",
    response_model=ReplyDetail,
    responses=_REVIEW_ERROR_RESPONSES,
    dependencies=[CanDraftReplies],
    summary="Submit the current revision for approval",
    description=(
        "Moves a draft (or a revised changes-requested reply) to "
        "`pending_approval`, recording the submitted version and a safe audit "
        "event atomically. Submission never approves or sends. Already pending "
        "(`409 reply_already_pending`), approved (`409 reply_already_approved`) "
        "and sent replies are rejected."
    ),
)
def submit_for_approval(
    db: DbSession,
    account: CurrentAccount,
    reply_id: ReplyIdPath,
    payload: ReplySubmit,
) -> ReplyDetail:
    return reply_service.submit_for_approval(
        db, reply_id, payload, principal=principal_for(account)
    )


@reply_router.post(
    "/{reply_id}/approve",
    response_model=ReplyDetail,
    responses=_REVIEW_ERROR_RESPONSES,
    dependencies=[CanReviewReplies],
    summary="Approve the exact submitted revision",
    description=(
        "Requires the `replies:review` permission, `pending_approval` and "
        "`version` equal to the submitted revision. The reviewer is the "
        "authenticated account. Records the reviewer, timestamp and exact "
        "approved version in an append-only review decision, then transitions "
        "to `approved`. Approval never sends a message and never changes the "
        "ticket status.\n\n"
        "An author can never approve their own reply (`403 "
        "self_approval_forbidden`), regardless of role."
    ),
)
def approve_reply(
    db: DbSession,
    account: CurrentAccount,
    reply_id: ReplyIdPath,
    payload: ReplyApprove,
) -> ReplyDetail:
    return reply_service.approve_reply(
        db, reply_id, payload, principal=principal_for(account)
    )


@reply_router.post(
    "/{reply_id}/request-changes",
    response_model=ReplyDetail,
    responses=_REVIEW_ERROR_RESPONSES,
    dependencies=[CanReviewReplies],
    summary="Request changes on the submitted revision",
    description=(
        "Requires `pending_approval`, the exact submitted `version` and a "
        "non-blank internal `comment` (max 2000 characters). Stores the "
        "decision and feedback with the exact revision, transitions to "
        "`changes_requested`, and keeps the comment out of the customer-facing "
        "body and out of general activity summaries."
    ),
)
def request_changes(
    db: DbSession,
    account: CurrentAccount,
    reply_id: ReplyIdPath,
    payload: ReplyRequestChanges,
) -> ReplyDetail:
    return reply_service.request_changes(
        db, reply_id, payload, principal=principal_for(account)
    )


@reply_router.post(
    "/{reply_id}/send-demo",
    response_model=ReplySendResult,
    responses=_REVIEW_ERROR_RESPONSES,
    dependencies=[CanSendDemo],
    summary="Mark an approved reply as sent (demo only)",
    description=(
        "**Marked as sent in demo mode — no customer message is delivered.** "
        "The server-side approval gate requires the current state to be "
        "`approved`, the approved version to equal the current revision, a "
        "stored approval decision for that revision, and a reply that was not "
        "already sent. The reply row is locked for the transition so concurrent "
        "send attempts cannot both succeed.\n\n"
        "On success, `new`/`open` tickets move to `pending` (matching the "
        "frontend demo rule) and one audit event records the simulated send."
    ),
)
def send_demo(
    db: DbSession,
    account: CurrentAccount,
    reply_id: ReplyIdPath,
    payload: ReplySendDemo,
) -> ReplySendResult:
    return reply_service.mark_sent_demo(
        db, reply_id, payload, principal=principal_for(account)
    )
