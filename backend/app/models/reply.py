"""Customer replies, immutable text revisions and review decisions.

The logical reply (``customer_replies``) holds the *current* workflow state and
the current revision number/body. Every distinct body is also stored in
``reply_revisions`` as an immutable snapshot, and every human review decision is
stored in ``reply_reviews`` (append-only). This keeps the mutable workflow
metadata on one row while preserving exactly which text was reviewed, approved
and marked as sent.

``reviewer_feedback`` on the logical reply is the *current* reviewer comment.
It is internal and must never be projected into a customer-visible response.
Historical comments survive in ``reply_reviews`` even after the reply is
revised and the current feedback is cleared.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, enum_type, utcnow
from app.models.enums import ReplyReviewDecision, ReplyState

if TYPE_CHECKING:
    from app.models.activity import TicketActivity
    from app.models.agent import Agent
    from app.models.ticket import Ticket

# Reply bodies are customer-facing text; 8k characters is ample for a support
# response and keeps a single payload bounded.
REPLY_MAX_LENGTH = 8000
# Internal reviewer comments are deliberately shorter than the reply itself.
REVIEW_COMMENT_MAX_LENGTH = 2000


class CustomerReply(TimestampMixin, Base):
    """A logical customer reply and its current workflow metadata.

    State transitions are owned by :mod:`app.services.replies`; the database
    constraints below enforce the essential invariants (an approved reply's
    ``approved_version`` must be its current version, and a ``sent`` reply can
    only exist with an approval for that exact version).
    """

    __tablename__ = "customer_replies"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    public_id: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Verified account that created the draft. Null for historical replies.
    author_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Current revision body. Always mirrored into ``reply_revisions`` with the
    # same ``version`` in the same transaction.
    body: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[ReplyState] = mapped_column(
        enum_type(ReplyState, "reply_state"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The exact version that was submitted for review.
    submitted_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewer_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Snapshot of the reviewer's display name for historical audit display.
    reviewer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reviewer_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The exact version a human approved. Only this version may be demo-sent.
    approved_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_by_actor_name: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="replies")
    author: Mapped["Agent"] = relationship(
        back_populates="authored_replies", foreign_keys=[author_id]
    )
    reviewer: Mapped["Agent | None"] = relationship(
        back_populates="reviewed_replies", foreign_keys=[reviewer_id]
    )
    revisions: Mapped[list["ReplyRevision"]] = relationship(
        back_populates="reply",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReplyRevision.version",
    )
    reviews: Mapped[list["ReplyReview"]] = relationship(
        back_populates="reply",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReplyReview.created_at",
    )
    activities: Mapped[list["TicketActivity"]] = relationship(
        back_populates="reply", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "length(btrim(body)) > 0", name="body_not_blank"
        ),
        CheckConstraint(
            f"length(body) <= {REPLY_MAX_LENGTH}", name="body_max_length"
        ),
        CheckConstraint(
            "state <> 'sent' OR (reviewed_at IS NOT NULL AND sent_at IS NOT NULL)",
            name="sent_requires_review",
        ),
        CheckConstraint(
            "sent_at IS NULL OR state = 'sent'", name="sent_state_matches"
        ),
        # Submission/approval metadata must always point at a real version, and
        # a pending/approved reply is about its current version.
        CheckConstraint(
            "submitted_version IS NULL OR "
            "(submitted_version >= 1 AND submitted_version <= version)",
            name="submitted_version_valid",
        ),
        CheckConstraint(
            "state <> 'pending_approval' OR "
            "(submitted_version IS NOT NULL AND submitted_version = version)",
            name="pending_matches_submission",
        ),
        CheckConstraint(
            "approved_version IS NULL OR "
            "(approved_version >= 1 AND approved_version <= version "
            "AND reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="approval_metadata_complete",
        ),
        CheckConstraint(
            "state <> 'approved' OR "
            "(approved_version IS NOT NULL AND approved_version = version)",
            name="approved_matches_version",
        ),
        # The approval gate, enforced by the database itself: a reply cannot be
        # flagged as sent unless its *current* version carries an approval.
        # The explicit NULL check matters because `NULL = version` is NULL, and
        # a CHECK constraint accepts NULL.
        CheckConstraint(
            "state <> 'sent' OR "
            "(approved_version IS NOT NULL AND approved_version = version)",
            name="sent_matches_approval",
        ),
        CheckConstraint(
            "public_id LIKE 'REP-%'", name="public_id_prefixed"
        ),
        # One in-flight reply per ticket; sent replies are immutable history and
        # a new reply record starts afterwards (matches the frontend workflow).
        Index(
            "uq_customer_replies_one_active_per_ticket",
            "ticket_id",
            unique=True,
            postgresql_where=text("state <> 'sent'"),
        ),
        Index("ix_customer_replies_ticket_state", "ticket_id", "state"),
        Index("ix_customer_replies_state_submitted", "state", "submitted_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"CustomerReply(public_id={self.public_id!r}, state={self.state!r})"


class ReplyRevision(Base):
    """An immutable snapshot of one reply body.

    Rows are inserted once and never updated. ``(reply_id, version)`` is unique,
    so a version number always identifies exactly one body.
    """

    __tablename__ = "reply_revisions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reply_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_replies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    author_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    reply: Mapped["CustomerReply"] = relationship(back_populates="revisions")
    author: Mapped["Agent"] = relationship()
    reviews: Mapped[list["ReplyReview"]] = relationship(
        back_populates="revision", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint(
            "reply_id", "version", name="uq_reply_revisions_reply_version"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("length(btrim(body)) > 0", name="body_not_blank"),
        CheckConstraint(
            f"length(body) <= {REPLY_MAX_LENGTH}", name="body_max_length"
        ),
        Index("ix_reply_revisions_reply_created", "reply_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ReplyRevision(reply_id={self.reply_id!r}, version={self.version!r})"


class ReplyReview(Base):
    """An append-only human review decision for one exact revision.

    ``comment`` is internal reviewer feedback. It is never copied into the
    customer-visible reply body or into a general activity summary.
    """

    __tablename__ = "reply_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reply_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_replies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reply_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[ReplyReviewDecision] = mapped_column(
        enum_type(ReplyReviewDecision, "reply_review_decision"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewer_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Display-name snapshot so history survives agent renames or removal.
    reviewer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    reply: Mapped["CustomerReply"] = relationship(back_populates="reviews")
    revision: Mapped["ReplyRevision"] = relationship(back_populates="reviews")
    reviewer: Mapped["Agent | None"] = relationship()

    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "decision <> 'changes_requested' OR "
            "(comment IS NOT NULL AND length(btrim(comment)) > 0)",
            name="changes_requested_requires_comment",
        ),
        CheckConstraint(
            "comment IS NULL OR length(comment) <= "
            f"{REVIEW_COMMENT_MAX_LENGTH}",
            name="comment_max_length",
        ),
        Index("ix_reply_reviews_reply_created", "reply_id", "created_at"),
        Index(
            "ix_reply_reviews_reply_version_decision",
            "reply_id",
            "version",
            "decision",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"ReplyReview(reply_id={self.reply_id!r}, "
            f"version={self.version!r}, decision={self.decision!r})"
        )


__all__ = [
    "CustomerReply",
    "REPLY_MAX_LENGTH",
    "REVIEW_COMMENT_MAX_LENGTH",
    "ReplyRevision",
    "ReplyReview",
]
