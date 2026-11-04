"""Authorization, role boundaries and trusted actor attribution.

The permission matrix lives in ``app.authorization``. These tests exercise it
through HTTP so a route that forgets its dependency fails loudly, and they
prove that request bodies cannot select the acting account, reviewer or role.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_AGENT,
    AUTHOR_AGENT,
    REVIEWER_AGENT,
    use_account,
)
from tests.helpers import activity_rows, ticket_row

AUTHOR = AUTHOR_AGENT  # AG-03, account role agent
REVIEWER = REVIEWER_AGENT  # AG-01, account role reviewer
ADMIN = ADMIN_AGENT  # AG-08, account role admin

FREE_TICKET = "TF-1050"  # seeded, no reply
OTHER_FREE_TICKET = "TF-1049"  # seeded, no reply


def _create_reply(
    auth_client: TestClient, *, ticket: str, actor: str, body: str = "Hello."
) -> dict:
    use_account(auth_client, actor)
    response = auth_client.post(
        f"/api/v1/tickets/{ticket}/replies", json={"body": body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _submit(auth_client: TestClient, reply_id: str, *, actor: str) -> dict:
    use_account(auth_client, actor)
    response = auth_client.post(f"/api/v1/replies/{reply_id}/submit", json={})
    assert response.status_code == 200, response.text
    return response.json()


def _review(
    auth_client: TestClient, reply_id: str, action: str, *, actor: str, version: int = 1
):
    use_account(auth_client, actor)
    body: dict = {"version": version}
    if action == "request-changes":
        body["comment"] = "Please revise this reply."
    return auth_client.post(f"/api/v1/replies/{reply_id}/{action}", json=body)


# ---------------------------------------------------------------------------
# Authentication boundary
# ---------------------------------------------------------------------------

_GET_PATHS = [
    "/api/v1/tickets",
    "/api/v1/tickets/TF-1046",
    "/api/v1/tickets/TF-1046/notes",
    "/api/v1/tickets/TF-1046/replies",
    "/api/v1/tickets/TF-1046/activities",
    "/api/v1/replies",
    "/api/v1/replies/approvals",
    "/api/v1/replies/REP-101",
    "/api/v1/activities",
    "/api/v1/agents",
    "/api/v1/dashboard/summary",
    "/api/v1/auth/me",
]


def test_every_operational_route_requires_authentication(
    client: TestClient, seeded: None
) -> None:
    for path in _GET_PATHS:
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "not_authenticated", path

    logout = client.post(
        "/api/v1/auth/logout", headers={"X-Requested-With": "ticketflow"}
    )
    # Logout is intentionally safe without a valid access token.
    assert logout.status_code == 200

    posts = [
        ("/api/v1/tickets/TF-1046/notes", {"content": "hidden"}),
        ("/api/v1/tickets/TF-1046/replies", {"body": "hidden"}),
        ("/api/v1/replies/REP-101/submit", {}),
        ("/api/v1/replies/REP-101/approve", {"version": 1}),
        ("/api/v1/replies/REP-101/request-changes", {"version": 1, "comment": "x"}),
        ("/api/v1/replies/REP-101/send-demo", {}),
    ]
    for path, body in posts:
        response = client.post(path, json=body)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "not_authenticated", path

    patches = [
        ("/api/v1/tickets/TF-1046/status", {"status": "open"}),
        ("/api/v1/tickets/TF-1046/priority", {"priority": "low"}),
        ("/api/v1/tickets/TF-1046/category", {"category": "general"}),
        ("/api/v1/tickets/TF-1046/assignment", {"agent_id": None}),
    ]
    for path, body in patches:
        response = client.patch(path, json=body)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "not_authenticated", path


def test_unauthenticated_mutation_changes_nothing(
    client: TestClient, seeded: None, session_factory
) -> None:
    before = ticket_row(session_factory, "TF-1046")
    response = client.patch(
        "/api/v1/tickets/TF-1046/priority", json={"priority": "low"}
    )
    assert response.status_code == 401
    assert ticket_row(session_factory, "TF-1046") == before


# ---------------------------------------------------------------------------
# Role boundaries
# ---------------------------------------------------------------------------


def test_agent_cannot_review_replies(auth_client: TestClient, seeded: None) -> None:
    reply = _create_reply(auth_client, ticket=FREE_TICKET, actor=AUTHOR)
    _submit(auth_client, reply["id"], actor=AUTHOR)

    approve = _review(auth_client, reply["id"], "approve", actor=AUTHOR)
    assert approve.status_code == 403
    assert approve.json()["error"]["code"] == "forbidden"

    changes = _review(
        auth_client, reply["id"], "request-changes", actor=AUTHOR
    )
    assert changes.status_code == 403
    assert changes.json()["error"]["code"] == "forbidden"

    # The pending reply is untouched and a reviewer can still decide.
    use_account(auth_client, AUTHOR)
    assert auth_client.get(f"/api/v1/replies/{reply['id']}").json()[
        "state"
    ] == "pending_approval"
    approved = _review(auth_client, reply["id"], "approve", actor=REVIEWER)
    assert approved.status_code == 200, approved.text
    assert approved.json()["reviewer_id"] == REVIEWER


def test_admin_cannot_approve_their_own_reply(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _create_reply(auth_client, ticket=FREE_TICKET, actor=ADMIN)
    _submit(auth_client, reply["id"], actor=ADMIN)

    # Administrators have the review permission, but never on their own draft.
    own = _review(auth_client, reply["id"], "approve", actor=ADMIN)
    assert own.status_code == 403
    assert own.json()["error"]["code"] == "self_approval_forbidden"

    also_request_changes = _review(
        auth_client, reply["id"], "request-changes", actor=ADMIN
    )
    assert also_request_changes.status_code == 403
    assert also_request_changes.json()["error"]["code"] == "self_approval_forbidden"

    other = _review(auth_client, reply["id"], "approve", actor=REVIEWER)
    assert other.status_code == 200, other.text
    assert other.json()["state"] == "approved"
    assert other.json()["reviewer_id"] == REVIEWER


def test_reviewer_cannot_approve_their_own_reply(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _create_reply(auth_client, ticket=OTHER_FREE_TICKET, actor=REVIEWER)
    _submit(auth_client, reply["id"], actor=REVIEWER)

    own = _review(auth_client, reply["id"], "approve", actor=REVIEWER)
    assert own.status_code == 403
    assert own.json()["error"]["code"] == "self_approval_forbidden"

    other = _review(auth_client, reply["id"], "approve", actor=ADMIN)
    assert other.status_code == 200, other.text
    assert other.json()["reviewer_id"] == ADMIN


def test_approval_does_not_send(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _create_reply(auth_client, ticket=FREE_TICKET, actor=AUTHOR)
    _submit(auth_client, reply["id"], actor=AUTHOR)
    approved = _review(auth_client, reply["id"], "approve", actor=REVIEWER)
    assert approved.status_code == 200
    assert approved.json()["state"] == "approved"
    assert approved.json()["sent_at"] is None


def test_demo_send_requires_the_approval_gate(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _create_reply(auth_client, ticket=FREE_TICKET, actor=AUTHOR)
    _submit(auth_client, reply["id"], actor=AUTHOR)

    blocked = _review(auth_client, reply["id"], "send-demo", actor=AUTHOR)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "approval_required"

    assert _review(auth_client, reply["id"], "approve", actor=REVIEWER).status_code == 200
    sent = _review(auth_client, reply["id"], "send-demo", actor=AUTHOR)
    assert sent.status_code == 200, sent.text
    assert sent.json()["reply"]["state"] == "sent"
    assert sent.json()["delivery"] == "demo_marked_sent"


# ---------------------------------------------------------------------------
# Trusted attribution / spoofed fields
# ---------------------------------------------------------------------------


def test_note_author_comes_from_the_access_token(
    auth_client: TestClient, seeded: None, session_factory
) -> None:
    use_account(auth_client, AUTHOR)
    response = auth_client.post(
        "/api/v1/tickets/TF-1046/notes",
        json={
            "content": "Verified attribution test note.",
            "author_id": ADMIN,
            "author_name": "Spoofed Admin",
            "actor_id": ADMIN,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["author"]["id"] == AUTHOR
    assert response.json()["author"]["name"] == "Dawit Mengistu"

    notes = activity_rows(session_factory, "TF-1046")
    note_events = [row for row in notes if row["action"] == "note_added"]
    assert note_events[-1]["actor_id"] == AUTHOR


def test_ticket_mutation_actor_comes_from_the_access_token(
    auth_client: TestClient, seeded: None, session_factory
) -> None:
    use_account(auth_client, AUTHOR)
    from tests.helpers import ticket_version

    response = auth_client.patch(
        "/api/v1/tickets/TF-1046/status",
        json={
            "status": "open",
            "expected_version": ticket_version(auth_client, "TF-1046"),
            "actor_id": ADMIN,
            "actor_name": "Spoofed Admin",
        },
    )
    assert response.status_code == 200, response.text

    events = [
        row
        for row in activity_rows(session_factory, "TF-1046")
        if row["action"] == "status_changed"
    ]
    assert events
    assert events[-1]["actor_id"] == AUTHOR


def test_reply_author_and_reviewer_are_never_caller_supplied(
    auth_client: TestClient, seeded: None
) -> None:
    use_account(auth_client, AUTHOR)
    created = auth_client.post(
        f"/api/v1/tickets/{FREE_TICKET}/replies",
        json={"body": "Attribution test.", "author_id": ADMIN, "reviewer_id": ADMIN},
    )
    assert created.status_code == 201, created.text
    reply = created.json()
    assert reply["author"]["id"] == AUTHOR

    _submit(auth_client, reply["id"], actor=AUTHOR)
    use_account(auth_client, REVIEWER)
    approved = auth_client.post(
        f"/api/v1/replies/{reply['id']}/approve",
        json={"version": 1, "reviewer_id": ADMIN, "reviewer_name": "Spoofed"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["reviewer_id"] == REVIEWER
    assert approved.json()["reviewer_name"] == "Abebe Kebede"
