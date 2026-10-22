"""Ticket operations: persistent internal notes and activity note links.

Revision ID: 0002_ticket_operations
Revises: 0001_initial
Create Date: 2026-10-21

Additive only. The Phase 5 migration is intentionally untouched. Note bodies
live in ``ticket_notes``; ``ticket_activities`` links to them via ``note_id``
and stores only a concise summary, so general activity metadata never contains
the note body.

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_ticket_operations"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
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
        # Short names: the metadata naming convention prefixes
        # ``ck_ticket_notes_`` when the table is created.
        sa.CheckConstraint(
            "length(btrim(content)) > 0", name="content_not_blank"
        ),
        sa.CheckConstraint(
            "length(content) <= 4000", name="content_max_length"
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["agents.id"],
            name="fk_ticket_notes_author_id_agents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_ticket_notes_ticket_id_tickets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_notes"),
    )
    op.create_index("ix_ticket_notes_author_id", "ticket_notes", ["author_id"])
    op.create_index(
        "ix_ticket_notes_ticket_created", "ticket_notes", ["ticket_id", "created_at"]
    )

    op.add_column(
        "ticket_activities",
        sa.Column("note_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_ticket_activities_note_id", "ticket_activities", ["note_id"]
    )
    op.create_foreign_key(
        "fk_ticket_activities_note_id_ticket_notes",
        "ticket_activities",
        "ticket_notes",
        ["note_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ticket_activities_note_id_ticket_notes",
        "ticket_activities",
        type_="foreignkey",
    )
    op.drop_index("ix_ticket_activities_note_id", table_name="ticket_activities")
    op.drop_column("ticket_activities", "note_id")
    op.drop_index("ix_ticket_notes_ticket_created", table_name="ticket_notes")
    op.drop_index("ix_ticket_notes_author_id", table_name="ticket_notes")
    op.drop_table("ticket_notes")
