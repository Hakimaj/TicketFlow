"""Agent lookup and SQL-derived ticket dashboard metrics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.seed import AGENT_SEEDS, TICKET_SEEDS

ACTIVE = {
    TicketStatus.NEW,
    TicketStatus.OPEN,
    TicketStatus.PENDING,
}


def _expected_active() -> int:
    return sum(1 for seed in TICKET_SEEDS if seed["status"] in ACTIVE)


def _expected_unassigned_active() -> int:
    return sum(
        1
        for seed in TICKET_SEEDS
        if seed["status"] in ACTIVE and seed["assigned_agent_id"] is None
    )


def _expected_urgent_high_active() -> int:
    return sum(
        1
        for seed in TICKET_SEEDS
        if seed["status"] in ACTIVE
        and seed["priority"] in (TicketPriority.URGENT, TicketPriority.HIGH)
    )


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


def test_agent_roster(client: TestClient, seeded: None) -> None:
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == len(AGENT_SEEDS)
    assert [agent["id"] for agent in items] == sorted(
        agent["id"] for agent in items
    )
    assert set(items[0]) == {"id", "name", "role", "team", "is_demo_user"}
    # No work email or account/credential details in the roster.
    assert all("email" not in agent for agent in items)

    demo = next(agent for agent in items if agent["id"] == "AG-01")
    assert demo == {
        "id": "AG-01",
        "name": "Abebe Kebede",
        "role": "supervisor",
        "team": "customer_support",
        "is_demo_user": True,
    }


def test_agent_filters(client: TestClient, seeded: None) -> None:
    billing = client.get("/api/v1/agents", params={"team": "billing_team"}).json()
    assert [agent["id"] for agent in billing["items"]] == ["AG-02"]

    supervisors = client.get(
        "/api/v1/agents", params={"role": "supervisor"}
    ).json()
    assert [agent["id"] for agent in supervisors["items"]] == ["AG-01"]

    customer_agents = client.get(
        "/api/v1/agents",
        params={"team": "customer_support", "role": "agent"},
    ).json()
    assert [agent["id"] for agent in customer_agents["items"]] == ["AG-06", "AG-07"]


def test_invalid_agent_filters_rejected(client: TestClient, seeded: None) -> None:
    for params in ({"team": "unknown_team"}, {"role": "owner"}):
        response = client.get("/api/v1/agents", params=params)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_dashboard_summary_matches_seed(
    client: TestClient, seeded: None
) -> None:
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    summary = response.json()

    assert summary["total_tickets"] == len(TICKET_SEEDS)
    assert summary["active_tickets"] == _expected_active()
    assert summary["unassigned_tickets"] == _expected_unassigned_active()
    assert summary["urgent_high_tickets"] == _expected_urgent_high_active()
    assert summary["needs_review_tickets"] == sum(
        1 for seed in TICKET_SEEDS if seed["status"] is TicketStatus.NEEDS_REVIEW
    )
    assert summary["generated_at"].endswith("Z")
    assert "pending_reply_approvals" not in summary
    assert "pending_approvals" not in summary


def test_dashboard_breakdowns_are_complete_and_accurate(
    client: TestClient, seeded: None
) -> None:
    summary = client.get("/api/v1/dashboard/summary").json()

    status_counts = {row["status"]: row["count"] for row in summary["status_counts"]}
    category_counts = {
        row["category"]: row["count"] for row in summary["category_counts"]
    }
    priority_counts = {
        row["priority"]: row["count"] for row in summary["priority_counts"]
    }

    assert status_counts == {
        status.value: sum(1 for seed in TICKET_SEEDS if seed["status"] is status)
        for status in TicketStatus
    }
    assert category_counts == {
        category.value: sum(
            1 for seed in TICKET_SEEDS if seed["category"] is category
        )
        for category in TicketCategory
    }
    assert priority_counts == {
        priority.value: sum(
            1 for seed in TICKET_SEEDS if seed["priority"] is priority
        )
        for priority in TicketPriority
    }

    assert sum(status_counts.values()) == len(TICKET_SEEDS)
    assert sum(category_counts.values()) == len(TICKET_SEEDS)
    assert sum(priority_counts.values()) == len(TICKET_SEEDS)
    assert [row["status"] for row in summary["status_counts"]] == [
        status.value for status in TicketStatus
    ]


def test_dashboard_reflects_persisted_mutations(
    client: TestClient, seeded: None
) -> None:
    before = client.get("/api/v1/dashboard/summary").json()

    client.patch("/api/v1/tickets/TF-1051/status", json={"status": "resolved"})
    client.patch("/api/v1/tickets/TF-1043/assignment", json={"agent_id": "AG-03"})
    after = client.get("/api/v1/dashboard/summary").json()

    assert after["total_tickets"] == before["total_tickets"]
    assert after["active_tickets"] == before["active_tickets"] - 1
    assert after["urgent_high_tickets"] == before["urgent_high_tickets"] - 1
    assert after["unassigned_tickets"] == before["unassigned_tickets"] - 1

    before_status = {
        row["status"]: row["count"] for row in before["status_counts"]
    }
    after_status = {row["status"]: row["count"] for row in after["status_counts"]}
    assert after_status["open"] == before_status["open"] - 1
    assert after_status["resolved"] == before_status["resolved"] + 1

    events = client.get("/api/v1/tickets/TF-1051/activities").json()
    assert events[-1]["action"] == "resolved"
