"""Server-enforced demo-send approval gate, rollback and concurrency.

The gate is enforced in the service layer and mirrored by PostgreSQL check
constraints; these tests exercise it through HTTP, through direct service calls
(a bypass attempt) and with two simultaneous send requests on real PostgreSQL
connections.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.models.activity import TicketActivity
from app.models.enums import ReplyState
from app.models.reply import CustomerReply, ReplyReview, ReplyRevision
from app.schemas.replies import (
    ReplyApprove,
    ReplyCreate,
    ReplyRequestChanges,
    ReplySendDemo,
    ReplySubmit,
    ReplyUpdate,
)
from app.services import replies as reply_service
from tests.conftest import (
    AUTHOR_AGENT,
    REVIEWER_AGENT,
    principal_for,
    use_account,
)
from tests.helpers import activity_rows, ticket_row

AUTHOR = AUTHOR_AGENT  # AG-03, account role agent
REVIEWER = REVIEWER_AGENT  # AG-01, account role reviewer

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _draft(auth_client: TestClient, ticket: str = "TF-1050", body: str = "Hello.") -> dict:
    use_account(auth_client, AUTHOR)
    response = auth_client.post(
        f"/api/v1/tickets/{ticket}/replies", json={"body": body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _submit(auth_client: TestClient, reply_id: str) -> dict:
    use_account(auth_client, AUTHOR)
    response = auth_client.post(
        f"/api/v1/replies/{reply_id}/submit", json={}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _approve(auth_client: TestClient, reply_id: str, version: int) -> dict:
    use_account(auth_client, REVIEWER)
    response = auth_client.post(
        f"/api/v1/replies/{reply_id}/approve", json={"version": version}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _send(auth_client: TestClient, reply_id: str, actor: str = REVIEWER):
    use_account(auth_client, actor)
    return auth_client.post(f"/api/v1/replies/{reply_id}/send-demo", json={})


def _approved(auth_client: TestClient, ticket: str = "TF-1050") -> dict:
    reply = _draft(auth_client, ticket)
    _submit(auth_client, reply["id"])
    return _approve(auth_client, reply["id"], reply["version"])


def _count(session_factory, model) -> int:
    with session_factory() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


# ---------------------------------------------------------------------------
# Gate rejections
# ---------------------------------------------------------------------------


def test_draft_pending_and_changes_requested_cannot_be_sent(
    auth_client: TestClient, seeded: None
) -> None:
    draft = _draft(auth_client, "TF-1046", "Not approved.")
    rejected = _send(auth_client, draft["id"])
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "approval_required"

    _submit(auth_client, draft["id"])
    pending = _send(auth_client, draft["id"])
    assert pending.status_code == 409
    assert pending.json()["error"]["code"] == "approval_required"

    use_account(auth_client, REVIEWER)
    changes = auth_client.post(
        f"/api/v1/replies/{draft['id']}/request-changes",
        json={
            "version": 1,
            "comment": "Please reword the closing line.",
        },
    )
    assert changes.status_code == 200
    withheld = _send(auth_client, draft["id"])
    assert withheld.status_code == 409
    assert withheld.json()["error"]["code"] == "approval_required"

    stored = auth_client.get(f"/api/v1/replies/{draft['id']}").json()
    assert stored["state"] == "changes_requested"
    assert stored["sent_at"] is None


def test_approved_reply_can_be_sent_and_records_metadata(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    approved = _approved(auth_client, "TF-1050")
    assert approved["state"] == "approved"

    response = _send(auth_client, approved["id"])
    assert response.status_code == 200, response.text
    payload = response.json()
    reply = payload["reply"]

    assert payload["delivery"] == "demo_marked_sent"
    assert "No email, SMS or other customer message was delivered." in (
        payload["notice"]
    )
    assert reply["state"] == "sent"
    assert reply["sent_at"].endswith("Z")
    assert reply["sent_by_actor_name"] == "Abebe Kebede"
    assert reply["approved_version"] == 1

    # Documented ticket rule: new/open -> pending on demo send.
    assert ticket_row(session_factory, "TF-1050")["status"] == "pending"

    events = activity_rows(session_factory, "TF-1050")
    sent_events = [e for e in events if e["action"] == "replied_sent"]
    assert len(sent_events) == 1
    assert sent_events[0]["actor_id"] == REVIEWER
    assert "demo mode" in (sent_events[0]["detail"] or "")
    assert "No external message was transmitted" in (
        sent_events[0]["detail"] or ""
    )
    assert [e["action"] for e in events].count("status_changed") == 1


def test_resolved_ticket_status_is_not_changed_by_demo_send(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    approved = _approved(auth_client, "TF-1036")  # seeded resolved ticket
    before = ticket_row(session_factory, "TF-1036")
    assert before["status"] == "resolved"

    assert _send(auth_client, approved["id"]).status_code == 200
    after = ticket_row(session_factory, "TF-1036")
    assert after["status"] == "resolved"
    assert after["due_at"] == before["due_at"]
    actions = [
        event["action"]
        for event in activity_rows(session_factory, "TF-1036")
    ]
    assert actions[-4:] == [
        "replied_draft",
        "reply_submitted",
        "reply_approved",
        "replied_sent",
    ]
    assert "status_changed" not in actions


def test_modified_approved_version_cannot_be_sent(
    auth_client: TestClient, seeded: None
) -> None:
    approved = _approved(auth_client)
    use_account(auth_client, AUTHOR)
    edited = auth_client.patch(
        f"/api/v1/replies/{approved['id']}",
        json={"body": "Changed after approval."},
    )
    assert edited.status_code == 200
    assert edited.json()["state"] == "draft"

    rejected = _send(auth_client, approved["id"])
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "approval_required"


def test_missing_stored_approval_decision_blocks_sending(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    approved = _approved(auth_client)
    with session_factory() as session:
        reply = session.scalar(
            select(CustomerReply).where(
                CustomerReply.public_id == approved["id"]
            )
        )
        review = session.scalar(
            select(ReplyReview).where(ReplyReview.reply_id == reply.id)
        )
        session.delete(review)
        session.commit()

    rejected = _send(auth_client, approved["id"])
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "approval_required"
    assert "no stored approval decision" in rejected.json()["error"]["message"]


def test_tampered_body_without_revision_blocks_sending(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    """Even if workflow metadata still looks approved, text must match."""
    approved = _approved(auth_client)
    with session_factory() as session:
        reply = session.scalar(
            select(CustomerReply).where(
                CustomerReply.public_id == approved["id"]
            )
        )
        reply.body = "Silently swapped text that was never reviewed."
        session.commit()

    rejected = _send(auth_client, approved["id"])
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "approval_required"


def test_repeated_send_is_rejected_without_duplicate_audit(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    approved = _approved(auth_client)
    assert _send(auth_client, approved["id"]).status_code == 200

    before = activity_rows(session_factory, "TF-1050")
    repeated = _send(auth_client, approved["id"])
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "reply_already_sent"

    after = activity_rows(session_factory, "TF-1050")
    assert after == before
    assert [e["action"] for e in after].count("replied_sent") == 1


def test_seeded_approved_reply_can_be_demo_sent_and_seeded_sent_cannot(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    """Seed data carries a stored approval decision for its exact revision."""
    sent = _send(auth_client, "REP-103")
    assert sent.status_code == 200, sent.text
    assert sent.json()["reply"]["state"] == "sent"
    assert ticket_row(session_factory, "TF-1045")["status"] == "pending"

    already_sent = _send(auth_client, "REP-105")
    assert already_sent.status_code == 409
    assert already_sent.json()["error"]["code"] == "reply_already_sent"


def test_direct_service_bypass_is_rejected(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    """Calling the domain operation directly must apply the same gate."""
    draft = _draft(auth_client, "TF-1046", "Draft text.")

    with session_factory() as session:
        with pytest.raises(ApiError) as excinfo:
            reply_service.mark_sent_demo(
                session,
                draft["id"],
                ReplySendDemo(),
                principal=principal_for(session_factory, REVIEWER),
            )
    assert excinfo.value.status_code == 409
    assert excinfo.value.code == "approval_required"

    stored = auth_client.get(f"/api/v1/replies/{draft['id']}").json()
    assert stored["state"] == "draft"
    assert stored["sent_at"] is None


def test_demo_send_uses_no_external_messaging_client() -> None:
    """Static guard: the reply service imports no messaging/HTTP auth_client."""
    source = (
        Path(reply_service.__file__).read_text(encoding="utf-8").lower()
    )
    for forbidden in (
        "import requests",
        "import httpx",
        "import smtplib",
        "import aiosmtplib",
        "telegram",
        "twilio",
        "sendgrid",
        "resend",
        "boto3",
        "celery",
    ):
        assert forbidden not in source, forbidden


# ---------------------------------------------------------------------------
# Transactional rollback
# ---------------------------------------------------------------------------


def _boom(*args, **kwargs):
    raise RuntimeError("audit store unavailable")


def test_failed_audit_rolls_back_draft_creation(
    monkeypatch, session_factory, seeded: None, accounts: None
) -> None:
    monkeypatch.setattr(reply_service.activity_repo, "add_activity", _boom)

    with session_factory() as session:
        with pytest.raises(RuntimeError):
            reply_service.create_draft(
                session,
                "TF-1050",
                ReplyCreate(body="Rollback me."),
                principal=principal_for(session_factory, AUTHOR),
            )

    with session_factory() as session:
        from app.models.ticket import Ticket

        ticket = session.scalar(
            select(Ticket).where(Ticket.public_id == "TF-1050")
        )
        reply = session.scalar(
            select(CustomerReply).where(CustomerReply.ticket_id == ticket.id)
        )
        # No reply, revision or event survived the failure.
        total_replies = int(
            session.scalar(
                select(func.count()).select_from(CustomerReply)
            )
            or 0
        )
        total_revisions = int(
            session.scalar(
                select(func.count()).select_from(ReplyRevision)
            )
            or 0
        )
    assert reply is None
    assert total_replies == 5  # only the seeded replies
    assert total_revisions == 5  # only the seeded revisions


def test_failed_audit_rolls_back_revision(
    monkeypatch, auth_client: TestClient, session_factory, seeded: None
) -> None:
    reply = _draft(auth_client, "TF-1046", "Original body.")
    monkeypatch.setattr(reply_service.activity_repo, "add_activity", _boom)

    with session_factory() as session:
        with pytest.raises(RuntimeError):
            reply_service.update_reply(
                session,
                reply["id"],
                ReplyUpdate(body="New body."),
                principal=principal_for(session_factory, AUTHOR),
            )

    stored = auth_client.get(f"/api/v1/replies/{reply['id']}").json()
    assert stored["body"] == "Original body."
    assert stored["version"] == 1
    assert [item["body"] for item in stored["revisions"]] == ["Original body."]
    reply_events = [
        event
        for event in activity_rows(session_factory, "TF-1046")
        if event["reply_id"] == reply["id"]
    ]
    assert len(reply_events) == 1
    assert reply_events[0]["action"] == "replied_draft"


def test_failed_audit_rolls_back_approval(
    monkeypatch, session_factory, seeded: None, accounts: None
) -> None:
    # Build a pending reply through the service directly so the failure path is
    # exercised in the same session.
    with session_factory() as session:
        draft = reply_service.create_draft(
            session,
            "TF-1050",
            ReplyCreate(body="Approve me."),
            principal=principal_for(session_factory, AUTHOR),
        )
        pending = reply_service.submit_for_approval(
            session,
            draft.id,
            ReplySubmit(),
            principal=principal_for(session_factory, AUTHOR),
        )
        assert pending.state == "pending_approval"

        monkeypatch.setattr(
            reply_service.activity_repo, "add_activity", _boom
        )
        with pytest.raises(RuntimeError):
            reply_service.approve_reply(
                session,
                draft.id,
                ReplyApprove(version=1),
                principal=principal_for(session_factory, REVIEWER),
            )

    with session_factory() as session:
        stored = session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == draft.id)
        )
        assert stored.state is ReplyState.PENDING_APPROVAL
        assert stored.approved_version is None
        assert stored.reviewer_id is None
    assert _count(session_factory, ReplyReview) == 3  # seeded decisions only


def test_failed_audit_rolls_back_request_changes_and_send(
    monkeypatch, session_factory, seeded: None, accounts: None
) -> None:
    real_add_activity = reply_service.activity_repo.add_activity

    with session_factory() as session:
        draft = reply_service.create_draft(
            session,
            "TF-1050",
            ReplyCreate(body="Review me."),
            principal=principal_for(session_factory, AUTHOR),
        )
        reply_service.submit_for_approval(
            session,
            draft.id,
            ReplySubmit(),
            principal=principal_for(session_factory, AUTHOR),
        )

        monkeypatch.setattr(
            reply_service.activity_repo, "add_activity", _boom
        )
        with pytest.raises(RuntimeError):
            reply_service.request_changes(
                session,
                draft.id,
                ReplyRequestChanges(
                    version=1,
                    comment="Needs work.",
                ),
                principal=principal_for(session_factory, REVIEWER),
            )

    with session_factory() as session:
        stored = session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == draft.id)
        )
        assert stored.state is ReplyState.PENDING_APPROVAL
        assert stored.reviewer_feedback is None
        ticket = session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == draft.id)
        )
        assert ticket is not None
    assert _count(session_factory, ReplyReview) == 3

    # Restore the audit writer, approve for real, then make the demo-send audit
    # write fail in a second transaction.
    monkeypatch.setattr(
        reply_service.activity_repo, "add_activity", real_add_activity
    )
    with session_factory() as session:
        reply_service.approve_reply(
            session,
            draft.id,
            ReplyApprove(version=1),
            principal=principal_for(session_factory, REVIEWER),
        )
        monkeypatch.setattr(
            reply_service.activity_repo, "add_activity", _boom
        )
        with pytest.raises(RuntimeError):
            reply_service.mark_sent_demo(
                session,
                draft.id,
                ReplySendDemo(),
                principal=principal_for(session_factory, REVIEWER),
            )

    with session_factory() as session:
        stored = session.scalar(
            select(CustomerReply).where(CustomerReply.public_id == draft.id)
        )
        assert stored.state is ReplyState.APPROVED
        assert stored.sent_at is None
        assert stored.sent_by_actor_name is None
    assert ticket_row(session_factory, "TF-1050")["status"] == "new"
    assert not any(
        event["action"] == "replied_sent"
        for event in activity_rows(session_factory, "TF-1050")
    )
    assert _count(session_factory, ReplyReview) == 4


# ---------------------------------------------------------------------------
# Concurrency (real PostgreSQL row locks)
# ---------------------------------------------------------------------------


def test_two_simultaneous_sends_only_one_succeeds(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    approved = _approved(auth_client, "TF-1050")
    assert approved["state"] == "approved"

    barrier = threading.Barrier(2, timeout=15)
    outcomes: list[str] = []
    errors: list[BaseException] = []

    def attempt() -> None:
        try:
            with session_factory() as session:
                barrier.wait()
                try:
                    reply_service.mark_sent_demo(
                        session,
                        approved["id"],
                        ReplySendDemo(),
                        principal=principal_for(session_factory, REVIEWER),
                    )
                    outcomes.append("sent")
                except ApiError as exc:
                    outcomes.append(exc.code)
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, errors
    assert sorted(outcomes) == ["reply_already_sent", "sent"]

    ticket_events = activity_rows(session_factory, "TF-1050")
    sent_events = [
        event for event in ticket_events if event["action"] == "replied_sent"
    ]
    status_events = [
        event
        for event in ticket_events
        if event["action"] == "status_changed"
    ]
    assert len(sent_events) == 1
    assert len(status_events) == 1

    with session_factory() as session:
        reply = session.scalar(
            select(CustomerReply).where(
                CustomerReply.public_id == approved["id"]
            )
        )
    assert reply.state is ReplyState.SENT
    assert reply.sent_at is not None
