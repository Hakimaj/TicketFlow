"""Administrator account management: ``/api/v1/accounts``.

All requests go through the real API and PostgreSQL. Credentials are created
in the test body only — nothing secret is committed.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.models.auth import RefreshSession, UserAccount
from app.models.enums import AccountRole
from tests.conftest import (
    ADMIN_AGENT,
    AUTHOR_AGENT,
    REVIEWER_AGENT,
    use_account,
)

INITIAL_PASSWORD = "Provisioned!Passw0rd-2026"
NEXT_PASSWORD = "Replaced!Passw0rd-2027"
NEW_EMAIL = "provisioned@ticketflow.test"
SAFE_FIELDS = {
    "id",
    "email",
    "display_name",
    "role",
    "is_active",
    "must_change_password",
    "agent_id",
    "agent_name",
    "created_at",
    "updated_at",
}


def _create_account(client: TestClient, **overrides):
    payload = {
        "email": NEW_EMAIL,
        "display_name": "Provisioned Agent",
        "role": "agent",
        "agent_id": "AG-05",
        "password": INITIAL_PASSWORD,
    }
    payload.update(overrides)
    return client.post("/api/v1/accounts", json=payload)


def _auth_header(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Requested-With": "ticketflow",
    }


def _login(client: TestClient, email: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Requested-With": "ticketflow"},
    )


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("agent_id", [AUTHOR_AGENT, REVIEWER_AGENT])
def test_non_admin_roles_cannot_manage_accounts(
    auth_client: TestClient, seeded: None, agent_id: str
) -> None:
    use_account(auth_client, agent_id)
    me = auth_client.get("/api/v1/auth/me").json()

    listing = auth_client.get("/api/v1/accounts")
    assert listing.status_code == 403
    assert listing.json()["error"]["code"] == "forbidden"

    created = _create_account(auth_client)
    assert created.status_code == 403

    patched = auth_client.patch(
        f"/api/v1/accounts/{me['id']}", json={"display_name": "Renamed"}
    )
    assert patched.status_code == 403
    assert patched.json()["error"]["code"] == "forbidden"


def test_unauthenticated_account_management_is_rejected(
    client: TestClient, seeded: None
) -> None:
    assert client.get("/api/v1/accounts").status_code == 401
    assert _create_account(client).status_code == 401


# ---------------------------------------------------------------------------
# Listing and response shape
# ---------------------------------------------------------------------------


def test_admin_lists_accounts_without_credential_material(
    auth_client: TestClient, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)

    response = auth_client.get("/api/v1/accounts")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pagination"]["total"] >= 3
    assert {item["email"] for item in body["items"]} >= {
        "author@ticketflow.test",
        "reviewer@ticketflow.test",
        "admin@ticketflow.test",
    }
    for item in body["items"]:
        assert set(item) == SAFE_FIELDS
        assert item["role"] in {"agent", "reviewer", "admin"}
        assert isinstance(item["is_active"], bool)
        assert isinstance(item["must_change_password"], bool)

    serialized = response.text.lower()
    for secret in ("password_hash", "argon2", "token_hash", "refresh"):
        assert secret not in serialized


def test_account_filters_and_pagination(
    auth_client: TestClient, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)

    admins = auth_client.get("/api/v1/accounts", params={"role": "admin"}).json()
    assert admins["items"]
    assert all(item["role"] == "admin" for item in admins["items"])

    searched = auth_client.get(
        "/api/v1/accounts", params={"search": "reviewer@ticketflow.test"}
    ).json()
    assert [item["email"] for item in searched["items"]] == [
        "reviewer@ticketflow.test"
    ]

    active = auth_client.get(
        "/api/v1/accounts", params={"is_active": True, "page_size": 2}
    ).json()
    assert len(active["items"]) == 2
    assert active["pagination"]["page_size"] == 2
    assert active["pagination"]["total"] >= 3
    assert active["pagination"]["page_count"] >= 2


# ---------------------------------------------------------------------------
# Provisioning and the forced password change
# ---------------------------------------------------------------------------


def test_provisioned_account_must_change_its_password(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)
    created = _create_account(auth_client)

    assert created.status_code == 201, created.text
    body = created.json()
    assert set(body) == SAFE_FIELDS
    assert body["email"] == NEW_EMAIL
    assert body["role"] == "agent"
    assert body["agent_id"] == "AG-05"
    assert body["agent_name"] is not None
    assert body["is_active"] is True
    assert body["must_change_password"] is True
    assert INITIAL_PASSWORD not in created.text
    assert "password_hash" not in created.text.lower()

    # The password is hashed with Argon2id and never stored in clear text.
    with session_factory() as session:
        account = session.scalar(
            select(UserAccount).where(UserAccount.email == NEW_EMAIL)
        )
        assert account is not None
        assert account.password_hash.startswith("$argon2")
        assert INITIAL_PASSWORD not in account.password_hash
        assert account.must_change_password is True
        account_id = str(account.id)

    # Sign-in works, but operational endpoints are blocked until the password
    # is replaced.
    login = _login(auth_client, NEW_EMAIL, INITIAL_PASSWORD)
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert login.json()["user"]["must_change_password"] is True

    blocked = auth_client.get("/api/v1/tickets", headers=_auth_header(token))
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"

    # Profile read and password change remain available.
    profile = auth_client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert profile.status_code == 200

    wrong = auth_client.post(
        "/api/v1/auth/password",
        json={"current_password": "wrong-password", "new_password": NEXT_PASSWORD},
        headers=_auth_header(token),
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "invalid_current_password"

    unchanged = auth_client.post(
        "/api/v1/auth/password",
        json={
            "current_password": INITIAL_PASSWORD,
            "new_password": INITIAL_PASSWORD,
        },
        headers=_auth_header(token),
    )
    assert unchanged.status_code == 422
    assert unchanged.json()["error"]["code"] == "password_unchanged"

    changed = auth_client.post(
        "/api/v1/auth/password",
        json={"current_password": INITIAL_PASSWORD, "new_password": NEXT_PASSWORD},
        headers=_auth_header(token),
    )
    assert changed.status_code == 200, changed.text
    new_token = changed.json()["access_token"]
    assert changed.json()["user"]["must_change_password"] is False

    allowed = auth_client.get("/api/v1/tickets", headers=_auth_header(new_token))
    assert allowed.status_code == 200

    # The old password no longer works; the new one does.
    assert _login(auth_client, NEW_EMAIL, INITIAL_PASSWORD).status_code == 401
    relogin = _login(auth_client, NEW_EMAIL, NEXT_PASSWORD)
    assert relogin.status_code == 200
    assert relogin.json()["user"]["must_change_password"] is False

    # The account is now visible as ready in the admin list.
    listed = auth_client.get(
        "/api/v1/accounts", params={"search": NEW_EMAIL}
    ).json()["items"][0]
    assert listed["id"] == account_id
    assert listed["must_change_password"] is False


def test_password_change_revokes_other_refresh_sessions(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)
    _create_account(auth_client)
    first = _login(auth_client, NEW_EMAIL, INITIAL_PASSWORD)
    assert first.status_code == 200
    cookie_name = get_settings().refresh_cookie_name
    first_cookie = first.cookies.get(cookie_name)
    assert first_cookie

    changed = auth_client.post(
        "/api/v1/auth/password",
        json={"current_password": INITIAL_PASSWORD, "new_password": NEXT_PASSWORD},
        headers=_auth_header(first.json()["access_token"]),
    )
    assert changed.status_code == 200, changed.text

    # The pre-change refresh cookie is dead, so a stolen session cannot outlive
    # the password change.
    auth_client.cookies.clear()
    auth_client.cookies.set(cookie_name, first_cookie, path="/api/v1/auth")
    replay = auth_client.post(
        "/api/v1/auth/refresh",
        headers={"X-Requested-With": "ticketflow"},
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "refresh_invalid"


def test_duplicate_accounts_and_agent_links_are_rejected(
    auth_client: TestClient, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)

    duplicate = _create_account(auth_client, email="ADMIN@ticketflow.test")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "account_exists"

    taken_agent = _create_account(auth_client, agent_id="AG-01")
    assert taken_agent.status_code == 409
    assert taken_agent.json()["error"]["code"] == "agent_already_linked"

    unknown_agent = _create_account(auth_client, agent_id="AG-999")
    assert unknown_agent.status_code == 422
    assert unknown_agent.json()["error"]["code"] == "invalid_agent"

    short_password = _create_account(auth_client, password="short")
    assert short_password.status_code == 422
    assert short_password.json()["error"]["code"] == "validation_error"

    bad_role = _create_account(auth_client, role="owner")
    assert bad_role.status_code == 422


def test_client_cannot_set_role_permissions_or_inactive_flags(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)
    created = auth_client.post(
        "/api/v1/accounts",
        json={
            "email": NEW_EMAIL,
            "display_name": "Privilege Attempt",
            "role": "agent",
            "agent_id": "AG-05",
            "password": INITIAL_PASSWORD,
            "permissions": ["accounts:manage"],
            "is_superuser": True,
            "must_change_password": False,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["role"] == "agent"
    assert body["must_change_password"] is True

    with session_factory() as session:
        account = session.scalar(
            select(UserAccount).where(UserAccount.email == NEW_EMAIL)
        )
    assert account.role is AccountRole.AGENT
    assert account.must_change_password is True


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_deactivation_blocks_login_and_existing_sessions(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)
    created = _create_account(auth_client).json()

    login = _login(auth_client, NEW_EMAIL, INITIAL_PASSWORD)
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    cookie_name = get_settings().refresh_cookie_name
    refresh_cookie = login.cookies.get(cookie_name)
    assert refresh_cookie

    deactivated = auth_client.patch(
        f"/api/v1/accounts/{created['id']}", json={"is_active": False}
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False

    # No new access token, no session rotation, no use of the existing one.
    assert _login(auth_client, NEW_EMAIL, INITIAL_PASSWORD).status_code == 401
    auth_client.cookies.clear()
    auth_client.cookies.set(cookie_name, refresh_cookie, path="/api/v1/auth")
    rotated = auth_client.post(
        "/api/v1/auth/refresh",
        headers={"X-Requested-With": "ticketflow"},
    )
    assert rotated.status_code == 401
    assert rotated.json()["error"]["code"] == "refresh_invalid"
    stale = auth_client.get("/api/v1/tickets", headers=_auth_header(access_token))
    assert stale.status_code == 401
    assert stale.json()["error"]["code"] == "invalid_token"

    # The refresh session is revoked in the database, not just ignored.
    with session_factory() as session:
        sessions = session.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == uuid.UUID(created["id"])
            )
        ).all()
    assert sessions
    assert all(row.revoked_at is not None for row in sessions)

    # Reactivation restores sign-in.
    reactivated = auth_client.patch(
        f"/api/v1/accounts/{created['id']}", json={"is_active": True}
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True
    assert _login(auth_client, NEW_EMAIL, INITIAL_PASSWORD).status_code == 200


def test_admin_cannot_change_their_own_role_or_activation(
    auth_client: TestClient, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)
    me = auth_client.get("/api/v1/auth/me").json()

    demote = auth_client.patch(
        f"/api/v1/accounts/{me['id']}", json={"role": "agent"}
    )
    assert demote.status_code == 403
    assert demote.json()["error"]["code"] == "self_management_forbidden"

    deactivate = auth_client.patch(
        f"/api/v1/accounts/{me['id']}", json={"is_active": False}
    )
    assert deactivate.status_code == 403

    # Non-privileged self service (display name) is still allowed.
    renamed = auth_client.patch(
        f"/api/v1/accounts/{me['id']}", json={"display_name": "Bereket S."}
    )
    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "Bereket S."
    assert renamed.json()["role"] == "admin"


def test_role_and_agent_link_updates(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)
    created = _create_account(auth_client).json()

    promoted = auth_client.patch(
        f"/api/v1/accounts/{created['id']}", json={"role": "reviewer"}
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "reviewer"

    relinked = auth_client.patch(
        f"/api/v1/accounts/{created['id']}", json={"agent_id": "AG-06"}
    )
    assert relinked.status_code == 200
    assert relinked.json()["agent_id"] == "AG-06"
    assert relinked.json()["agent_name"]

    unlinked = auth_client.patch(
        f"/api/v1/accounts/{created['id']}", json={"agent_id": None}
    )
    assert unlinked.status_code == 200
    assert unlinked.json()["agent_id"] is None
    assert unlinked.json()["agent_name"] is None

    taken = auth_client.patch(
        f"/api/v1/accounts/{created['id']}", json={"agent_id": "AG-01"}
    )
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "agent_already_linked"

    unknown = auth_client.patch(
        f"/api/v1/accounts/{created['id']}", json={"agent_id": "AG-999"}
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "invalid_agent"

    with session_factory() as session:
        account = session.get(UserAccount, uuid.UUID(created["id"]))
    assert account is not None
    assert account.role is AccountRole.REVIEWER
    assert account.agent_id is None


def test_role_change_applies_to_existing_sessions(
    auth_client: TestClient, session_factory, seeded: None
) -> None:
    """Authorization is read from persisted rows, not from the access token."""
    use_account(auth_client, AUTHOR_AGENT)
    agent_me = auth_client.get("/api/v1/auth/me").json()
    assert agent_me["role"] == "agent"
    assert "replies:review" not in agent_me["permissions"]

    use_account(auth_client, ADMIN_AGENT)
    promoted = auth_client.patch(
        f"/api/v1/accounts/{agent_me['id']}", json={"role": "reviewer"}
    )
    assert promoted.status_code == 200

    # Same access token as before the promotion: the role and its permissions
    # are re-derived from PostgreSQL on every request, not from token claims.
    use_account(auth_client, AUTHOR_AGENT)
    refreshed = auth_client.get("/api/v1/auth/me").json()
    assert refreshed["role"] == "reviewer"
    assert "replies:review" in refreshed["permissions"]


def test_empty_update_and_unknown_account_are_rejected(
    auth_client: TestClient, seeded: None
) -> None:
    use_account(auth_client, ADMIN_AGENT)
    me = auth_client.get("/api/v1/auth/me").json()

    empty = auth_client.patch(f"/api/v1/accounts/{me['id']}", json={})
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "empty_update"

    missing = auth_client.patch(
        f"/api/v1/accounts/{uuid.uuid4()}", json={"display_name": "Nobody"}
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "account_not_found"
