"""Migration consistency and database-level constraint tests (real PostgreSQL)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.models.enums import (
    ActivityAction,
    ActivityActorType,
    AgentRole,
    ReplyReviewDecision,
    ReplyState,
    SupportTeam,
    TicketCategory,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ},
        capture_output=True,
        text=True,
        check=False,
    )


def test_database_is_at_head_revision() -> None:
    result = _alembic("current")
    assert result.returncode == 0, result.stderr
    assert "0005_intake_accounts (head)" in result.stdout


def test_models_and_migrations_are_in_sync() -> None:
    """`alembic check` fails when models add/remove anything unauthored."""
    result = _alembic("check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No new upgrade operations detected" in result.stdout


def test_all_expected_tables_exist(db_engine) -> None:
    inspector = inspect(db_engine)
    assert set(inspector.get_table_names()) == {
        "agents",
        "requesters",
        "tickets",
        "customer_replies",
        "reply_revisions",
        "reply_reviews",
        "ticket_activities",
        "ticket_notes",
        "user_accounts",
        "refresh_sessions",
        "alembic_version",
    }


def test_ticket_indexes_cover_queue_columns(db_engine) -> None:
    index_names = {
        index["name"] for index in inspect(db_engine).get_indexes("tickets")
    }
    assert {
        "ix_tickets_status",
        "ix_tickets_category",
        "ix_tickets_priority",
        "ix_tickets_assigned_agent_id",
        "ix_tickets_created_at",
        "ix_tickets_status_created_at",
        "ix_tickets_assigned_agent_status",
    } <= index_names

    uniques = {
        constraint["name"]
        for constraint in inspect(db_engine).get_unique_constraints("tickets")
    }
    assert "uq_tickets_public_id" in uniques


def test_only_one_active_reply_per_ticket_index(db_engine) -> None:
    with db_engine.connect() as connection:
        indexdef = connection.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'uq_customer_replies_one_active_per_ticket'"
            )
        )
    assert indexdef is not None
    assert "UNIQUE" in indexdef
    assert "WHERE" in indexdef and "sent" in indexdef


def test_enum_labels_match_frontend_contract(db_engine) -> None:
    from app.models.enums import AccountRole

    expected = {
        "agent_role": [member.value for member in AgentRole],
        "support_team": [member.value for member in SupportTeam],
        "ticket_status": [member.value for member in TicketStatus],
        "ticket_priority": [member.value for member in TicketPriority],
        "ticket_category": [member.value for member in TicketCategory],
        "ticket_channel": [member.value for member in TicketChannel],
        "reply_state": [member.value for member in ReplyState],
        "reply_review_decision": [
            member.value for member in ReplyReviewDecision
        ],
        "activity_actor_type": [member.value for member in ActivityActorType],
        "activity_action": [member.value for member in ActivityAction],
        "account_role": [member.value for member in AccountRole],
    }
    with db_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT t.typname, e.enumlabel FROM pg_type t "
                "JOIN pg_enum e ON e.enumtypid = t.oid "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE n.nspname = 'public' ORDER BY t.typname, e.enumsortorder"
            )
        ).all()

    actual: dict[str, list[str]] = {}
    for type_name, label in rows:
        actual.setdefault(type_name, []).append(label)
    assert actual == expected


def test_timestamps_are_timezone_aware(db_engine) -> None:
    with db_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT table_name, column_name, data_type "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND column_name IN ('created_at', 'updated_at')"
            )
        ).all()
    assert rows
    for table_name, column_name, data_type in rows:
        assert data_type == "timestamp with time zone", (table_name, column_name)


def test_foreign_keys_declare_deletion_behaviour(db_engine) -> None:
    inspector = inspect(db_engine)
    ticket_fks = {
        fk["name"]: fk["options"].get("ondelete")
        for fk in inspector.get_foreign_keys("tickets")
    }
    assert ticket_fks["fk_tickets_requester_id_requesters"] == "RESTRICT"
    assert ticket_fks["fk_tickets_assigned_agent_id_agents"] == "SET NULL"

    reply_fks = {
        fk["name"]: fk["options"].get("ondelete")
        for fk in inspector.get_foreign_keys("customer_replies")
    }
    assert reply_fks["fk_customer_replies_ticket_id_tickets"] == "CASCADE"

    note_fks = {
        fk["name"]: fk["options"].get("ondelete")
        for fk in inspector.get_foreign_keys("ticket_notes")
    }
    assert note_fks["fk_ticket_notes_ticket_id_tickets"] == "CASCADE"
    assert note_fks["fk_ticket_notes_author_id_agents"] == "RESTRICT"

    activity_fks = {
        fk["name"]: fk["options"].get("ondelete")
        for fk in inspector.get_foreign_keys("ticket_activities")
    }
    assert activity_fks["fk_ticket_activities_note_id_ticket_notes"] == "SET NULL"


def test_note_table_indexes_and_constraints(db_engine) -> None:
    inspector = inspect(db_engine)
    indexes = {
        index["name"] for index in inspector.get_indexes("ticket_notes")
    }
    assert {"ix_ticket_notes_author_id", "ix_ticket_notes_ticket_created"} <= indexes

    with db_engine.connect() as connection:
        checks = dict(
            connection.execute(
                text(
                    "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conrelid = 'ticket_notes'::regclass AND contype = 'c'"
                )
            ).all()
        )
    assert "ck_ticket_notes_content_not_blank" in checks
    assert "ck_ticket_notes_content_max_length" in checks
    assert "4000" in checks["ck_ticket_notes_content_max_length"]


def test_database_rejects_blank_and_oversized_notes(db_session) -> None:
    from app.models.agent import Agent
    from app.models.note import TicketNote
    from app.models.requester import Requester
    from app.models.ticket import Ticket

    requester = Requester(name="Note Tester", email="note@example.test")
    agent = Agent(
        id="AG-98",
        name="Note Agent",
        email="note.agent@example.test",
        role=AgentRole.AGENT,
    )
    db_session.add_all([requester, agent])
    db_session.flush()
    ticket = Ticket(
        public_id="TF-9200",
        subject="Note constraints",
        description="Checking note constraints.",
        requester_id=requester.id,
        channel=TicketChannel.WEB_FORM,
        category=TicketCategory.GENERAL,
        priority=TicketPriority.NORMAL,
        status=TicketStatus.OPEN,
    )
    db_session.add(ticket)
    db_session.flush()

    for invalid in ("   ", "x" * 4001):
        with pytest.raises(IntegrityError):
            with db_session.begin_nested():
                db_session.add(
                    TicketNote(
                        ticket_id=ticket.id,
                        author_id=agent.id,
                        content=invalid,
                    )
                )
                db_session.flush()


def test_database_rejects_sent_reply_without_review(db_session) -> None:
    from app.models.agent import Agent
    from app.models.reply import CustomerReply
    from app.models.requester import Requester
    from app.models.ticket import Ticket

    requester = Requester(name="Constraint Tester", email="constraint@example.test")
    agent = Agent(
        id="AG-99",
        name="Constraint Agent",
        email="agent@example.test",
        role=AgentRole.AGENT,
    )
    db_session.add_all([requester, agent])
    db_session.flush()
    ticket = Ticket(
        public_id="TF-9001",
        subject="Constraint check",
        description="Testing database constraints.",
        requester_id=requester.id,
        channel=TicketChannel.WEB_FORM,
        category=TicketCategory.GENERAL,
        priority=TicketPriority.LOW,
        status=TicketStatus.OPEN,
    )
    db_session.add(ticket)
    db_session.flush()

    db_session.add(
        CustomerReply(
            public_id="REP-901",
            ticket_id=ticket.id,
            author_id="AG-99",
            body="Body",
            state=ReplyState.SENT,
            version=1,
            sent_at=None,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_database_rejects_duplicate_public_ticket_id(db_session) -> None:
    from app.models.requester import Requester
    from app.models.ticket import Ticket

    requester = Requester(name="Dupe Tester", email="dupe@example.test")
    db_session.add(requester)
    db_session.flush()

    def make() -> Ticket:
        return Ticket(
            public_id="TF-9100",
            subject="Duplicate",
            description="Duplicate public id.",
            requester_id=requester.id,
            channel=TicketChannel.EMAIL,
            category=TicketCategory.BILLING,
            priority=TicketPriority.NORMAL,
            status=TicketStatus.NEW,
        )

    db_session.add(make())
    db_session.flush()
    db_session.add(make())
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_downgrade_and_upgrade_round_trip(db_engine) -> None:
    downgrade = _alembic("downgrade", "base")
    assert downgrade.returncode == 0, downgrade.stderr
    inspector = inspect(db_engine)
    assert "tickets" not in inspector.get_table_names()

    upgrade = _alembic("upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr
    # Inspection caches are per-call; re-create to see the new tables.
    fresh = inspect(db_engine)
    assert set(fresh.get_table_names()) >= {
        "agents",
        "requesters",
        "tickets",
        "customer_replies",
        "reply_revisions",
        "reply_reviews",
        "ticket_activities",
        "ticket_notes",
    }


def _seed_workflow_ticket(db_session) -> tuple:
    from app.models.agent import Agent
    from app.models.requester import Requester
    from app.models.ticket import Ticket

    requester = Requester(name="Reply Tester", email="reply@example.test")
    agent = Agent(
        id="AG-97",
        name="Reply Agent",
        email="reply.agent@example.test",
        role=AgentRole.AGENT,
    )
    db_session.add_all([requester, agent])
    db_session.flush()
    ticket = Ticket(
        public_id="TF-9300",
        subject="Reply constraints",
        description="Checking reply constraints.",
        requester_id=requester.id,
        channel=TicketChannel.EMAIL,
        category=TicketCategory.GENERAL,
        priority=TicketPriority.NORMAL,
        status=TicketStatus.OPEN,
    )
    db_session.add(ticket)
    db_session.flush()
    return ticket, agent


def test_reply_workflow_indexes_and_audit_column(db_engine) -> None:
    inspector = inspect(db_engine)
    revision_indexes = {
        index["name"] for index in inspector.get_indexes("reply_revisions")
    }
    assert {
        "ix_reply_revisions_reply_id",
        "ix_reply_revisions_author_id",
        "ix_reply_revisions_reply_created",
        "uq_reply_revisions_reply_version",
    } <= revision_indexes

    review_indexes = {
        index["name"] for index in inspector.get_indexes("reply_reviews")
    }
    assert {
        "ix_reply_reviews_reply_created",
        "ix_reply_reviews_reply_version_decision",
        "ix_reply_reviews_decision",
    } <= review_indexes

    reply_indexes = {
        index["name"] for index in inspector.get_indexes("customer_replies")
    }
    assert "ix_customer_replies_state_submitted" in reply_indexes

    activity_columns = {
        column["name"]
        for column in inspector.get_columns("ticket_activities")
    }
    assert "reply_version" in activity_columns

    with db_engine.connect() as connection:
        reply_checks = {
            name
            for (name,) in connection.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'customer_replies'::regclass "
                    "AND contype = 'c'"
                )
            )
        }
    assert {
        "ck_customer_replies_body_not_blank",
        "ck_customer_replies_body_max_length",
        "ck_customer_replies_sent_matches_approval",
        "ck_customer_replies_approved_matches_version",
        "ck_customer_replies_approval_metadata_complete",
    } <= reply_checks


@pytest.mark.parametrize(
    "state, approved_version, reviewer, reviewed_at, sent_at",
    [
        (ReplyState.APPROVED, None, True, True, None),
        (ReplyState.APPROVED, 2, True, True, None),
        (ReplyState.SENT, None, True, True, "now"),
        (ReplyState.SENT, 2, True, True, "now"),
    ],
)
def test_database_enforces_approval_gate(
    db_session, state, approved_version, reviewer, reviewed_at, sent_at
) -> None:
    from app.models.common import utcnow
    from app.models.reply import CustomerReply

    ticket, agent = _seed_workflow_ticket(db_session)
    now = utcnow()

    db_session.add(
        CustomerReply(
            public_id="REP-902",
            ticket_id=ticket.id,
            author_id=agent.id,
            body="Body",
            state=state,
            version=1,
            submitted_version=1,
            submitted_at=now,
            approved_version=approved_version,
            reviewer_id=agent.id if reviewer else None,
            reviewer_name=agent.name if reviewer else None,
            reviewed_at=now if reviewed_at else None,
            sent_at=now if sent_at else None,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_database_rejects_blank_or_oversized_reply_body(db_session) -> None:
    from app.models.reply import CustomerReply

    ticket, agent = _seed_workflow_ticket(db_session)
    for index, invalid in enumerate(("   ", "x" * 8001)):
        with pytest.raises(IntegrityError):
            with db_session.begin_nested():
                db_session.add(
                    CustomerReply(
                        public_id=f"REP-91{index}",
                        ticket_id=ticket.id,
                        author_id=agent.id,
                        body=invalid,
                        state=ReplyState.DRAFT,
                        version=1,
                    )
                )
                db_session.flush()


def test_revision_versions_are_unique_per_reply(db_session) -> None:
    from app.models.reply import CustomerReply, ReplyRevision

    ticket, agent = _seed_workflow_ticket(db_session)
    reply = CustomerReply(
        public_id="REP-903",
        ticket_id=ticket.id,
        author_id=agent.id,
        body="Body",
        state=ReplyState.DRAFT,
        version=2,
    )
    db_session.add(reply)
    db_session.flush()

    for version in (1, 2):
        db_session.add(
            ReplyRevision(
                reply_id=reply.id,
                version=version,
                body=f"Body v{version}",
                author_id=agent.id,
            )
        )
    db_session.flush()

    db_session.add(
        ReplyRevision(
            reply_id=reply.id,
            version=2,
            body="Duplicate version",
            author_id=agent.id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_change_request_review_requires_internal_comment(db_session) -> None:
    from app.models.reply import CustomerReply, ReplyReview, ReplyRevision

    ticket, agent = _seed_workflow_ticket(db_session)
    reply = CustomerReply(
        public_id="REP-904",
        ticket_id=ticket.id,
        author_id=agent.id,
        body="Body",
        state=ReplyState.PENDING_APPROVAL,
        version=1,
        submitted_version=1,
    )
    db_session.add(reply)
    db_session.flush()
    revision = ReplyRevision(
        reply_id=reply.id, version=1, body="Body", author_id=agent.id
    )
    db_session.add(revision)
    db_session.flush()

    db_session.add(
        ReplyReview(
            reply_id=reply.id,
            revision_id=revision.id,
            version=1,
            decision=ReplyReviewDecision.CHANGES_REQUESTED,
            reviewer_id=agent.id,
            reviewer_name=agent.name,
            comment="   ",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
