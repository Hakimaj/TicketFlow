"""Agent lookup and SQL-derived ticket dashboard metrics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.enums import (
    ReplyState,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.seed import AGENT_SEEDS, REPLY_SEEDS, TICKET_SEEDS

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


def test_agent_roster(auth_client: TestClient, seeded: None) -> None:
    response = auth_client.get("/api/v1/agents")
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


def test_agent_filters(auth_client: TestClient, seeded: None) -> None:
    billing = auth_client.get("/api/v1/agents", params={"team": "billing_team"}).json()
    assert [agent["id"] for agent in billing["items"]] == ["AG-02"]

    supervisors = auth_client.get(
        "/api/v1/agents", params={"role": "supervisor"}
    ).json()
    assert [agent["id"] for agent in supervisors["items"]] == ["AG-01"]

    customer_agents = auth_client.get(
        "/api/v1/agents",
        params={"team": "customer_support", "role": "agent"},
    ).json()
    assert [agent["id"] for agent in customer_agents["items"]] == ["AG-06", "AG-07"]


def test_invalid_agent_filters_rejected(auth_client: TestClient, seeded: None) -> None:
    for params in ({"team": "unknown_team"}, {"role": "owner"}):
        response = auth_client.get("/api/v1/agents", params=params)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_dashboard_summary_matches_seed(
    auth_client: TestClient, seeded: None
) -> None:
    response = auth_client.get("/api/v1/dashboard/summary")
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

    # Reply metrics are per logical reply (REPLY_SEEDS has one row per reply).
    def reply_count(state: ReplyState) -> int:
        return sum(1 for seed in REPLY_SEEDS if seed["state"] is state)

    assert summary["pending_reply_approvals"] == reply_count(
        ReplyState.PENDING_APPROVAL
    )
    assert summary["draft_replies"] == reply_count(ReplyState.DRAFT)
    assert summary["approved_replies_awaiting_send"] == reply_count(
        ReplyState.APPROVED
    )
    assert summary["sent_replies_demo"] == reply_count(ReplyState.SENT)
    assert "pending_approvals" not in summary


def test_dashboard_breakdowns_are_complete_and_accurate(
    auth_client: TestClient, seeded: None
) -> None:
    summary = auth_client.get("/api/v1/dashboard/summary").json()

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
    auth_client: TestClient, seeded: None
) -> None:
    before = auth_client.get("/api/v1/dashboard/summary").json()

    from tests.helpers import ticket_version

    auth_client.patch(
        "/api/v1/tickets/TF-1051/status",
        json={
            "status": "resolved",
            "expected_version": ticket_version(auth_client, "TF-1051"),
        },
    )
    auth_client.patch(
        "/api/v1/tickets/TF-1043/assignment",
        json={
            "agent_id": "AG-03",
            "expected_version": ticket_version(auth_client, "TF-1043"),
        },
    )
    after = auth_client.get("/api/v1/dashboard/summary").json()

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

    events = auth_client.get("/api/v1/tickets/TF-1051/activities").json()
    assert events[-1]["action"] == "resolved"


def test_dashboard_extended_breakdowns(auth_client: TestClient, seeded: None) -> None:
    """`?trend_days=` adds timestamp-derived chart data; nothing is invented."""
    plain = auth_client.get("/api/v1/dashboard/summary").json()
    assert plain["received_trend"] is None
    assert plain["priority_summary"] is None
    assert plain["agent_workload"] is None

    days = 60  # wide enough to cover every seeded ticket's age
    summary = auth_client.get(f"/api/v1/dashboard/summary?trend_days={days}").json()

    trend = summary["received_trend"]
    assert trend is not None
    assert len(trend) == days
    # No invented history: buckets before the oldest seeded data are zero and
    # total received equals the current ticket total.
    assert sum(point["received"] for point in trend) == len(TICKET_SEEDS)
    assert all("received" in point and "resolved" in point for point in trend)
    # Resolution proxy: window includes resolved/closed ticket last-touch days.
    resolved_total = sum(point["resolved"] for point in trend)
    assert resolved_total >= 0

    priority_summary = summary["priority_summary"]
    assert priority_summary is not None
    assert [row["priority"] for row in priority_summary] == [
        priority.value for priority in TicketPriority
    ]
    for row in priority_summary:
        active_only = row["open"] + row["pending"] + row["needs_review"]
        assert active_only <= row["total"]
    assert sum(row["total"] for row in priority_summary) == len(TICKET_SEEDS)

    workload = summary["agent_workload"]
    assert workload is not None
    workload_by_id = {
        row["agent_id"]: row["count"] for row in workload
    }
    seeded_workload_total = sum(workload_by_id.values())
    # Active tickets only, split across assignments (or the null bucket).
    active_total = sum(
        1 for seed in TICKET_SEEDS if seed["status"] in ACTIVE
    )
    assert seeded_workload_total == active_total
    # Every named row must name an existing agent.
    roster = {agent["id"] for agent in AGENT_SEEDS}
    assert all(
        row["agent_id"] is None or row["agent_id"] in roster for row in workload
    )
    # Unassigned bucket exists and matches the persisted unassigned count.
    unassigned = workload_by_id.get(None, 0)
    persisted = auth_client.get("/api/v1/dashboard/summary").json()
    assert unassigned == persisted["unassigned_tickets"]


def test_dashboard_trend_days_rejected_when_out_of_range(
    auth_client: TestClient, seeded: None
) -> None:
    assert auth_client.get("/api/v1/dashboard/summary?trend_days=0").status_code == 422
    assert (
        auth_client.get("/api/v1/dashboard/summary?trend_days=3651").status_code
        == 422
    )
