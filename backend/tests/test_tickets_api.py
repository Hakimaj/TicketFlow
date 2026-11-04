"""Ticket list and detail behaviour against the seeded PostgreSQL database."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.models.enums import TicketPriority, TicketStatus
from app.seed import TICKET_SEEDS

ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def _expected_count(**criteria: object) -> int:
    """Count matching fixtures independently of the SQL under test."""
    total = 0
    for seed in TICKET_SEEDS:
        if all(seed.get(key) == value for key, value in criteria.items()):
            total += 1
    return total


def _all_items(auth_client: TestClient, **params: object) -> list[dict]:
    response = auth_client.get(
        "/api/v1/tickets", params={"page_size": 100, **params}
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_list_returns_page_and_pagination_metadata(
    auth_client: TestClient, seeded: None
) -> None:
    response = auth_client.get("/api/v1/tickets")
    assert response.status_code == 200
    payload = response.json()

    assert len(payload["items"]) == 20
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": len(TICKET_SEEDS),
        "page_count": 2,
    }

    item = payload["items"][0]
    assert item["id"] == "TF-1051"  # newest first by default
    assert item["status"] == "open"
    assert item["priority"] == "urgent"
    assert item["category"] == "billing"
    assert item["channel"] == "web_form"
    assert item["assigned_team"] == "billing_team"
    assert item["assigned_agent_id"] == "AG-02"
    assert item["assigned_agent_name"] == "Hana Tesfaye"
    assert ISO_UTC.match(item["created_at"])
    assert ISO_UTC.match(item["updated_at"])


def test_list_rows_are_privacy_limited(auth_client: TestClient, seeded: None) -> None:
    item = _all_items(auth_client)[0]
    # Email, original message and internal triage notes belong to the detail
    # endpoint, not to every queue row.
    assert "requester_email" not in item
    assert "description" not in item
    assert "review_note" not in item
    assert "@" not in str(item)


def test_pagination_walks_pages_without_duplicates(
    auth_client: TestClient, seeded: None
) -> None:
    first = auth_client.get("/api/v1/tickets", params={"page": 1, "page_size": 10})
    second = auth_client.get("/api/v1/tickets", params={"page": 2, "page_size": 10})
    third = auth_client.get("/api/v1/tickets", params={"page": 3, "page_size": 10})

    assert first.status_code == second.status_code == third.status_code == 200
    ids = [item["id"] for page in (first, second, third) for item in page.json()["items"]]
    assert len(ids) == len(TICKET_SEEDS)
    assert len(set(ids)) == len(TICKET_SEEDS)

    assert first.json()["pagination"]["page_count"] == 3
    assert len(first.json()["items"]) == 10
    assert len(third.json()["items"]) == 4

    beyond = auth_client.get("/api/v1/tickets", params={"page": 99})
    assert beyond.status_code == 200
    assert beyond.json()["items"] == []
    assert beyond.json()["pagination"]["total"] == len(TICKET_SEEDS)


def test_search_matches_ticket_id_subject_and_requester(
    auth_client: TestClient, seeded: None
) -> None:
    by_id = auth_client.get("/api/v1/tickets", params={"search": "TF-1051"}).json()
    assert [item["id"] for item in by_id["items"]] == ["TF-1051"]

    by_subject = auth_client.get(
        "/api/v1/tickets", params={"search": "checkout freezes"}
    ).json()
    assert [item["id"] for item in by_subject["items"]] == ["TF-1048"]

    by_requester = auth_client.get("/api/v1/tickets", params={"search": "marta"}).json()
    assert [item["id"] for item in by_requester["items"]] == ["TF-1051"]

    case_insensitive = auth_client.get(
        "/api/v1/tickets", params={"search": "TELEBIRR"}
    ).json()
    assert case_insensitive["pagination"]["total"] >= 3


def test_search_like_wildcards_are_escaped(auth_client: TestClient, seeded: None) -> None:
    # A literal '%' appears in no subject/requester; an unescaped LIKE would
    # match every row.
    response = auth_client.get("/api/v1/tickets", params={"search": "%"})
    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 0

    response = auth_client.get("/api/v1/tickets", params={"search": "_"})
    assert response.json()["pagination"]["total"] == 0


def test_status_filter_including_multi_value(
    auth_client: TestClient, seeded: None
) -> None:
    open_items = _all_items(auth_client, status="open")
    assert len(open_items) == _expected_count(status=TicketStatus.OPEN)
    assert {item["status"] for item in open_items} == {"open"}

    multi = _all_items(auth_client, status=["open", "pending"])
    expected = _expected_count(status=TicketStatus.OPEN) + _expected_count(
        status=TicketStatus.PENDING
    )
    assert len(multi) == expected
    assert {item["status"] for item in multi} == {"open", "pending"}


def test_priority_and_category_filters(auth_client: TestClient, seeded: None) -> None:
    urgent = _all_items(auth_client, priority="urgent")
    assert len(urgent) == _expected_count(priority=TicketPriority.URGENT)
    assert {item["priority"] for item in urgent} == {"urgent"}

    billing = _all_items(auth_client, category="billing")
    assert len(billing) == _expected_count(category="billing")
    assert {item["category"] for item in billing} == {"billing"}

    combined = _all_items(auth_client, category="billing", priority="urgent")
    assert len(combined) == _expected_count(
        category="billing", priority=TicketPriority.URGENT
    )


def test_assigned_agent_and_unassigned_filters(
    auth_client: TestClient, seeded: None
) -> None:
    assigned = _all_items(auth_client, assigned_agent_id="AG-02")
    assert len(assigned) == _expected_count(assigned_agent_id="AG-02")
    assert {item["assigned_agent_id"] for item in assigned} == {"AG-02"}

    unassigned = _all_items(auth_client, unassigned="true")
    assert len(unassigned) == _expected_count(assigned_agent_id=None)
    assert {item["assigned_agent_id"] for item in unassigned} == {None}


def test_unassigned_and_agent_filter_cannot_be_combined(
    auth_client: TestClient, seeded: None
) -> None:
    response = auth_client.get(
        "/api/v1/tickets",
        params={"unassigned": "true", "assigned_agent_id": "AG-02"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"


def test_sorting_uses_domain_order_and_is_deterministic(
    auth_client: TestClient, seeded: None
) -> None:
    rank = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    by_priority = _all_items(auth_client, sort_by="priority", sort_dir="asc")
    ranks = [rank[item["priority"]] for item in by_priority]
    assert ranks == sorted(ranks)
    assert by_priority[0]["priority"] == "urgent"

    newest = _all_items(auth_client, sort_by="created_at", sort_dir="desc")
    assert newest[0]["id"] == "TF-1051"
    oldest = _all_items(auth_client, sort_by="created_at", sort_dir="asc")
    assert oldest[0]["id"] == "TF-1028"

    subjects = [item["subject"].lower() for item in _all_items(auth_client, sort_by="subject", sort_dir="asc")]
    assert subjects == sorted(subjects)


def test_invalid_query_values_return_validation_errors(
    auth_client: TestClient, seeded: None
) -> None:
    cases = [
        {"page": 0},
        {"page": "abc"},
        {"page_size": 0},
        {"page_size": 101},
        {"status": "bogus"},
        {"priority": "critical"},
        {"category": "refunds"},
        {"sort_by": "id; DROP TABLE tickets"},
        {"sort_dir": "sideways"},
        {"unassigned": "maybe"},
    ]
    for params in cases:
        response = auth_client.get("/api/v1/tickets", params=params)
        assert response.status_code == 422, (params, response.text)
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert error["details"]
        # Never echo the submitted value back as SQL.
        assert "DROP TABLE" not in response.text


def test_detail_returns_ticket_with_requester_summary(
    auth_client: TestClient, seeded: None
) -> None:
    response = auth_client.get("/api/v1/tickets/TF-1051")
    assert response.status_code == 200
    ticket = response.json()

    assert ticket["id"] == "TF-1051"
    assert ticket["subject"] == "Charged twice from Telebirr for order #ET-88412"
    assert ticket["requester"] == {
        "id": ticket["requester"]["id"],
        "name": "Marta Alemu",
        "email": "marta.alemu@myetmail.example",
    }
    assert ticket["requester"]["id"]
    assert ticket["assigned_agent_id"] == "AG-02"
    assert ticket["assigned_agent_name"] == "Hana Tesfaye"
    assert ticket["assigned_team"] == "billing_team"
    assert ticket["status"] == "open"
    assert ticket["category"] == "billing"
    assert ticket["priority"] == "urgent"
    assert ticket["review_note"] is None
    assert ticket["suggested_category"] == "billing"
    assert ticket["due_at"] is None or ISO_UTC.match(ticket["due_at"])
    assert ISO_UTC.match(ticket["created_at"])
    assert ticket["description"].startswith("I paid for one order")

    # Related collections are intentionally not embedded in this phase.
    assert "replies" not in ticket
    assert "activity" not in ticket
    assert "activities" not in ticket


def test_detail_returns_review_metadata(auth_client: TestClient, seeded: None) -> None:
    ticket = auth_client.get("/api/v1/tickets/TF-1038").json()
    assert ticket["status"] == "needs_review"
    assert ticket["suggested_priority"] == "urgent"
    assert ticket["review_note"].startswith("Possible account merge issue")
    assert ticket["assigned_agent_id"] is None


def test_detail_is_case_insensitive_for_public_id(
    auth_client: TestClient, seeded: None
) -> None:
    response = auth_client.get("/api/v1/tickets/tf-1029")
    assert response.status_code == 200
    assert response.json()["id"] == "TF-1029"


def test_unknown_ticket_returns_404_envelope(
    auth_client: TestClient, seeded: None
) -> None:
    response = auth_client.get("/api/v1/tickets/TF-9999")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "ticket_not_found",
            "message": "Ticket TF-9999 was not found.",
        }
    }


def test_empty_result_is_not_an_error(auth_client: TestClient, seeded: None) -> None:
    response = auth_client.get("/api/v1/tickets", params={"search": "nothing-matches"})
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "pagination": {"page": 1, "page_size": 20, "total": 0, "page_count": 0},
    }


def test_unauthenticated_database_failure_is_sanitized() -> None:
    """Authentication is decided before any operational query runs.

    Without credentials the request is rejected as unauthenticated, so a
    database outage cannot leak driver details to anonymous callers. The
    sanitized 503 path is covered by the readiness probe tests.
    """
    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://ticketflow:secret@127.0.0.1:1/none",
    )
    with TestClient(create_app(settings)) as broken_client:
        response = broken_client.get("/api/v1/tickets")
        ready = broken_client.get("/api/v1/health/ready")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert ready.status_code == 503
    body = ready.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == "unavailable"
    body = (response.text + ready.text).lower()
    assert "secret" not in body
    assert "sqlalchemy" not in body
    assert "traceback" not in body
    assert "select" not in body
