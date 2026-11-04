"""Authentication: user accounts, refresh sessions and account attribution.

Revision ID: 0004_auth
Revises: 0003_reply_workflow
Create Date: 2026-10-23

Additive only. Historical rows keep their existing agent-based attribution and
receive a NULL account reference, which means "historical / unverified" rather
than inventing a verified account.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_auth"
down_revision: str | None = "0003_reply_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

account_role = postgresql.ENUM(
    "agent", "reviewer", "admin", name="account_role", create_type=False
)


def upgrade() -> None:
    op.execute("CREATE TYPE account_role AS ENUM ('agent', 'reviewer', 'admin')")

    op.create_table(
        "user_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("role", account_role, nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("agent_id", sa.String(length=16), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name="fk_user_accounts_agent_id_agents",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_accounts"),
        sa.UniqueConstraint("email", name="uq_user_accounts_email"),
    )
    op.create_index("ix_user_accounts_role", "user_accounts", ["role"])
    # Unique index (matches the model's unique=True, index=True) so at most
    # one account exists per support agent.
    op.create_index(
        "ix_user_accounts_agent_id", "user_accounts", ["agent_id"], unique=True
    )

    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            name="fk_refresh_sessions_user_id_user_accounts",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_sessions"),
    )
    op.create_index(
        "ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"]
    )
    # Unique index so one token hash can never be reused across sessions.
    op.create_index(
        "ix_refresh_sessions_token_hash",
        "refresh_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_refresh_sessions_user_expires",
        "refresh_sessions",
        ["user_id", "expires_at"],
    )

    attribution_columns = [
        ("ticket_activities", "actor_account_id", "ix_ticket_activities_actor_account_id"),
        ("ticket_notes", "author_account_id", "ix_ticket_notes_author_account_id"),
        ("customer_replies", "author_account_id", "ix_customer_replies_author_account_id"),
        ("reply_revisions", "author_account_id", "ix_reply_revisions_author_account_id"),
        ("reply_reviews", "reviewer_account_id", "ix_reply_reviews_reviewer_account_id"),
    ]
    for table, column, index_name in attribution_columns:
        op.add_column(table, sa.Column(column, sa.Uuid(), nullable=True))
        op.create_index(index_name, table, [column])
        op.create_foreign_key(
            f"fk_{table}_{column}_user_accounts",
            table,
            "user_accounts",
            [column],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    attribution_columns = [
        ("ticket_activities", "actor_account_id"),
        ("ticket_notes", "author_account_id"),
        ("customer_replies", "author_account_id"),
        ("reply_revisions", "author_account_id"),
        ("reply_reviews", "reviewer_account_id"),
    ]
    for table, column in reversed(attribution_columns):
        op.drop_constraint(
            f"fk_{table}_{column}_user_accounts", table, type_="foreignkey"
        )
        op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_column(table, column)

    op.drop_table("refresh_sessions")
    op.drop_table("user_accounts")
    op.execute("DROP TYPE account_role")
