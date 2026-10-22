"""Initial TicketFlow schema: requesters, agents, tickets, replies, activity.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-21

Enum values intentionally match the frontend TypeScript unions. Timestamps are
``timestamptz`` (UTC). No table is seeded here; demo data is seeded only by the
explicit, idempotent ``python -m scripts.seed`` command.

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Native PostgreSQL enum types, created once and shared between tables.
agent_role = postgresql.ENUM("admin", "supervisor", "agent", name="agent_role",
    create_type=False,
)
support_team = postgresql.ENUM(
    "customer_support",
    "billing_team",
    "logistics_team",
    "technical_support",
    "returns_team",
    name="support_team",
    create_type=False,
)
ticket_channel = postgresql.ENUM(
    "web_form", "email", "phone", "chat", name="ticket_channel",
    create_type=False,
)
ticket_category = postgresql.ENUM(
    "billing",
    "delivery",
    "technical",
    "returns",
    "general",
    name="ticket_category",
    create_type=False,
)
ticket_priority = postgresql.ENUM(
    "urgent", "high", "normal", "low", name="ticket_priority",
    create_type=False,
)
ticket_status = postgresql.ENUM(
    "new",
    "open",
    "pending",
    "needs_review",
    "resolved",
    "closed",
    name="ticket_status",
    create_type=False,
)
reply_state = postgresql.ENUM(
    "draft",
    "pending_approval",
    "approved",
    "changes_requested",
    "sent",
    name="reply_state",
    create_type=False,
)
activity_actor_type = postgresql.ENUM(
    "agent", "system", "automation", name="activity_actor_type",
    create_type=False,
)
activity_action = postgresql.ENUM(
    "created",
    "categorized",
    "assigned",
    "replied_draft",
    "replied_sent",
    "status_changed",
    "escalated",
    "review_flagged",
    "merged",
    "resolved",
    "priority_changed",
    "note_added",
    "reply_submitted",
    "reply_approved",
    "reply_changes_requested",
    name="activity_action",
    create_type=False,
)

ENUM_TYPES = (
    agent_role,
    support_team,
    ticket_channel,
    ticket_category,
    ticket_priority,
    ticket_status,
    reply_state,
    activity_actor_type,
    activity_action,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ENUM_TYPES:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", agent_role, nullable=False),
        sa.Column("team", support_team, nullable=True),
        sa.Column(
            "is_demo_user",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agents"),
        sa.UniqueConstraint("email", name="uq_agents_email"),
    )

    op.create_table(
        "requesters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requesters"),
        sa.UniqueConstraint("email", name="uq_requesters_email"),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("channel", ticket_channel, nullable=False),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("assigned_team", support_team, nullable=True),
        sa.Column("assigned_agent_id", sa.String(length=16), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suggested_category", ticket_category, nullable=True),
        sa.Column("suggested_priority", ticket_priority, nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "length(btrim(subject)) > 0", name="ck_tickets_subject_not_blank"
        ),
        sa.CheckConstraint(
            "public_id LIKE 'TF-%'", name="ck_tickets_public_id_prefixed"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_agent_id"],
            ["agents.id"],
            name="fk_tickets_assigned_agent_id_agents",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["requesters.id"],
            name="fk_tickets_requester_id_requesters",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tickets"),
        sa.UniqueConstraint("public_id", name="uq_tickets_public_id"),
    )
    op.create_index("ix_tickets_requester_id", "tickets", ["requester_id"])
    op.create_index("ix_tickets_category", "tickets", ["category"])
    op.create_index("ix_tickets_priority", "tickets", ["priority"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_assigned_agent_id", "tickets", ["assigned_agent_id"])
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])
    op.create_index(
        "ix_tickets_status_created_at", "tickets", ["status", "created_at"]
    )
    op.create_index(
        "ix_tickets_assigned_agent_status",
        "tickets",
        ["assigned_agent_id", "status"],
    )

    op.create_table(
        "customer_replies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.String(length=16), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("state", reply_state, nullable=False),
        sa.Column(
            "version", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_id", sa.String(length=16), nullable=True),
        sa.Column("reviewer_name", sa.String(length=160), nullable=True),
        sa.Column("reviewer_feedback", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by_actor_name", sa.String(length=160), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "version >= 1", name="ck_customer_replies_version_positive"
        ),
        sa.CheckConstraint(
            "state <> 'sent' OR (reviewed_at IS NOT NULL AND sent_at IS NOT NULL)",
            name="ck_customer_replies_sent_requires_review",
        ),
        sa.CheckConstraint(
            "sent_at IS NULL OR state = 'sent'",
            name="ck_customer_replies_sent_state_matches",
        ),
        sa.CheckConstraint(
            "public_id LIKE 'REP-%'",
            name="ck_customer_replies_public_id_prefixed",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["agents.id"],
            name="fk_customer_replies_author_id_agents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["agents.id"],
            name="fk_customer_replies_reviewer_id_agents",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_customer_replies_ticket_id_tickets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_replies"),
        sa.UniqueConstraint("public_id", name="uq_customer_replies_public_id"),
    )
    op.create_index(
        "ix_customer_replies_ticket_id", "customer_replies", ["ticket_id"]
    )
    op.create_index(
        "ix_customer_replies_author_id", "customer_replies", ["author_id"]
    )
    op.create_index(
        "ix_customer_replies_reviewer_id", "customer_replies", ["reviewer_id"]
    )
    op.create_index("ix_customer_replies_state", "customer_replies", ["state"])
    op.create_index(
        "ix_customer_replies_ticket_state",
        "customer_replies",
        ["ticket_id", "state"],
    )
    op.create_index(
        "uq_customer_replies_one_active_per_ticket",
        "customer_replies",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("state <> 'sent'"),
    )

    op.create_table(
        "ticket_activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.String(length=16), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("reply_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.String(length=16), nullable=True),
        sa.Column("actor_name", sa.String(length=160), nullable=False),
        sa.Column("actor_type", activity_actor_type, nullable=False),
        sa.Column("action", activity_action, nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "is_internal_note",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "public_id LIKE 'ACT-%'",
            name="ck_ticket_activities_public_id_prefixed",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["agents.id"],
            name="fk_ticket_activities_actor_id_agents",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reply_id"],
            ["customer_replies.id"],
            name="fk_ticket_activities_reply_id_customer_replies",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_ticket_activities_ticket_id_tickets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_activities"),
        sa.UniqueConstraint("public_id", name="uq_ticket_activities_public_id"),
    )
    op.create_index(
        "ix_ticket_activities_ticket_id", "ticket_activities", ["ticket_id"]
    )
    op.create_index("ix_ticket_activities_reply_id", "ticket_activities", ["reply_id"])
    op.create_index("ix_ticket_activities_actor_id", "ticket_activities", ["actor_id"])
    op.create_index("ix_ticket_activities_action", "ticket_activities", ["action"])
    op.create_index(
        "ix_ticket_activities_created_at", "ticket_activities", ["created_at"]
    )
    op.create_index(
        "ix_ticket_activities_ticket_created",
        "ticket_activities",
        ["ticket_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("ticket_activities")
    op.drop_table("customer_replies")
    op.drop_table("tickets")
    op.drop_table("requesters")
    op.drop_table("agents")

    bind = op.get_bind()
    for enum_type in reversed(ENUM_TYPES):
        enum_type.drop(bind, checkfirst=True)
