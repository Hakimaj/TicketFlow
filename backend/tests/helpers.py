"""Small DB assertion helpers for API tests."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.activity import TicketActivity
from app.models.agent import Agent
from app.models.note import TicketNote
from app.models.requester import Requester
from app.models.ticket import Ticket


def ticket_version(client, public_id: str) -> int:
    """The concurrency version the API exposes for a ticket (1 if absent)."""
    response = client.get(f"/api/v1/tickets/{public_id}")
    if response.status_code != 200:
        return 1
    return int(response.json()["version"])


def ticket_row(session_factory: sessionmaker[Session], public_id: str) -> dict[str, Any]:
    with session_factory() as session:
        ticket = session.scalar(
            select(Ticket).where(Ticket.public_id == public_id)
        )
        assert ticket is not None, public_id
        return {
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "category": ticket.category.value,
            "assigned_team": (
                ticket.assigned_team.value if ticket.assigned_team else None
            ),
            "assigned_agent_id": ticket.assigned_agent_id,
            "due_at": ticket.due_at,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
        }


def activity_rows(
    session_factory: sessionmaker[Session], public_id: str
) -> list[dict[str, Any]]:
    with session_factory() as session:
        rows = session.scalars(
            select(TicketActivity)
            .join(Ticket, Ticket.id == TicketActivity.ticket_id)
            .where(Ticket.public_id == public_id)
            .order_by(
                TicketActivity.created_at.asc(), TicketActivity.public_id.asc()
            )
        ).all()
        return [
            {
                "id": row.public_id,
                "action": row.action.value,
                "detail": row.detail,
                "actor_id": row.actor_id,
                "actor_name": row.actor_name,
                "is_internal_note": row.is_internal_note,
                "reply_id": (
                    row.reply.public_id if row.reply else None
                ),
                "reply_version": row.reply_version,
                "note_id": str(row.note_id) if row.note_id else None,
                "created_at": row.created_at,
            }
            for row in rows
        ]


def note_rows(
    session_factory: sessionmaker[Session], public_id: str
) -> list[dict[str, Any]]:
    with session_factory() as session:
        rows = session.scalars(
            select(TicketNote)
            .join(Ticket, Ticket.id == TicketNote.ticket_id)
            .where(Ticket.public_id == public_id)
            .order_by(TicketNote.created_at.asc(), TicketNote.id.asc())
        ).all()
        return [
            {
                "id": str(row.id),
                "content": row.content,
                "author_id": row.author_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]


def count_rows(session_factory: sessionmaker[Session], model) -> int:
    from sqlalchemy import func

    with session_factory() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def agent_name(session_factory: sessionmaker[Session], agent_id: str) -> str:
    with session_factory() as session:
        agent = session.get(Agent, agent_id)
        assert agent is not None, agent_id
        return agent.name


def requester_count(session_factory: sessionmaker[Session]) -> int:
    return count_rows(session_factory, Requester)
