"""Staff ticket intake: ``POST /api/v1/tickets``.

Every assertion here goes through the real endpoint and a real PostgreSQL
database; nothing is mocked except the deliberate audit-store failure.
"""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ApiError
from app.models.ticket import Ticket
from tests.conftest import (
    ADMIN_AGENT,
    AUTHOR_AGENT,
    REVIEWER_AGENT,
    principal_for,
    use_account,
)
from tests.helpers import activity_rows, count_rows, requester_count, ticket_row

VALID_PAYLOAD = {
    "subject": "Refund for order ET-99120 has not arrived",
    "description": (
        "The return was collected two weeks ago and no refund has appeared on "
        "the card yet."
    ),
    "category": "billing",
    "priority": "high",
    "channel": "email",
    "requester_name": "Marta Alemu",
    "requester_email": "Marta.Alemu@Example.com",
}


def _create(client: TestClient, **overrides):
    return client.post("/api/v1/tickets", json={**VALID_PAYLOAD, **overrides})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_creates_ticket_with_audit_event_and_defaults(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    before_tickets = count_rows(session_factory, Ticket)

    response = _create(auth_client)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"].startswith("TF-")
    assert body["subject"] == VALID_PAYLOAD["subject"]
    assert body["description"] == VALID_PAYLOAD["description"]
    assert body["status"] == "new"
    assert body["category"] == "billing"
    assert body["priority"] == "high"
    assert body["channel"] == "email"
    # Category-derived routing, no invented assignee.
    assert body["assigned_team"] == "billing_team"
    assert body["assigned_agent_id"] is None
    # urgent/high use the same 8-hour SLA target as triage.
    assert body["due_at"] is not None
    assert body["version"] == 1
    # Requester identity is stored normalized and returned on the detail view.
    assert body["requester"]["name"] == "Marta Alemu"
    assert body["requester"]["email"] == "marta.alemu@example.com"

    assert count_rows(session_factory, Ticket) == before_tickets + 1
    row = ticket_row(session_factory, body["id"])
    assert row["status"] == "new"
    assert row["assigned_team"] == "billing_team"

    events = activity_rows(session_factory, body["id"])
    assert len(events) == 1
    assert events[0]["action"] == "created"
    assert events[0]["detail"] == "Ticket created via email intake."
    # Attribution comes from the verified account (the client's default review
    # token), never from the payload.
    assert events[0]["actor_id"] == REVIEWER_AGENT


def test_low_priority_has_no_sla_target(
    auth_client: TestClient, seeded: None
) -> None:
    response = _create(auth_client, priority="low", channel="web_form")
    assert response.status_code == 201, response.text
    assert response.json()["due_at"] is None
    assert response.json()["channel"] == "web_form"


def test_priority_and_channel_default_to_normal_and_web_form(
    auth_client: TestClient, seeded: None
) -> None:
    payload = {
        key: value
        for key, value in VALID_PAYLOAD.items()
        if key not in {"priority", "channel"}
    }
    response = auth_client.post("/api/v1/tickets", json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["priority"] == "normal"
    assert response.json()["channel"] == "web_form"
    assert response.json()["due_at"] is None


def test_existing_requester_email_is_reused(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    before = requester_count(session_factory)

    first = _create(auth_client)
    # Same customer, different casing: must not duplicate the requester.
    second = _create(auth_client, requester_email="MARTA.ALEMU@example.com")

    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["requester"]["id"] == second.json()["requester"]["id"]
    assert first.json()["id"] != second.json()["id"]
    assert requester_count(session_factory) == before + 1


def test_created_ticket_is_visible_in_the_queue_and_detail(
    auth_client: TestClient, seeded: None
) -> None:
    created = _create(auth_client, subject="Unique intake subject 55123").json()

    queue = auth_client.get(
        "/api/v1/tickets", params={"search": "Unique intake subject 55123"}
    )
    assert queue.status_code == 200
    assert [item["id"] for item in queue.json()["items"]] == [created["id"]]

    detail = auth_client.get(f"/api/v1/tickets/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["description"] == created["description"]
    assert detail.json()["version"] == 1


def test_created_ticket_can_be_triaged_with_its_version(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    created = _create(auth_client).json()

    response = auth_client.patch(
        f"/api/v1/tickets/{created['id']}/status",
        json={"status": "pending", "expected_version": created["version"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "pending"
    assert response.json()["version"] == created["version"] + 1


def test_ticket_identifiers_are_unique_and_sequential(
    auth_client: TestClient, seeded: None
) -> None:
    first = _create(auth_client).json()["id"]
    second = _create(auth_client).json()["id"]
    assert first != second
    assert int(second.split("-")[1]) == int(first.split("-")[1]) + 1


def test_concurrent_intake_allocates_distinct_identifiers(
    session_factory, seeded: None, accounts: None
) -> None:
    """The advisory lock serialises TF-#### allocation under real threads."""
    from app.services import tickets as ticket_service
    from app.schemas.tickets import TicketCreate

    barrier = threading.Barrier(2, timeout=15)
    created: list[str] = []
    errors: list[BaseException] = []

    def attempt() -> None:
        try:
            with session_factory() as session:
                barrier.wait()
                detail = ticket_service.create_ticket(
                    session,
                    TicketCreate(**VALID_PAYLOAD),
                    principal=principal_for(session_factory, REVIEWER_AGENT),
                )
                created.append(detail.id)
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, errors
    assert len(created) == 2
    assert len(set(created)) == 2


# ---------------------------------------------------------------------------
# Validation and authorization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "payload"),
    [
        ("subject", {"subject": "   "}),
        ("subject", {"subject": "ab"}),
        ("description", {"description": "too short"}),
        ("description", {"description": "            "}),
        ("category", {"category": "refunds"}),
        ("priority", {"priority": "critical"}),
        ("channel", {"channel": "carrier_pigeon"}),
        ("requester_name", {"requester_name": ""}),
        ("requester_email", {"requester_email": "not-an-email"}),
        ("requester_email", {"requester_email": "@example.com"}),
    ],
)
def test_invalid_payloads_are_rejected_and_nothing_is_persisted(
    auth_client: TestClient,
    session_factory,
    seeded: None,
    field: str,
    payload: dict,
) -> None:
    before = count_rows(session_factory, Ticket)

    response = _create(auth_client, **payload)

    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert field in {detail["field"] for detail in error["details"]}
    assert count_rows(session_factory, Ticket) == before


def test_missing_required_fields_are_rejected(
    auth_client: TestClient, seeded: None
) -> None:
    response = auth_client.post("/api/v1/tickets", json={"subject": "Only a subject"})
    assert response.status_code == 422
    fields = {
        detail["field"] for detail in response.json()["error"]["details"]
    }
    assert {"description", "category", "requester_name", "requester_email"} <= fields


def test_unauthenticated_intake_is_rejected(client: TestClient, seeded: None) -> None:
    response = client.post("/api/v1/tickets", json=VALID_PAYLOAD)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_any_triage_role_can_create_tickets(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    for agent_id in (AUTHOR_AGENT, REVIEWER_AGENT, ADMIN_AGENT):
        use_account(auth_client, agent_id)
        response = _create(auth_client, subject=f"Intake by {agent_id}")
        assert response.status_code == 201, response.text
        events = activity_rows(session_factory, response.json()["id"])
        assert events[0]["actor_id"] == agent_id


# ---------------------------------------------------------------------------
# Attribution cannot be spoofed
# ---------------------------------------------------------------------------


def test_body_cannot_forge_actor_status_or_version(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    use_account(auth_client, AUTHOR_AGENT)

    response = auth_client.post(
        "/api/v1/tickets",
        json={
            **VALID_PAYLOAD,
            "actor_id": REVIEWER_AGENT,
            "actor_name": "Spoofed Reviewer",
            "status": "resolved",
            "version": 99,
            "assigned_agent_id": "AG-02",
            "reviewer_id": REVIEWER_AGENT,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "new"
    assert body["version"] == 1
    assert body["assigned_agent_id"] is None

    events = activity_rows(session_factory, body["id"])
    assert events[0]["actor_id"] == AUTHOR_AGENT


# ---------------------------------------------------------------------------
# Transactional integrity
# ---------------------------------------------------------------------------


def test_audit_failure_rolls_back_ticket_and_requester(
    monkeypatch, session_factory, seeded: None, accounts: None
) -> None:
    from app.schemas.tickets import TicketCreate
    from app.services import tickets as ticket_service

    def boom(*args, **kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(ticket_service.activity_repo, "add_activity", boom)
    before_tickets = count_rows(session_factory, Ticket)
    before_requesters = requester_count(session_factory)

    with session_factory() as session:
        with pytest.raises(RuntimeError):
            ticket_service.create_ticket(
                session,
                TicketCreate(**VALID_PAYLOAD),
                principal=principal_for(session_factory, REVIEWER_AGENT),
            )

    assert count_rows(session_factory, Ticket) == before_tickets
    assert requester_count(session_factory) == before_requesters


def test_conflicting_requester_insert_is_reported_as_conflict(
    monkeypatch, session_factory, seeded: None, accounts: None
) -> None:
    """A concurrent requester insert surfaces as 409, not a 500 or a partial row."""
    from sqlalchemy.exc import IntegrityError

    from app.schemas.tickets import TicketCreate
    from app.services import tickets as ticket_service

    class _FailingFlush:
        def __init__(self, session):
            self._session = session

        def __getattr__(self, name):
            return getattr(self._session, name)

        def scalar(self, *_args, **_kwargs):
            return None  # pretend the requester does not exist yet

        def flush(self, *_args, **_kwargs):
            raise IntegrityError("insert", {}, Exception("duplicate key"))

    before = count_rows(session_factory, Ticket)
    with session_factory() as session:
        with pytest.raises(ApiError) as exc:
            ticket_service.create_ticket(
                _FailingFlush(session),
                TicketCreate(**VALID_PAYLOAD),
                principal=principal_for(session_factory, REVIEWER_AGENT),
            )
    assert exc.value.status_code == 409
    assert exc.value.code == "ticket_conflict"
    assert count_rows(session_factory, Ticket) == before
