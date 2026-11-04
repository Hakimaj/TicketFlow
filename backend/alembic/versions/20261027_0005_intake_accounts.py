"""Ticket intake concurrency token and account provisioning flag.

Revision ID: 0005_intake_accounts
Revises: 0004_auth
Create Date: 2026-10-27

Additive only:

- ``tickets.version`` — integer concurrency token starting at 1. Every
  successful triage mutation increments it under a row lock, so a stale
  ``expected_version`` from another operator is rejected with ``409``.
- ``user_accounts.must_change_password`` — set when an administrator provisions
  an account with an initial password. Such an account can sign in but cannot
  use operational endpoints until it replaces that password.

Existing rows keep working: the server defaults backfill every ticket with
version 1 and every account with the flag disabled.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_intake_accounts"
down_revision: str | None = "0004_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "user_accounts",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_accounts", "must_change_password")
    op.drop_column("tickets", "version")
