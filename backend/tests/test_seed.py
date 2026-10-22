"""Idempotent seeding and consistency of the demonstration fixtures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models.activity import TicketActivity
from app.models.agent import Agent
from app.models.enums import TicketStatus
from app.models.reply import CustomerReply
from app.models.requester import Requester
from app.models.ticket import Ticket
from app.seed import (
    ACTIVITY_SEEDS,
    AGENT_SEEDS,
    REPLY_SEEDS,
    TICKET_SEEDS,
    seed_demo_data,
)

ANCHOR = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def _count(session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_seed_creates_all_fixtures_once(session_factory, clean_db) -> None:
    with session_factory() as session:
        report = seed_demo_data(session, anchor=ANCHOR)
        session.commit()

        assert report.created == {
            "agents": len(AGENT_SEEDS),
            "requesters": len(TICKET_SEEDS),
            "tickets": len(TICKET_SEEDS),
            "customer_replies": len(REPLY_SEEDS),
            "ticket_activities": len(ACTIVITY_SEEDS),
        }
        assert report.skipped == {}

        assert _count(session, Agent) == len(AGENT_SEEDS)
        assert _count(session, Ticket) == len(TICKET_SEEDS)
        assert _count(session, Requester) == len(TICKET_SEEDS)
        assert _count(session, CustomerReply) == len(REPLY_SEEDS)
        assert _count(session, TicketActivity) == len(ACTIVITY_SEEDS)


def test_seed_is_idempotent(session_factory, clean_db) -> None:
    with session_factory() as session:
        seed_demo_data(session, anchor=ANCHOR)
        session.commit()

        second = seed_demo_data(session, anchor=ANCHOR)
        session.commit()

        assert second.created == {}
        assert second.skipped["tickets"] == len(TICKET_SEEDS)
        assert second.skipped["customer_replies"] == len(REPLY_SEEDS)
        assert _count(session, Ticket) == len(TICKET_SEEDS)
        assert _count(session, CustomerReply) == len(REPLY_SEEDS)


def test_seed_never_overwrites_local_changes(session_factory, clean_db) -> None:
    with session_factory() as session:
        seed_demo_data(session, anchor=ANCHOR)
        session.commit()

        ticket = session.scalar(select(Ticket).where(Ticket.public_id == "TF-1051"))
        ticket.status = TicketStatus.CLOSED
        ticket.subject = "Locally edited subject"
        session.commit()

        seed_demo_data(session, anchor=ANCHOR)
        session.commit()
        session.expire_all()

        reloaded = session.scalar(
            select(Ticket).where(Ticket.public_id == "TF-1051")
        )
        assert reloaded.subject == "Locally edited subject"
        assert reloaded.status.value == "closed"


def test_reply_fixtures_match_their_tickets_and_requesters(
    session_factory, clean_db
) -> None:
    """Regression guard for the Phase 3 wrong-customer/wrong-product issue."""
    expected = {
        "REP-101": ("TF-1051", "Marta Alemu"),
        "REP-102": ("TF-1048", "Samuel Bekele"),
        "REP-103": ("TF-1045", "Hirut Wolde"),
        "REP-104": ("TF-1047", "Tigist Fikru"),
        "REP-105": ("TF-1044", "Nahom Girma"),
    }
    with session_factory() as session:
        seed_demo_data(session, anchor=ANCHOR)
        session.commit()

        rows = session.execute(
            select(CustomerReply.public_id, Ticket.public_id, Requester.name)
            .join(Ticket, Ticket.id == CustomerReply.ticket_id)
            .join(Requester, Requester.id == Ticket.requester_id)
        ).all()
        actual = {reply: (ticket, name) for reply, ticket, name in rows}
        assert actual == expected


def test_reply_review_feedback_is_internal_and_separate(
    session_factory, clean_db
) -> None:
    with session_factory() as session:
        seed_demo_data(session, anchor=ANCHOR)
        session.commit()

        reply = session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == "REP-104")
        )
        assert reply.reviewer_name == "Abebe Kebede"
        assert reply.reviewer_id == "AG-01"
        assert reply.reviewer_feedback
        assert reply.reviewer_feedback not in reply.body
        # Reviewer feedback never leaks into the customer-visible body.
        assert "size L is actually in stock" not in reply.body


def test_seeded_timestamps_are_utc_aware(session_factory, clean_db) -> None:
    with session_factory() as session:
        seed_demo_data(session, anchor=ANCHOR)
        session.commit()

        tickets = session.scalars(select(Ticket)).all()
        assert tickets
        for ticket in tickets:
            assert ticket.created_at.tzinfo is not None
            assert ticket.created_at.utcoffset() == timedelta(0)
            assert ticket.created_at <= ANCHOR


def test_activity_metadata_contains_no_customer_pii(
    session_factory, clean_db
) -> None:
    with session_factory() as session:
        seed_demo_data(session, anchor=ANCHOR)
        session.commit()

        activities = session.scalars(select(TicketActivity)).all()
        assert activities
        for activity in activities:
            detail = activity.detail or ""
            assert "@" not in detail
            assert "myetmail.example" not in detail
            # No full customer messages are copied into audit rows.
            assert len(detail) < 300
