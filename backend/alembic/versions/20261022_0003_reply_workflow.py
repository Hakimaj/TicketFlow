"""Reply workflow: immutable revisions, review decisions and approval metadata.

Revision ID: 0003_reply_workflow
Revises: 0002_ticket_operations
Create Date: 2026-10-22

Additive only: the Phase 5 and Phase 6 migrations are intentionally untouched.

* ``reply_revisions`` stores one immutable snapshot per reply version.
* ``reply_reviews`` is an append-only record of the exact version reviewed and
  the human decision (approval or request-changes). Reviewer comments stay
  internal and live only here (and in the reply's current feedback column).
* ``customer_replies`` gains ``submitted_version`` and ``approved_version`` so
  an approval is attributable to one exact revision.
* ``ticket_activities`` gains ``reply_version`` for revision-level audit links.

Existing rows are backfilled: every existing reply gets revision 1 from its
current body, and approval metadata is derived from the pre-existing columns.
The database then enforces that an ``approved`` reply's ``approved_version`` is
its current version and that a ``sent`` reply can only exist when that exact
version was approved.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_reply_workflow"
down_revision: str | None = "0002_ticket_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REPLY_MAX_LENGTH = 8000
REVIEW_COMMENT_MAX_LENGTH = 2000

reply_review_decision = postgresql.ENUM(
    "approved",
    "changes_requested",
    name="reply_review_decision",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE reply_review_decision AS ENUM "
        "('approved', 'changes_requested')"
    )

    op.create_table(
        "reply_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reply_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        # Short names: the metadata naming convention prefixes the table name.
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint("length(btrim(body)) > 0", name="body_not_blank"),
        sa.CheckConstraint(
            f"length(body) <= {REPLY_MAX_LENGTH}", name="body_max_length"
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["agents.id"],
            name="fk_reply_revisions_author_id_agents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reply_id"],
            ["customer_replies.id"],
            name="fk_reply_revisions_reply_id_customer_replies",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reply_revisions"),
        sa.UniqueConstraint(
            "reply_id", "version", name="uq_reply_revisions_reply_version"
        ),
    )
    op.create_index(
        "ix_reply_revisions_author_id", "reply_revisions", ["author_id"]
    )
    op.create_index("ix_reply_revisions_reply_id", "reply_revisions", ["reply_id"])
    op.create_index(
        "ix_reply_revisions_reply_created",
        "reply_revisions",
        ["reply_id", "created_at"],
    )

    # Backfill one immutable snapshot for every reply that predates revisions.
    op.execute(
        """
        INSERT INTO reply_revisions (id, reply_id, version, body, author_id, created_at)
        SELECT gen_random_uuid(), id, version, body, author_id, created_at
        FROM customer_replies
        """
    )

    op.add_column(
        "customer_replies",
        sa.Column("submitted_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "customer_replies",
        sa.Column("approved_version", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE customer_replies SET submitted_version = version "
        "WHERE submitted_at IS NOT NULL"
    )
    op.execute(
        "UPDATE customer_replies SET approved_version = version "
        "WHERE state IN ('approved', 'sent') "
        "AND reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL"
    )

    op.create_table(
        "reply_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reply_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("decision", reply_review_decision, nullable=False),
        sa.Column("reviewer_id", sa.String(length=16), nullable=True),
        sa.Column("reviewer_name", sa.String(length=160), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint(
            "decision <> 'changes_requested' OR "
            "(comment IS NOT NULL AND length(btrim(comment)) > 0)",
            name="changes_requested_requires_comment",
        ),
        sa.CheckConstraint(
            f"comment IS NULL OR length(comment) <= {REVIEW_COMMENT_MAX_LENGTH}",
            name="comment_max_length",
        ),
        sa.ForeignKeyConstraint(
            ["reply_id"],
            ["customer_replies.id"],
            name="fk_reply_reviews_reply_id_customer_replies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["reply_revisions.id"],
            name="fk_reply_reviews_revision_id_reply_revisions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["agents.id"],
            name="fk_reply_reviews_reviewer_id_agents",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reply_reviews"),
    )
    op.create_index("ix_reply_reviews_reply_id", "reply_reviews", ["reply_id"])
    op.create_index(
        "ix_reply_reviews_revision_id", "reply_reviews", ["revision_id"]
    )
    op.create_index("ix_reply_reviews_decision", "reply_reviews", ["decision"])
    op.create_index(
        "ix_reply_reviews_reviewer_id", "reply_reviews", ["reviewer_id"]
    )
    op.create_index(
        "ix_reply_reviews_reply_created",
        "reply_reviews",
        ["reply_id", "created_at"],
    )
    op.create_index(
        "ix_reply_reviews_reply_version_decision",
        "reply_reviews",
        ["reply_id", "version", "decision"],
    )

    # Body invariants (the Phase 5 table had none) plus the approval gate,
    # added after the backfill so existing demo rows are already consistent.
    op.create_check_constraint(
        "body_not_blank",
        "customer_replies",
        "length(btrim(body)) > 0",
    )
    op.create_check_constraint(
        "body_max_length",
        "customer_replies",
        f"length(body) <= {REPLY_MAX_LENGTH}",
    )
    op.create_check_constraint(
        "submitted_version_valid",
        "customer_replies",
        "submitted_version IS NULL OR "
        "(submitted_version >= 1 AND submitted_version <= version)",
    )
    op.create_check_constraint(
        "pending_matches_submission",
        "customer_replies",
        "state <> 'pending_approval' OR "
        "(submitted_version IS NOT NULL AND submitted_version = version)",
    )
    op.create_check_constraint(
        "approval_metadata_complete",
        "customer_replies",
        "approved_version IS NULL OR "
        "(approved_version >= 1 AND approved_version <= version "
        "AND reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "approved_matches_version",
        "customer_replies",
        "state <> 'approved' OR "
        "(approved_version IS NOT NULL AND approved_version = version)",
    )
    # `NULL = version` evaluates to NULL, which a CHECK constraint accepts, so
    # the NULL guard is required for this to be a real gate.
    op.create_check_constraint(
        "sent_matches_approval",
        "customer_replies",
        "state <> 'sent' OR "
        "(approved_version IS NOT NULL AND approved_version = version)",
    )
    op.create_index(
        "ix_customer_replies_state_submitted",
        "customer_replies",
        ["state", "submitted_at"],
    )

    op.add_column(
        "ticket_activities",
        sa.Column("reply_version", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ticket_activities", "reply_version")

    op.drop_index(
        "ix_customer_replies_state_submitted", table_name="customer_replies"
    )
    for constraint in (
        "sent_matches_approval",
        "approved_matches_version",
        "approval_metadata_complete",
        "pending_matches_submission",
        "submitted_version_valid",
        "body_max_length",
        "body_not_blank",
    ):
        # Short name: Alembic re-applies the metadata naming convention and
        # resolves it to ``ck_customer_replies_<name>``.
        op.drop_constraint(
            constraint,
            "customer_replies",
            type_="check",
        )

    op.drop_table("reply_reviews")
    op.drop_column("customer_replies", "approved_version")
    op.drop_column("customer_replies", "submitted_version")
    op.drop_table("reply_revisions")
    op.execute("DROP TYPE reply_review_decision")
