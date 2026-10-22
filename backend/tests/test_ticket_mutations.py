"""Persistent ticket status/priority/category/assignment mutations."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.models.enums import TicketStatus
from app.schemas.notes import NoteCreate
from app.services import notes as note_service
from tests.helpers import activity_rows, ticket_row


def _patch(client: TestClient, ticket: str, field: str, body: dict):
    return client.patch(f"/api/v1/tickets/{ticket}/{field}", json=body)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_status_update_persists_and_records_one_activity(
    client: TestClient, session_factory, seeded: None
) -> None:
    before = ticket_row(session_factory, "TF-1051")
    response = _patch(client, "TF-1051", "status", {"status": "pending"})

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "pending"
    after = ticket_row(session_factory, "TF-1051")
    assert after["status"] == "pending"
    assert after["updated_at"] > before["updated_at"]

    activities = activity_rows(session_factory, "TF-1051")
    assert len(activities) == 4
    latest = activities[-1]
    assert latest["action"] == "status_changed"
    assert latest["detail"] == "Status changed from Open to Pending."
    assert latest["actor_id"] == "AG-01"


def test_status_noop_writes_no_audit_and_keeps_updated_at(
    client: TestClient, session_factory, seeded: None
) -> None:
    before = ticket_row(session_factory, "TF-1051")
    response = _patch(client, "TF-1051", "status", {"status": "open"})

    assert response.status_code == 200
    assert response.json()["status"] == "open"
    after = ticket_row(session_factory, "TF-1051")
    assert after["updated_at"] == before["updated_at"]
    assert len(activity_rows(session_factory, "TF-1051")) == 3


def test_repeating_a_status_change_does_not_duplicate_audit(
    client: TestClient, session_factory, seeded: None
) -> None:
    assert _patch(client, "TF-1051", "status", {"status": "pending"}).status_code == 200
    assert _patch(client, "TF-1051", "status", {"status": "pending"}).status_code == 200
    actions = [row["action"] for row in activity_rows(session_factory, "TF-1051")]
    assert actions.count("status_changed") == 1


def test_resolved_status_clears_due_at(
    client: TestClient, session_factory, seeded: None
) -> None:
    assert ticket_row(session_factory, "TF-1051")["due_at"] is not None
    response = _patch(client, "TF-1051", "status", {"status": "resolved"})

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert response.json()["due_at"] is None
    assert ticket_row(session_factory, "TF-1051")["due_at"] is None
    assert activity_rows(session_factory, "TF-1051")[-1]["action"] == "resolved"


def test_needs_review_status_uses_review_flagged_action(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(client, "TF-1051", "status", {"status": "needs_review"})
    assert response.status_code == 200
    assert activity_rows(session_factory, "TF-1051")[-1]["action"] == "review_flagged"


def test_actor_override_is_recorded_but_documented_as_untrusted(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(
        client, "TF-1051", "status", {"status": "pending", "actor_id": "ag-02"}
    )
    assert response.status_code == 200
    latest = activity_rows(session_factory, "TF-1051")[-1]
    assert latest["actor_id"] == "AG-02"
    assert latest["actor_name"] == "Hana Tesfaye"


def test_unknown_actor_is_rejected_without_changes(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(
        client, "TF-1051", "status", {"status": "pending", "actor_id": "AG-999"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_actor"
    assert ticket_row(session_factory, "TF-1051")["status"] == "open"
    assert len(activity_rows(session_factory, "TF-1051")) == 3


def test_invalid_status_is_rejected(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(client, "TF-1051", "status", {"status": "archived"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "status"
    assert ticket_row(session_factory, "TF-1051")["status"] == "open"
    assert len(activity_rows(session_factory, "TF-1051")) == 3


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------


def test_priority_update_persists_and_sets_sla_target(
    client: TestClient, session_factory, seeded: None
) -> None:
    before = ticket_row(session_factory, "TF-1043")
    assert before["due_at"] is None
    response = _patch(client, "TF-1043", "priority", {"priority": "urgent"})

    assert response.status_code == 200
    assert response.json()["priority"] == "urgent"
    assert response.json()["due_at"] is not None
    after = ticket_row(session_factory, "TF-1043")
    assert after["priority"] == "urgent"
    assert after["due_at"] is not None
    assert after["updated_at"] > before["updated_at"]

    latest = activity_rows(session_factory, "TF-1043")[-1]
    assert latest["action"] == "priority_changed"
    assert latest["detail"] == "Priority changed from Low to Urgent."


def test_priority_noop_writes_no_audit(
    client: TestClient, session_factory, seeded: None
) -> None:
    before = ticket_row(session_factory, "TF-1043")
    response = _patch(client, "TF-1043", "priority", {"priority": "low"})
    assert response.status_code == 200
    assert ticket_row(session_factory, "TF-1043")["updated_at"] == before["updated_at"]
    assert activity_rows(session_factory, "TF-1043") == []


def test_lower_priority_clears_due_at(
    client: TestClient, session_factory, seeded: None
) -> None:
    assert ticket_row(session_factory, "TF-1051")["due_at"] is not None
    response = _patch(client, "TF-1051", "priority", {"priority": "low"})
    assert response.status_code == 200
    assert response.json()["due_at"] is None


def test_priority_change_on_terminal_ticket_keeps_due_at_untouched(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(client, "TF-1044", "priority", {"priority": "urgent"})
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert response.json()["due_at"] is None
    assert activity_rows(session_factory, "TF-1044")[-1]["action"] == "priority_changed"


def test_invalid_priority_is_rejected(client: TestClient, seeded: None) -> None:
    response = _patch(client, "TF-1051", "priority", {"priority": "critical"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# Category → team routing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ticket_id", "target", "expected_team", "expected_agent"),
    [
        ("TF-1051", "delivery", "logistics_team", "AG-02"),
        ("TF-1051", "technical", "technical_support", "AG-02"),
        ("TF-1051", "returns", "returns_team", "AG-02"),
        ("TF-1051", "general", "customer_support", "AG-02"),
        ("TF-1043", "billing", "billing_team", None),
    ],
)
def test_category_routing_rules(
    client: TestClient,
    session_factory,
    seeded: None,
    ticket_id: str,
    target: str,
    expected_team: str,
    expected_agent: str | None,
) -> None:
    response = _patch(client, ticket_id, "category", {"category": target})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["category"] == target
    assert body["assigned_team"] == expected_team
    # Category routing never silently reassigns the agent.
    assert body["assigned_agent_id"] == expected_agent
    row = ticket_row(session_factory, ticket_id)
    assert row["assigned_team"] == expected_team
    latest = activity_rows(session_factory, ticket_id)[-1]
    assert latest["action"] == "categorized"
    routed_to = f"routed to {expected_team.replace('_', ' ').title()}".lower()
    assert routed_to in latest["detail"].lower()


def test_category_noop_writes_no_audit(
    client: TestClient, session_factory, seeded: None
) -> None:
    before = ticket_row(session_factory, "TF-1051")
    response = _patch(client, "TF-1051", "category", {"category": "billing"})
    assert response.status_code == 200
    assert ticket_row(session_factory, "TF-1051")["updated_at"] == before["updated_at"]
    assert len(activity_rows(session_factory, "TF-1051")) == 3


def test_invalid_category_is_rejected(client: TestClient, seeded: None) -> None:
    response = _patch(client, "TF-1051", "category", {"category": "refunds"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


def test_assign_unassigned_ticket(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(client, "TF-1043", "assignment", {"agent_id": "AG-03"})

    assert response.status_code == 200
    body = response.json()
    assert body["assigned_agent_id"] == "AG-03"
    assert body["assigned_agent_name"] == "Dawit Mengistu"
    # Team remains category-derived (general → customer support).
    assert body["assigned_team"] == "customer_support"
    latest = activity_rows(session_factory, "TF-1043")[-1]
    assert latest["action"] == "assigned"
    assert latest["detail"] == "Assigned to Dawit Mengistu."


def test_reassign_ticket(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(client, "TF-1051", "assignment", {"agent_id": "AG-04"})

    assert response.status_code == 200
    body = response.json()
    assert body["assigned_agent_id"] == "AG-04"
    assert body["assigned_team"] == "billing_team"
    latest = activity_rows(session_factory, "TF-1051")[-1]
    assert latest["detail"] == "Reassigned from Hana Tesfaye to Selam Girma."


def test_explicit_null_unassigns(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(client, "TF-1051", "assignment", {"agent_id": None})

    assert response.status_code == 200
    body = response.json()
    assert body["assigned_agent_id"] is None
    assert body["assigned_agent_name"] is None
    assert body["assigned_team"] == "billing_team"
    latest = activity_rows(session_factory, "TF-1051")[-1]
    assert latest["action"] == "assigned"
    assert latest["detail"] == "Unassigned (previously assigned to Hana Tesfaye)."


def test_omitted_agent_field_is_not_unassignment(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(client, "TF-1051", "assignment", {})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "agent_id"
    assert ticket_row(session_factory, "TF-1051")["assigned_agent_id"] == "AG-02"
    assert len(activity_rows(session_factory, "TF-1051")) == 3


def test_empty_agent_id_is_not_treated_as_unassignment(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(client, "TF-1051", "assignment", {"agent_id": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert ticket_row(session_factory, "TF-1051")["assigned_agent_id"] == "AG-02"
    assert len(activity_rows(session_factory, "TF-1051")) == 3


def test_unknown_agent_reference_is_rejected(
    client: TestClient, session_factory, seeded: None
) -> None:
    response = _patch(client, "TF-1051", "assignment", {"agent_id": "AG-999"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_agent"
    assert ticket_row(session_factory, "TF-1051")["assigned_agent_id"] == "AG-02"
    assert len(activity_rows(session_factory, "TF-1051")) == 3


def test_same_agent_is_noop(
    client: TestClient, session_factory, seeded: None
) -> None:
    before = ticket_row(session_factory, "TF-1051")
    response = _patch(client, "TF-1051", "assignment", {"agent_id": "AG-02"})
    assert response.status_code == 200
    assert ticket_row(session_factory, "TF-1051")["updated_at"] == before["updated_at"]
    assert len(activity_rows(session_factory, "TF-1051")) == 3


def test_admin_agent_is_assignable(client: TestClient, seeded: None) -> None:
    response = _patch(client, "TF-1043", "assignment", {"agent_id": "AG-08"})
    assert response.status_code == 200
    assert response.json()["assigned_agent_id"] == "AG-08"


# ---------------------------------------------------------------------------
# 404s and transactional rollback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "body"),
    [
        ("status", {"status": "open"}),
        ("priority", {"priority": "low"}),
        ("category", {"category": "billing"}),
        ("assignment", {"agent_id": "AG-02"}),
    ],
)
def test_unknown_ticket_returns_404(
    client: TestClient, seeded: None, field: str, body: dict
) -> None:
    response = _patch(client, "TF-9999", field, body)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ticket_not_found"


def test_activity_failure_rolls_back_ticket_change(
    monkeypatch, session_factory, seeded: None
) -> None:
    from app.services import tickets as ticket_service

    def boom(*args, **kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(ticket_service.activity_repo, "add_activity", boom)

    with session_factory() as session:
        with pytest.raises(RuntimeError):
            ticket_service.update_status(
                session, "TF-1051", TicketStatus.PENDING
            )

    assert ticket_row(session_factory, "TF-1051")["status"] == "open"
    assert len(activity_rows(session_factory, "TF-1051")) == 3


def test_failed_note_creation_rolls_back_note_and_activity(
    monkeypatch, session_factory, seeded: None
) -> None:
    from app.services import notes as notes_service

    def boom(*args, **kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(notes_service.activity_repo, "add_activity", boom)
    before = ticket_row(session_factory, "TF-1051")

    with session_factory() as session:
        with pytest.raises(RuntimeError):
            note_service.create_note(
                session,
                "TF-1051",
                NoteCreate(content="Should never persist."),
            )

    from tests.helpers import note_rows

    assert note_rows(session_factory, "TF-1051") == []
    assert len(activity_rows(session_factory, "TF-1051")) == 3
    assert ticket_row(session_factory, "TF-1051")["updated_at"] == before["updated_at"]
