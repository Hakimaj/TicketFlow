"""Persisted ticket-specific and global activity history."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.seed import ACTIVITY_SEEDS
from tests.conftest import FIXED_ANCHOR
from tests.helpers import activity_rows


def _iso(hours_before_anchor: float) -> str:
    value = FIXED_ANCHOR - timedelta(hours=hours_before_anchor)
    return value.isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Ticket-specific history
# ---------------------------------------------------------------------------


def test_ticket_activities_are_ordered_oldest_first(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    response = auth_client.get("/api/v1/tickets/TF-1051/activities")
    assert response.status_code == 200
    events = response.json()
    assert [event["id"] for event in events] == [
        row["id"] for row in activity_rows(session_factory, "TF-1051")
    ]
    assert len(events) == 3
    assert events[0]["action"] == "created"
    assert events[-1]["action"] == "assigned"
    for event in events:
        assert event["ticket_id"] == "TF-1051"
        assert event["created_at"].endswith("Z")


def test_ticket_activities_scoped_and_404(auth_client: TestClient, seeded: None) -> None:
    events = auth_client.get("/api/v1/tickets/TF-1043/activities").json()
    assert events == []
    missing = auth_client.get("/api/v1/tickets/TF-9999/activities")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ticket_not_found"


def test_new_mutation_appears_in_ticket_history(
    auth_client: TestClient, seeded: None
) -> None:
    from tests.helpers import ticket_version

    auth_client.patch(
        "/api/v1/tickets/TF-1051/status",
        json={
            "status": "pending",
            "expected_version": ticket_version(auth_client, "TF-1051"),
        },
    )
    events = auth_client.get("/api/v1/tickets/TF-1051/activities").json()
    assert events[-1]["action"] == "status_changed"
    assert events[-1]["summary"] == "Status changed from Open to Pending."


# ---------------------------------------------------------------------------
# Global activity log
# ---------------------------------------------------------------------------


def test_global_activity_defaults(auth_client: TestClient, seeded: None) -> None:
    response = auth_client.get("/api/v1/activities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": len(ACTIVITY_SEEDS),
        "page_count": 1,
    }
    items = payload["items"]
    assert len(items) == len(ACTIVITY_SEEDS)
    timestamps = [item["created_at"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True)
    assert items[0]["id"] == "ACT-040"  # 0.4h ago


def test_global_filter_by_ticket(auth_client: TestClient, seeded: None) -> None:
    payload = auth_client.get(
        "/api/v1/activities", params={"ticket_id": "tf-1051"}
    ).json()
    assert payload["pagination"]["total"] == 3
    assert {item["ticket_id"] for item in payload["items"]} == {"TF-1051"}

    unknown = auth_client.get(
        "/api/v1/activities", params={"ticket_id": "TF-9999"}
    ).json()
    assert unknown["items"] == []
    assert unknown["pagination"]["total"] == 0


def test_global_filter_by_action_and_actor(
    auth_client: TestClient, seeded: None
) -> None:
    resolved = auth_client.get(
        "/api/v1/activities", params={"action": "resolved"}
    ).json()
    expected_resolved = sum(
        1 for seed in ACTIVITY_SEEDS if seed["action"].value == "resolved"
    )
    assert resolved["pagination"]["total"] == expected_resolved
    assert {item["action"] for item in resolved["items"]} == {"resolved"}

    mixed = auth_client.get(
        "/api/v1/activities",
        params=[("action", "resolved"), ("action", "assigned")],
    ).json()
    expected_mixed = sum(
        1
        for seed in ACTIVITY_SEEDS
        if seed["action"].value in {"resolved", "assigned"}
    )
    assert mixed["pagination"]["total"] == expected_mixed

    hana = auth_client.get(
        "/api/v1/activities", params={"actor_id": "ag-02"}
    ).json()
    expected_hana = sum(
        1 for seed in ACTIVITY_SEEDS if seed["actor_name"] == "Hana Tesfaye"
    )
    assert hana["pagination"]["total"] == expected_hana
    assert {item["actor_id"] for item in hana["items"]} == {"AG-02"}

    unknown_actor = auth_client.get(
        "/api/v1/activities", params={"actor_id": "AG-999"}
    ).json()
    assert unknown_actor["pagination"]["total"] == 0


def test_global_search_matches_safe_fields(
    auth_client: TestClient, seeded: None
) -> None:
    by_ticket = auth_client.get(
        "/api/v1/activities", params={"search": "TF-1051"}
    ).json()
    assert by_ticket["pagination"]["total"] == 3

    by_actor = auth_client.get(
        "/api/v1/activities", params={"search": "Hana"}
    ).json()
    assert by_actor["pagination"]["total"] == 4

    by_summary = auth_client.get(
        "/api/v1/activities", params={"search": "Cold-chain"}
    ).json()
    assert by_summary["pagination"]["total"] == 1
    assert by_summary["items"][0]["action"] == "escalated"

    # Enum value and human label both match.
    by_action_value = auth_client.get(
        "/api/v1/activities", params={"search": "status_changed"}
    ).json()
    assert by_action_value["pagination"]["total"] == 1

    # `%` is matched literally rather than as a LIKE wildcard: only the two
    # seeded summaries containing a percent sign match, not every row.
    expected_percent = sum(
        1 for seed in ACTIVITY_SEEDS if "%" in (seed["detail"] or "")
    )
    assert 0 < expected_percent < len(ACTIVITY_SEEDS)
    wildcard = auth_client.get("/api/v1/activities", params={"search": "%"}).json()
    assert wildcard["pagination"]["total"] == expected_percent


def test_global_date_window_is_start_inclusive_end_exclusive(
    auth_client: TestClient, seeded: None
) -> None:
    boundary = _iso(3)
    at_or_after = auth_client.get(
        "/api/v1/activities", params={"start": boundary, "page_size": 100}
    ).json()
    expected_from = sum(1 for seed in ACTIVITY_SEEDS if seed["hours_ago"] <= 3)
    assert at_or_after["pagination"]["total"] == expected_from

    before_boundary = auth_client.get(
        "/api/v1/activities", params={"end": boundary, "page_size": 100}
    ).json()
    expected_before = sum(1 for seed in ACTIVITY_SEEDS if seed["hours_ago"] > 3)
    assert before_boundary["pagination"]["total"] == expected_before

    window = auth_client.get(
        "/api/v1/activities",
        params={"start": _iso(3), "end": _iso(0.5), "page_size": 100},
    ).json()
    expected_window = sum(
        1 for seed in ACTIVITY_SEEDS if 0.5 < seed["hours_ago"] <= 3
    )
    assert window["pagination"]["total"] == expected_window


def test_global_sort_and_stable_tiebreak(auth_client: TestClient, seeded: None) -> None:
    newest = auth_client.get(
        "/api/v1/activities", params={"sort_dir": "desc", "page_size": 100}
    ).json()["items"]
    oldest = auth_client.get(
        "/api/v1/activities", params={"sort_dir": "asc", "page_size": 100}
    ).json()["items"]
    assert newest[0]["id"] == "ACT-040"
    assert oldest[0]["id"] == "ACT-028"

    # ACT-037 and ACT-044 share a timestamp; public ID ascending wins in both
    # directions, matching the deterministic ordering contract.
    for items in (newest, oldest):
        ids = [item["id"] for item in items]
        assert ids.index("ACT-037") < ids.index("ACT-044")


def test_global_pagination_is_isolated(auth_client: TestClient, seeded: None) -> None:
    first = auth_client.get(
        "/api/v1/activities", params={"page": 1, "page_size": 5}
    ).json()
    second = auth_client.get(
        "/api/v1/activities", params={"page": 2, "page_size": 5}
    ).json()
    all_ids = [item["id"] for item in first["items"] + second["items"]]
    assert len(all_ids) == 10
    assert len(set(all_ids)) == 10
    assert first["pagination"]["page_count"] == 4


def test_activity_query_validation(auth_client: TestClient, seeded: None) -> None:
    for params in (
        {"page": 0},
        {"page_size": 101},
        {"action": "bogus"},
        {"sort_dir": "sideways"},
    ):
        response = auth_client.get("/api/v1/activities", params=params)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    reversed_range = auth_client.get(
        "/api/v1/activities", params={"start": _iso(1), "end": _iso(2)}
    )
    assert reversed_range.status_code == 422
    assert reversed_range.json()["error"]["code"] == "invalid_query"


def test_activity_summaries_are_privacy_safe(
    auth_client: TestClient, seeded: None
) -> None:
    items = auth_client.get(
        "/api/v1/activities", params={"page_size": 100}
    ).json()["items"]
    assert items
    for item in items:
        assert "@" not in (item["summary"] or "")
        assert "myetmail.example" not in (item["summary"] or "")


def test_note_event_is_safe_in_global_log(
    auth_client: TestClient, seeded: None
) -> None:
    marker = "internal-note-body-2d1f"
    note = auth_client.post(
        "/api/v1/tickets/TF-1051/notes", json={"content": marker}
    ).json()
    payload = auth_client.get(
        "/api/v1/activities", params={"action": "note_added"}
    ).json()
    assert payload["pagination"]["total"] == 1
    event = payload["items"][0]
    assert event["note_id"] == note["id"]
    assert event["summary"] == "Internal note added."
    assert marker not in event["summary"]


def test_failed_mutation_leaves_no_global_activity(
    monkeypatch, session_factory, seeded: None, accounts: None
) -> None:
    from app.models.enums import TicketStatus
    from app.services import tickets as ticket_service
    from tests.conftest import REVIEWER_AGENT, principal_for

    def boom(*args, **kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(ticket_service.activity_repo, "add_activity", boom)

    with session_factory() as session:
        with pytest.raises(RuntimeError):
            ticket_service.update_status(
                session,
                "TF-1051",
                TicketStatus.PENDING,
                expected_version=1,
                principal=principal_for(session_factory, REVIEWER_AGENT),
            )

    with session_factory() as session:
        from sqlalchemy import func, select

        from app.models.activity import TicketActivity

        total = int(
            session.scalar(select(func.count()).select_from(TicketActivity)) or 0
        )
    assert total == len(ACTIVITY_SEEDS)
    assert activity_rows(session_factory, "TF-1051")[-1]["action"] == "assigned"
