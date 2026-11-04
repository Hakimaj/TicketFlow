"""Persistent customer reply drafts, revisions, approval queue and review.

All tests run against the real PostgreSQL test database. Workflow transitions
are driven through the HTTP API unless a test explicitly needs to simulate
tampered/inconsistent persisted state at the service or database layer.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models.activity import TicketActivity
from app.models.enums import ReplyState
from app.models.reply import CustomerReply, ReplyRevision
from app.models.ticket import Ticket
from app.schemas.replies import ReplySubmit
from tests.conftest import AUTHOR_AGENT, REVIEWER_AGENT, principal_for, use_account
from tests.helpers import activity_rows, ticket_row

AUTHOR = AUTHOR_AGENT  # AG-03, account role agent
REVIEWER = REVIEWER_AGENT  # AG-01, account role reviewer
TICKET = "TF-1050"  # seeded, status new, no reply


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create(
    auth_client: TestClient,
    body: str = "Dear Abel, your parcel is on its way.",
    *,
    ticket: str = TICKET,
    actor: str = AUTHOR,
):
    use_account(auth_client, actor)
    return auth_client.post(
        f"/api/v1/tickets/{ticket}/replies", json={"body": body}
    )


def _draft(auth_client: TestClient, body: str = "Dear Abel, your parcel is on its way.") -> dict:
    response = _create(auth_client, body)
    assert response.status_code == 201, response.text
    return response.json()


def _submit(auth_client: TestClient, reply_id: str, *, actor: str = AUTHOR):
    use_account(auth_client, actor)
    return auth_client.post(f"/api/v1/replies/{reply_id}/submit", json={})


def _approve(
    auth_client: TestClient,
    reply_id: str,
    version: int,
    *,
    reviewer: str = REVIEWER,
    comment: str | None = None,
):
    use_account(auth_client, reviewer)
    payload: dict = {"version": version}
    if comment is not None:
        payload["comment"] = comment
    return auth_client.post(f"/api/v1/replies/{reply_id}/approve", json=payload)


def _request_changes(
    auth_client: TestClient,
    reply_id: str,
    version: int,
    comment: str = "Please add the delivery window.",
    *,
    reviewer: str = REVIEWER,
):
    use_account(auth_client, reviewer)
    return auth_client.post(
        f"/api/v1/replies/{reply_id}/request-changes",
        json={"version": version, "comment": comment},
    )


def _send(auth_client: TestClient, reply_id: str, *, actor: str = REVIEWER):
    use_account(auth_client, actor)
    return auth_client.post(f"/api/v1/replies/{reply_id}/send-demo", json={})


def _approved_reply(auth_client: TestClient, body: str = "Dear Abel, all set.") -> dict:
    reply = _draft(auth_client, body)
    assert _submit(auth_client, reply["id"]).status_code == 200
    response = _approve(auth_client, reply["id"], reply["version"])
    assert response.status_code == 200, response.text
    return response.json()


def _revision_bodies(session_factory, reply_id: str) -> list[str]:
    with session_factory() as session:
        reply = session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == reply_id)
        )
        return list(
            session.scalars(
                select(ReplyRevision.body)
                .where(ReplyRevision.reply_id == reply.id)
                .order_by(ReplyRevision.version.asc())
            ).all()
        )


def _reply_row(session_factory, reply_id: str) -> CustomerReply:
    with session_factory() as session:
        return session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == reply_id)
        )


# ---------------------------------------------------------------------------
# Drafts and revisions
# ---------------------------------------------------------------------------


def test_create_draft_persists_revision_and_safe_audit(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    before = ticket_row(session_factory, TICKET)
    response = _create(auth_client, "  Dear Abel, we found your parcel.  ")
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["ticket_id"] == TICKET
    assert body["state"] == "draft"
    assert body["version"] == 1
    assert body["body"] == "Dear Abel, we found your parcel."
    assert body["author"] == {"id": AUTHOR, "name": "Dawit Mengistu"}
    # Recipient is derived from the ticket's requester, never supplied.
    assert body["recipient"] == {
        "name": "Abel Tesfaye",
        "email": "abel.tesfaye@myetmail.example",
    }
    assert body["submitted_at"] is None
    assert body["submitted_version"] is None
    assert body["approved_version"] is None
    assert body["sent_at"] is None
    assert [item["version"] for item in body["revisions"]] == [1]
    assert body["revisions"][0]["body"] == body["body"]
    assert body["reviews"] == []

    assert _revision_bodies(session_factory, body["id"]) == [body["body"]]

    after = ticket_row(session_factory, TICKET)
    assert after["status"] == before["status"]

    events = activity_rows(session_factory, TICKET)
    assert len(events) == 1
    assert events[0]["action"] == "replied_draft"
    assert events[0]["actor_id"] == AUTHOR
    assert body["body"] not in (events[0]["detail"] or "")
    stored = auth_client.get(f"/api/v1/replies/{body['id']}").json()
    assert stored["reviews"] == []


def test_only_one_active_reply_per_ticket(
    auth_client: TestClient, seeded: None
) -> None:
    first = _draft(auth_client)
    second = _create(auth_client)
    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "reply_already_exists"
    assert first["id"] in error["message"]

    # Sent replies are history; a follow-up draft may start afterwards.
    assert _submit(auth_client, first["id"]).status_code == 200
    assert _approve(auth_client, first["id"], 1).status_code == 200
    assert _send(auth_client, first["id"]).status_code == 200
    follow_up = _create(auth_client, "Dear Abel, following up on the delivery.")
    assert follow_up.status_code == 201
    assert follow_up.json()["id"] != first["id"]


def test_empty_and_oversized_drafts_rejected(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    for body in ("", "   \n\t ", "x" * 8001):
        response = _create(auth_client, body)
        assert response.status_code == 422, body[:20]
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert error["details"][0]["field"] == "body"

    with session_factory() as session:
        assert int(
            session.scalar(
                select(func.count()).select_from(CustomerReply)
            )
            or 0
        ) == 5


def test_whitespace_body_cannot_be_persisted_or_submitted(
    auth_client: TestClient, monkeypatch, session_factory, seeded: None
) -> None:
    from types import SimpleNamespace

    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.core.errors import ApiError
    from app.services import replies as reply_service

    reply = _draft(auth_client)
    # The database itself now rejects a blank persisted body.
    with session_factory() as session:
        row = session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == reply["id"])
        )
        row.body = "   "
        with pytest.raises(IntegrityError):
            session.commit()

    # Defensive service guard: even a blank row that somehow existed could not
    # be submitted. A stub exercises the branch without bypassing the database.
    stub = SimpleNamespace(
        state=ReplyState.DRAFT,
        public_id="REP-000000000000",
        body="   ",
        version=1,
    )
    monkeypatch.setattr(
        reply_service.reply_repo,
        "lock_reply",
        lambda db, public_id: stub,
    )
    with session_factory() as session:
        with pytest.raises(ApiError) as excinfo:
            reply_service.submit_for_approval(
                session,
                "REP-000000000000",
                ReplySubmit(),
                principal=principal_for(session_factory, AUTHOR),
            )
    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "reply_empty"


def test_editing_a_draft_creates_a_new_immutable_revision(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    reply = _draft(auth_client, "First version.")
    use_account(auth_client, AUTHOR)
    edited = auth_client.patch(
        f"/api/v1/replies/{reply['id']}",
        json={"body": "Second version."},
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["version"] == 2
    assert body["body"] == "Second version."
    assert body["state"] == "draft"
    assert [item["body"] for item in body["revisions"]] == [
        "First version.",
        "Second version.",
    ]
    assert _revision_bodies(session_factory, reply["id"]) == [
        "First version.",
        "Second version.",
    ]


def test_identical_save_is_a_true_noop(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    reply = _draft(auth_client, "Unchanged text.")
    with session_factory() as session:
        before = session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == reply["id"])
        )
        before_updated = before.updated_at

    use_account(auth_client, AUTHOR)
    saved = auth_client.patch(
        f"/api/v1/replies/{reply['id']}",
        json={"body": "  Unchanged text.  "},
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["version"] == 1
    assert len(body["revisions"]) == 1
    with session_factory() as session:
        after = session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == reply["id"])
        )
        assert after.updated_at == before_updated
        assert after.body == "Unchanged text."

    with session_factory() as session:
        assert int(
            session.scalar(
                select(func.count())
                .select_from(ReplyRevision)
                .where(
                    ReplyRevision.reply_id
                    == session.scalar(
                        select(CustomerReply.id).where(
                            CustomerReply.public_id == reply["id"]
                        )
                    )
                )
            )
            or 0
        ) == 1
    assert len(activity_rows(session_factory, TICKET)) == 1


def test_editing_pending_reply_withdraws_submission(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _draft(auth_client, "Pending text.")
    submitted = _submit(auth_client, reply["id"]).json()
    assert submitted["state"] == "pending_approval"

    edited = auth_client.patch(
        f"/api/v1/replies/{reply['id']}", json={"body": "Edited text."}
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["state"] == "draft"
    assert body["version"] == 2
    assert body["submitted_at"] is None
    assert body["submitted_version"] is None

    # It is no longer in the approval queue.
    queue = auth_client.get("/api/v1/replies/approvals").json()
    assert reply["id"] not in [item["reply_id"] for item in queue["items"]]


def test_editing_approved_reply_invalidates_approval(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    approved = _approved_reply(auth_client, "Approved wording.")
    assert approved["state"] == "approved"
    assert approved["approved_version"] == 1

    use_account(auth_client, AUTHOR)
    edited = auth_client.patch(
        f"/api/v1/replies/{approved['id']}",
        json={"body": "Changed wording."},
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["state"] == "draft"
    assert body["version"] == 2
    assert body["approved_version"] is None
    assert body["reviewer_id"] is None
    assert body["reviewer_name"] is None

    # The historical approval is retained as an append-only decision.
    assert [review["version"] for review in body["reviews"]] == [1]
    assert body["reviews"][0]["decision"] == "approved"

    # Reapproval of the new version unlocks sending.
    assert _submit(auth_client, approved["id"]).status_code == 200
    reapproved = _approve(auth_client, approved["id"], 2)
    assert reapproved.status_code == 200
    assert reapproved.json()["version"] == 2
    assert _send(auth_client, approved["id"]).status_code == 200


def test_sent_reply_is_immutable(auth_client: TestClient, seeded: None) -> None:
    approved = _approved_reply(auth_client)
    assert _send(auth_client, approved["id"]).status_code == 200

    response = auth_client.patch(
        f"/api/v1/replies/{approved['id']}", json={"body": "Too late."}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "reply_immutable"


def test_unknown_tickets_and_replies(
    auth_client: TestClient, seeded: None
) -> None:
    assert _create(auth_client, ticket="TF-9999").status_code == 404
    assert auth_client.get("/api/v1/tickets/TF-9999/replies").status_code == 404
    missing = auth_client.get("/api/v1/replies/REP-9999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "reply_not_found"
    for call in (
        _submit(auth_client, "REP-9999"),
        _approve(auth_client, "REP-9999", 1),
        _request_changes(auth_client, "REP-9999", 1),
        _send(auth_client, "REP-9999"),
    ):
        assert call.status_code == 404
        assert call.json()["error"]["code"] == "reply_not_found"


def test_replies_are_scoped_to_their_ticket(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _draft(auth_client)

    own = auth_client.get(f"/api/v1/tickets/{TICKET}/replies").json()
    other = auth_client.get("/api/v1/tickets/TF-1046/replies").json()

    assert [item["id"] for item in own["items"]] == [reply["id"]]
    assert own["pagination"]["total"] == 1
    assert other["items"] == []
    assert other["pagination"]["total"] == 0

    # Seeded replies stay on their own tickets.
    seeded_replies = auth_client.get("/api/v1/tickets/TF-1051/replies").json()
    assert [item["id"] for item in seeded_replies["items"]] == ["REP-101"]


def test_reply_list_pagination_and_ordering(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    approved = _approved_reply(auth_client, "First reply.")
    assert _send(auth_client, approved["id"]).status_code == 200
    second = _create(auth_client, "Second reply.")
    assert second.status_code == 201

    first_page = auth_client.get(
        f"/api/v1/tickets/{TICKET}/replies", params={"page": 1, "page_size": 1}
    ).json()
    second_page = auth_client.get(
        f"/api/v1/tickets/{TICKET}/replies", params={"page": 2, "page_size": 1}
    ).json()

    assert first_page["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "page_count": 2,
    }
    # Newest created first.
    assert first_page["items"][0]["id"] == second.json()["id"]
    assert second_page["items"][0]["id"] == approved["id"]


# ---------------------------------------------------------------------------
# Submission and approval
# ---------------------------------------------------------------------------


def test_submit_records_version_and_safe_audit(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    reply = _draft(auth_client, "Please review this wording.")
    response = _submit(auth_client, reply["id"])
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["state"] == "pending_approval"
    assert body["submitted_version"] == 1
    assert body["submitted_at"].endswith("Z")
    assert body["reviewer_id"] is None
    assert body["sent_at"] is None

    events = activity_rows(session_factory, TICKET)
    assert [event["action"] for event in events] == [
        "replied_draft",
        "reply_submitted",
    ]
    assert "Please review this wording." not in (events[-1]["detail"] or "")
    # Submission does not change ticket status.
    assert ticket_row(session_factory, TICKET)["status"] == "new"


def test_repeated_submission_is_rejected(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _draft(auth_client)
    assert _submit(auth_client, reply["id"]).status_code == 200

    repeated = _submit(auth_client, reply["id"])
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "reply_already_pending"


def test_submitting_approved_or_sent_reply_is_rejected(
    auth_client: TestClient, seeded: None
) -> None:
    approved = _approved_reply(auth_client)

    again = _submit(auth_client, approved["id"])
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "reply_already_approved"

    assert _send(auth_client, approved["id"]).status_code == 200
    sent = _submit(auth_client, approved["id"])
    assert sent.status_code == 409
    assert sent.json()["error"]["code"] == "reply_already_sent"


def test_approval_queue_contains_only_pending_replies(
    auth_client: TestClient, seeded: None
) -> None:
    queue = auth_client.get("/api/v1/replies/approvals")
    assert queue.status_code == 200
    payload = queue.json()
    assert [item["reply_id"] for item in payload["items"]] == [
        "REP-101",
        "REP-102",
    ]
    assert payload["pagination"]["total"] == 2

    first = payload["items"][0]
    assert first["ticket_id"] == "TF-1051"
    assert first["ticket_subject"].startswith("Charged twice")
    assert first["ticket_category"] == "billing"
    assert first["ticket_priority"] == "urgent"
    assert first["ticket_status"] == "open"
    assert first["author"] == {"id": "AG-02", "name": "Hana Tesfaye"}
    assert first["version"] == 1
    assert first["submitted_version"] == 1
    assert first["submitted_at"].endswith("Z")
    assert first["state"] == "pending_approval"
    assert first["preview"]
    assert len(first["preview"]) <= 180
    assert "\n" not in first["preview"]
    # No full body field in the queue payload.
    assert "body" not in first

    draft = _draft(auth_client)
    assert draft["id"] not in [
        item["reply_id"]
        for item in auth_client.get("/api/v1/replies/approvals").json()["items"]
    ]
    assert _submit(auth_client, draft["id"]).status_code == 200
    assert draft["id"] in [
        item["reply_id"]
        for item in auth_client.get("/api/v1/replies/approvals").json()["items"]
    ]


def test_approval_queue_filters_search_and_pagination(
    auth_client: TestClient, seeded: None
) -> None:
    new = _draft(auth_client, "Delivery update for Abel: courier assigned.")
    assert _submit(auth_client, new["id"]).status_code == 200

    billing = auth_client.get(
        "/api/v1/replies/approvals", params={"category": "billing"}
    ).json()
    assert [item["reply_id"] for item in billing["items"]] == ["REP-101"]

    technical = auth_client.get(
        "/api/v1/replies/approvals", params={"priority": "high"}
    ).json()
    assert [item["reply_id"] for item in technical["items"]] == ["REP-102"]

    combined = auth_client.get(
        "/api/v1/replies/approvals",
        params=[("category", "billing"), ("category", "delivery")],
    ).json()
    assert combined["pagination"]["total"] == 2

    by_ticket = auth_client.get(
        "/api/v1/replies/approvals", params={"search": "TF-1050"}
    ).json()
    assert [item["reply_id"] for item in by_ticket["items"]] == [new["id"]]

    by_body = auth_client.get(
        "/api/v1/replies/approvals", params={"search": "courier assigned"}
    ).json()
    assert [item["reply_id"] for item in by_body["items"]] == [new["id"]]

    by_author = auth_client.get(
        "/api/v1/replies/approvals", params={"search": "Dawit"}
    ).json()
    assert [item["reply_id"] for item in by_author["items"]] == [new["id"]]

    # Literal wildcard matching, not a LIKE wildcard.
    wildcard = auth_client.get(
        "/api/v1/replies/approvals", params={"search": "%"}
    ).json()
    assert wildcard["pagination"]["total"] == 0

    newest = auth_client.get(
        "/api/v1/replies/approvals", params={"page_size": 2}
    ).json()
    oldest = auth_client.get(
        "/api/v1/replies/approvals",
        params={"page_size": 2, "sort_dir": "asc"},
    ).json()
    assert newest["items"][0]["reply_id"] == new["id"]
    # REP-102 was submitted earlier than REP-101 in the fixtures.
    assert oldest["items"][0]["reply_id"] == "REP-102"
    assert newest["pagination"]["page_count"] == 2

    second_page = auth_client.get(
        "/api/v1/replies/approvals", params={"page": 2, "page_size": 2}
    ).json()
    assert len(second_page["items"]) == 1
    assert second_page["items"][0]["reply_id"] == "REP-102"


def test_approval_queue_query_validation(auth_client: TestClient, seeded: None) -> None:
    for params in (
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"category": "bogus"},
        {"priority": "later"},
        {"sort_dir": "sideways"},
    ):
        response = auth_client.get("/api/v1/replies/approvals", params=params)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


def test_approve_exact_version_without_sending(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    reply = _draft(auth_client)
    assert _submit(auth_client, reply["id"]).status_code == 200

    response = _approve(auth_client, reply["id"], 1, comment="Looks good.")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["state"] == "approved"
    assert body["approved_version"] == 1
    assert body["reviewer_id"] == REVIEWER
    assert body["reviewer_name"] == "Abebe Kebede"
    assert body["reviewed_at"].endswith("Z")
    assert body["sent_at"] is None
    # Approval never changes the ticket status.
    assert ticket_row(session_factory, TICKET)["status"] == "new"

    assert len(body["reviews"]) == 1
    assert body["reviews"][0]["decision"] == "approved"
    assert body["reviews"][0]["comment"] == "Looks good."
    assert body["reviews"][0]["version"] == 1

    events = activity_rows(session_factory, TICKET)
    assert [event["action"] for event in events] == [
        "replied_draft",
        "reply_submitted",
        "reply_approved",
    ]
    assert "Looks good." not in (events[-1]["detail"] or "")


def test_approving_non_pending_reply_is_rejected(
    auth_client: TestClient, seeded: None
) -> None:
    draft = _draft(auth_client)
    response = _approve(auth_client, draft["id"], 1)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "reply_not_pending"

    assert _submit(auth_client, draft["id"]).status_code == 200
    assert _approve(auth_client, draft["id"], 1).status_code == 200
    repeated = _approve(auth_client, draft["id"], 1)
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "reply_not_pending"


def test_stale_version_approval_is_rejected(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _draft(auth_client, "Version one.")
    assert _submit(auth_client, reply["id"]).status_code == 200
    assert _request_changes(auth_client, reply["id"], 1).status_code == 200
    assert (
        auth_client.patch(
            f"/api/v1/replies/{reply['id']}", json={"body": "Version two."}
        ).status_code
        == 200
    )
    assert _submit(auth_client, reply["id"]).status_code == 200

    stale = _approve(auth_client, reply["id"], 1)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "reply_version_conflict"

    current = _approve(auth_client, reply["id"], 2)
    assert current.status_code == 200
    assert current.json()["approved_version"] == 2


def test_request_changes_requires_internal_comment(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    reply = _draft(auth_client, "Please review.")
    assert _submit(auth_client, reply["id"]).status_code == 200

    for comment in ("", "   \n "):
        response = _request_changes(auth_client, reply["id"], 1, comment=comment)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert response.json()["error"]["details"][0]["field"] == "comment"

    assert auth_client.get(f"/api/v1/replies/{reply['id']}").json()[
        "state"
    ] == "pending_approval"

    too_long = _request_changes(auth_client, reply["id"], 1, comment="x" * 2001)
    assert too_long.status_code == 422


def test_request_changes_keeps_feedback_internal(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    marker = "internal-feedback-9c14"
    reply = _draft(auth_client, "Customer-visible words.")
    assert _submit(auth_client, reply["id"]).status_code == 200

    response = _request_changes(
        auth_client, reply["id"], 1, comment=f"Add the timeline. {marker}"
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["state"] == "changes_requested"
    assert body["reviewer_feedback"] == f"Add the timeline. {marker}"
    assert marker not in body["body"]
    assert body["approved_version"] is None
    assert body["reviews"][0]["comment"] == f"Add the timeline. {marker}"
    assert body["reviews"][0]["version"] == 1

    events = activity_rows(session_factory, TICKET)
    assert events[-1]["action"] == "reply_changes_requested"
    assert marker not in (events[-1]["detail"] or "")

    global_log = auth_client.get(
        "/api/v1/activities", params={"search": marker}
    ).json()
    assert global_log["pagination"]["total"] == 0
    # The comment is available to staff on the reply, never in the body.
    assert body["reviews"][0]["comment"].endswith(marker)
    assert marker not in body["body"]


def test_revised_reply_requires_new_approval(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    reply = _draft(auth_client, "Initial draft.")
    assert _submit(auth_client, reply["id"]).status_code == 200
    assert _request_changes(auth_client, reply["id"], 1).status_code == 200

    use_account(auth_client, AUTHOR)
    revised = auth_client.patch(
        f"/api/v1/replies/{reply['id']}",
        json={"body": "Initial draft with the timeline."},
    )
    assert revised.status_code == 200
    body = revised.json()
    assert body["state"] == "draft"
    assert body["version"] == 2
    assert body["reviewer_feedback"] is None
    assert body["submitted_at"] is None
    # Prior decision survives the revision.
    assert [(item["version"], item["decision"]) for item in body["reviews"]] == [
        (1, "changes_requested")
    ]

    assert _submit(auth_client, reply["id"]).status_code == 200
    reapproved = _approve(auth_client, reply["id"], 2)
    assert reapproved.status_code == 200
    assert reapproved.json()["approved_version"] == 2
    assert len(reapproved.json()["reviews"]) == 2


def test_changes_requested_can_be_resubmitted_without_edit(
    auth_client: TestClient, seeded: None
) -> None:
    """Same policy as the frontend demo service: resubmission is allowed."""
    reply = _draft(auth_client, "Resubmit me.")
    assert _submit(auth_client, reply["id"]).status_code == 200
    assert _request_changes(auth_client, reply["id"], 1).status_code == 200

    response = _submit(auth_client, reply["id"])
    assert response.status_code == 200
    assert response.json()["state"] == "pending_approval"
    assert response.json()["version"] == 1


def test_reviewer_is_the_authenticated_account(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    reply = _draft(auth_client)
    assert _submit(auth_client, reply["id"]).status_code == 200

    # Caller-supplied reviewer/role fields cannot change who is recorded.
    use_account(auth_client, REVIEWER)
    approved = auth_client.post(
        f"/api/v1/replies/{reply['id']}/approve",
        json={"version": 1, "reviewer_id": "AG-08", "role": "admin"},
    ).json()
    assert approved["reviewer_id"] == REVIEWER
    assert approved["reviewer_name"] == "Abebe Kebede"
    assert approved["reviews"][0]["reviewer_id"] == REVIEWER


# ---------------------------------------------------------------------------
# Global reply listing (approvals workspace)
# ---------------------------------------------------------------------------


def test_list_all_replies_includes_every_state(
    auth_client: TestClient, seeded: None
) -> None:
    """The full listing returns all states joined to their parent ticket."""
    from app.seed import REPLY_SEEDS

    response = auth_client.get("/api/v1/replies")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == len(REPLY_SEEDS)

    states = {item["reply"]["state"] for item in body["items"]}
    assert states <= {state.value for state in ReplyState} | states
    # Every item pairs the reply with a real parent ticket.
    for item in body["items"]:
        reply = item["reply"]
        ticket = item["ticket"]
        assert reply["ticket_id"] == ticket["id"]
        assert set(ticket) == {
            "id",
            "subject",
            "category",
            "priority",
            "status",
            "requester_name",
            "created_at",
        }
        assert reply["body"]  # full bodies, not just previews

    paginated = auth_client.get("/api/v1/replies?page=1&page_size=2")
    assert len(paginated.json()["items"]) == 2
    assert paginated.json()["pagination"]["total"] == len(REPLY_SEEDS)

    searched = auth_client.get(
        "/api/v1/replies",
        params={"search": body["items"][0]["ticket"]["id"]},
    )
    assert searched.json()["pagination"]["total"] >= 1


# ---------------------------------------------------------------------------
# Dashboard and audit integration
# ---------------------------------------------------------------------------


def test_dashboard_reply_counts_follow_transitions(
    auth_client: TestClient, seeded: None
) -> None:
    before = auth_client.get("/api/v1/dashboard/summary").json()
    assert before["pending_reply_approvals"] == 2
    assert before["draft_replies"] == 0
    assert before["approved_replies_awaiting_send"] == 1
    assert before["sent_replies_demo"] == 1
    needs_review_before = before["needs_review_tickets"]

    reply = _draft(auth_client)
    after_draft = auth_client.get("/api/v1/dashboard/summary").json()
    assert after_draft["draft_replies"] == 1
    assert after_draft["pending_reply_approvals"] == 2

    assert _submit(auth_client, reply["id"]).status_code == 200
    after_submit = auth_client.get("/api/v1/dashboard/summary").json()
    assert after_submit["draft_replies"] == 0
    assert after_submit["pending_reply_approvals"] == 3

    assert _approve(auth_client, reply["id"], 1).status_code == 200
    after_approve = auth_client.get("/api/v1/dashboard/summary").json()
    assert after_approve["pending_reply_approvals"] == 2
    assert after_approve["approved_replies_awaiting_send"] == 2

    assert _send(auth_client, reply["id"]).status_code == 200
    after_send = auth_client.get("/api/v1/dashboard/summary").json()
    assert after_send["approved_replies_awaiting_send"] == 1
    assert after_send["sent_replies_demo"] == 2

    # Ticket-level review stays independent of reply approvals.
    assert after_send["needs_review_tickets"] == needs_review_before


def test_approval_counts_do_not_count_revisions(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _draft(auth_client, "Version one.")
    for text in ("Version two.", "Version three."):
        assert (
            auth_client.patch(
                f"/api/v1/replies/{reply['id']}", json={"body": text}
            ).status_code
            == 200
        )
    assert _submit(auth_client, reply["id"]).status_code == 200

    stored = auth_client.get(f"/api/v1/replies/{reply['id']}").json()
    assert stored["version"] == 3
    assert len(stored["revisions"]) == 3
    assert auth_client.get("/api/v1/dashboard/summary").json()[
        "pending_reply_approvals"
    ] == 3  # 2 seeded + this one logical reply


def test_every_transition_writes_one_safe_activity(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    reply = _draft(auth_client, "Body content that must never be logged.")
    assert _submit(auth_client, reply["id"]).status_code == 200
    assert _approve(auth_client, reply["id"], 1).status_code == 200
    assert _send(auth_client, reply["id"]).status_code == 200

    events = activity_rows(session_factory, TICKET)
    actions = [event["action"] for event in events]
    # The send transition writes the demo-send event and the ticket-status
    # event in the same transaction; their relative order is not significant.
    assert [action for action in actions if action != "status_changed"] == [
        "replied_draft",
        "reply_submitted",
        "reply_approved",
        "replied_sent",
    ]
    assert actions.count("status_changed") == 1
    stored = _reply_row(session_factory, reply["id"])
    for event in events:
        assert "Body content that must never be logged." not in (
            event["detail"] or ""
        )
        assert len(event["detail"] or "") < 300

    with session_factory() as session:
        linked = session.scalars(
            select(TicketActivity).where(
                TicketActivity.ticket_id
                == session.scalar(
                    select(Ticket.id).where(Ticket.public_id == TICKET)
                )
            )
        ).all()
    reply_events = [row for row in linked if row.reply_id == stored.id]
    assert len(reply_events) == 5
    assert {row.reply_version for row in reply_events} == {1}


def test_activity_log_exposes_reply_version(
    auth_client: TestClient, seeded: None
) -> None:
    reply = _draft(auth_client)
    events = auth_client.get(f"/api/v1/tickets/{TICKET}/activities").json()
    assert events[-1]["reply_id"] == reply["id"]
    assert events[-1]["reply_version"] == 1
    assert events[-1]["action"] == "replied_draft"
