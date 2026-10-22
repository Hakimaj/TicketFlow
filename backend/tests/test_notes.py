"""Persistent internal notes (not customer replies)."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models.reply import CustomerReply
from app.models.ticket import Ticket
from tests.conftest import FIXED_ANCHOR
from tests.helpers import activity_rows, note_rows, ticket_row


def _create(client: TestClient, ticket: str, content: str, **extra):
    return client.post(
        f"/api/v1/tickets/{ticket}/notes", json={"content": content, **extra}
    )


def test_create_note_persists_record_and_safe_audit(
    client: TestClient, session_factory, seeded: None
) -> None:
    before = ticket_row(session_factory, "TF-1051")
    response = _create(client, "TF-1051", "  Customer confirmed the reversal window.  ")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ticket_id"] == "TF-1051"
    assert body["content"] == "Customer confirmed the reversal window."
    assert body["author"] == {"id": "AG-01", "name": "Abebe Kebede"}
    assert body["id"]
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")

    stored = note_rows(session_factory, "TF-1051")
    assert len(stored) == 1
    assert stored[0]["id"] == body["id"]
    assert stored[0]["content"] == body["content"]
    assert ticket_row(session_factory, "TF-1051")["updated_at"] > before["updated_at"]

    activities = activity_rows(session_factory, "TF-1051")
    assert len(activities) == 4
    event = activities[-1]
    assert event["action"] == "note_added"
    assert event["detail"] == "Internal note added."
    assert event["is_internal_note"] is True
    assert event["note_id"] == body["id"]
    assert event["actor_id"] == "AG-01"


def test_note_author_override_and_invalid_actor(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _create(
        client, "TF-1051", "Handoff to billing.", actor_id="ag-02"
    )
    assert response.status_code == 201
    assert response.json()["author"] == {"id": "AG-02", "name": "Hana Tesfaye"}
    assert activity_rows(session_factory, "TF-1051")[-1]["actor_id"] == "AG-02"

    invalid = _create(client, "TF-1051", "Nope.", actor_id="AG-999")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_actor"
    assert len(note_rows(session_factory, "TF-1051")) == 1


def test_blank_whitespace_and_oversized_notes_rejected(
    client: TestClient, session_factory, seeded: None
) -> None:
    for content in ("", "   \n\t ", "x" * 4001):
        response = _create(client, "TF-1051", content)
        assert response.status_code == 422, content[:20]
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert error["details"][0]["field"] == "content"

    assert note_rows(session_factory, "TF-1051") == []
    assert len(activity_rows(session_factory, "TF-1051")) == 3


def test_maximum_length_note_is_accepted(
    client: TestClient, seeded: None
) -> None:
    response = _create(client, "TF-1051", "x" * 4000)
    assert response.status_code == 201
    assert len(response.json()["content"]) == 4000


def test_notes_are_scoped_to_their_ticket(
    client: TestClient, seeded: None
) -> None:
    _create(client, "TF-1051", "Only for 1051.")

    own = client.get("/api/v1/tickets/TF-1051/notes")
    other = client.get("/api/v1/tickets/TF-1048/notes")

    assert own.status_code == 200
    assert [item["content"] for item in own.json()["items"]] == ["Only for 1051."]
    assert own.json()["pagination"]["total"] == 1
    assert other.status_code == 200
    assert other.json()["items"] == []
    assert other.json()["pagination"]["total"] == 0


def test_notes_are_chronological_and_paginated(
    client: TestClient, session_factory, seeded: None
) -> None:
    from app.models.note import TicketNote

    with session_factory() as session:
        ticket = session.scalar(select(Ticket).where(Ticket.public_id == "TF-1051"))
        for index, hours in enumerate((3, 1, 2)):
            session.add(
                TicketNote(
                    ticket_id=ticket.id,
                    author_id="AG-01",
                    content=f"Note {index}",
                    created_at=FIXED_ANCHOR - timedelta(hours=hours),
                    updated_at=FIXED_ANCHOR - timedelta(hours=hours),
                )
            )
        session.commit()

    first = client.get(
        "/api/v1/tickets/TF-1051/notes", params={"page": 1, "page_size": 2}
    )
    second = client.get(
        "/api/v1/tickets/TF-1051/notes", params={"page": 2, "page_size": 2}
    )

    assert first.status_code == second.status_code == 200
    assert [item["content"] for item in first.json()["items"]] == [
        "Note 0",
        "Note 2",
    ]
    assert [item["content"] for item in second.json()["items"]] == ["Note 1"]
    assert first.json()["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total": 3,
        "page_count": 2,
    }


def test_notes_are_not_customer_replies(
    client: TestClient, session_factory, seeded: None
) -> None:
    with session_factory() as session:
        replies_before = int(
            session.scalar(select(func.count()).select_from(CustomerReply)) or 0
        )

    response = _create(client, "TF-1051", "Internal only — never send this.")
    assert response.status_code == 201

    with session_factory() as session:
        replies_after = int(
            session.scalar(select(func.count()).select_from(CustomerReply)) or 0
        )
        bodies = session.scalars(select(CustomerReply.body)).all()
        ticket = session.scalar(select(Ticket).where(Ticket.public_id == "TF-1051"))

    assert replies_after == replies_before
    assert "Internal only — never send this." not in bodies
    assert ticket is not None

    listing = client.get("/api/v1/tickets/TF-1051/notes").json()
    assert set(listing["items"][0]) == {
        "id",
        "ticket_id",
        "content",
        "author",
        "created_at",
        "updated_at",
    }


def test_note_body_never_appears_in_activity_metadata(
    client: TestClient, session_factory, seeded: None
) -> None:
    marker = "unique-note-body-7f3c9"
    response = _create(client, "TF-1051", marker)
    assert response.status_code == 201
    note_id = response.json()["id"]

    ticket_events = client.get("/api/v1/tickets/TF-1051/activities").json()
    note_event = next(event for event in ticket_events if event["note_id"] == note_id)
    assert note_event["action"] == "note_added"
    assert note_event["summary"] == "Internal note added."
    assert marker not in note_event["summary"]

    global_events = client.get(
        "/api/v1/activities", params={"search": marker}
    ).json()
    assert global_events["pagination"]["total"] == 0

    stored = activity_rows(session_factory, "TF-1051")[-1]
    assert stored["detail"] == "Internal note added."
    assert marker not in (stored["detail"] or "")


def test_unknown_ticket_notes_return_404(client: TestClient, seeded: None) -> None:
    assert _create(client, "TF-9999", "Nope.").status_code == 404
    assert client.get("/api/v1/tickets/TF-9999/notes").status_code == 404


def test_invalid_note_pagination_rejected(client: TestClient, seeded: None) -> None:
    for params in ({"page": 0}, {"page_size": 0}, {"page_size": 101}):
        response = client.get("/api/v1/tickets/TF-1051/notes", params=params)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
