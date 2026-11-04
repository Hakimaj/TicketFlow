"""Authentication: sign-in, refresh rotation, logout and token validation.

Everything runs against the real PostgreSQL test database through the HTTP API.
No test inspects or asserts on password/token material beyond the presence of a
generic error, so a regression that leaks secrets fails the suite.
"""

from __future__ import annotations

import threading
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import create_access_token
from app.models.auth import RefreshSession, UserAccount
from app.models.common import utcnow
from app.models.enums import AccountRole
from app.services import auth as auth_service
from tests.conftest import (
    ACCOUNT_SPECS,
    AUTHOR_AGENT,
    REVIEWER_AGENT,
    TEST_PASSWORD,
    api_login,
)

CSRF_HEADERS = {"X-Requested-With": "ticketflow"}


def _login(client: TestClient, agent_id: str = REVIEWER_AGENT):
    email = ACCOUNT_SPECS[agent_id][0]
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
        headers=CSRF_HEADERS,
    )


def _refresh(client: TestClient, token: str | None = None):
    """Refresh with the client's cookie, or an explicit (possibly old) one."""
    headers = dict(CSRF_HEADERS)
    if token is not None:
        headers["Cookie"] = f"{get_settings().refresh_cookie_name}={token}"
    return client.post("/api/v1/auth/refresh", headers=headers)


def test_login_returns_access_token_and_profile(
    client: TestClient, accounts: None
) -> None:
    response = _login(client)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0
    assert body["user"]["email"] == ACCOUNT_SPECS[REVIEWER_AGENT][0]
    assert body["user"]["role"] == "reviewer"
    assert "replies:review" in body["user"]["permissions"]

    # No credential material is echoed in any form. `must_change_password` is a
    # boolean state flag, so the check targets secret fields and values rather
    # than the word "password".
    serialized = response.text.lower()
    for forbidden in (
        "password_hash",
        """"password":""",
        "refresh_token",
        "token_hash",
    ):
        assert forbidden not in serialized

    assert response.headers.get("cache-control") == "no-store"
    cookie = response.headers.get("set-cookie", "")
    name = get_settings().refresh_cookie_name
    assert f"{name}=" in cookie
    assert "httponly" in cookie.lower()
    assert "path=/api/v1/auth" in cookie.lower()
    # The opaque token is bound to its session id for locked rotation/replay
    # detection; the id itself is not secret.
    assert "." in response.cookies.get(name, "")


def test_login_failures_are_generic(client: TestClient, accounts: None) -> None:
    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@ticketflow.test", "password": "wrong-password-123"},
        headers=CSRF_HEADERS,
    )
    bad_password = client.post(
        "/api/v1/auth/login",
        json={
            "email": ACCOUNT_SPECS[AUTHOR_AGENT][0],
            "password": "wrong-password-123",
        },
        headers=CSRF_HEADERS,
    )

    assert unknown.status_code == 401
    assert bad_password.status_code == 401
    assert unknown.json()["error"]["code"] == "invalid_credentials"
    assert bad_password.json()["error"] == unknown.json()["error"]


def test_login_requires_browser_marker(client: TestClient, accounts: None) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": ACCOUNT_SPECS[REVIEWER_AGENT][0],
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_rejected"


def test_inactive_account_cannot_sign_in(
    client: TestClient, accounts: None, session_factory
) -> None:
    with session_factory() as session:
        session.execute(
            update(UserAccount)
            .where(UserAccount.agent_id == AUTHOR_AGENT)
            .values(is_active=False)
        )
        session.commit()

    response = _login(client, AUTHOR_AGENT)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_protected_endpoints_require_a_valid_token(
    client: TestClient, seeded: None
) -> None:
    missing = client.get("/api/v1/tickets")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "not_authenticated"

    garbage = client.get(
        "/api/v1/tickets", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert garbage.status_code == 401
    assert garbage.json()["error"]["code"] == "invalid_token"


def test_expired_access_token_is_rejected(
    client: TestClient, accounts: None, session_factory
) -> None:
    with session_factory() as session:
        account = session.scalar(
            select(UserAccount).where(UserAccount.agent_id == AUTHOR_AGENT)
        )
        assert account is not None
        token, _ = create_access_token(
            account_id=account.id,
            role=account.role.value,
            now=utcnow() - timedelta(hours=2),
        )

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_refresh_rotates_and_replay_revokes_the_session_family(
    client: TestClient, accounts: None, session_factory
) -> None:
    login = _login(client)
    assert login.status_code == 200
    cookie_name = get_settings().refresh_cookie_name
    original = login.cookies.get(cookie_name)
    assert original

    rotated = _refresh(client)
    assert rotated.status_code == 200, rotated.text
    new_token = rotated.cookies.get(cookie_name)
    assert new_token and new_token != original

    # Replaying the superseded token is rejected, clears the browser cookie,
    # and revokes both the old and the newly rotated session.
    reused = _refresh(client, original)
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_invalid"
    assert "max-age=0" in reused.headers.get("set-cookie", "").lower()

    # The rotated token was part of the same compromised family.
    assert _refresh(client, new_token).status_code == 401

    with session_factory() as session:
        rows = session.scalars(select(RefreshSession)).all()
        assert rows
        assert all(row.revoked_at is not None for row in rows)


def test_concurrent_refresh_serializes_on_the_session_row(
    client: TestClient, accounts: None, session_factory
) -> None:
    login = _login(client)
    assert login.status_code == 200
    token = login.cookies.get(get_settings().refresh_cookie_name)
    assert token

    barrier = threading.Barrier(2)
    results: list[str] = []
    results_lock = threading.Lock()

    def worker() -> None:
        with session_factory() as session:
            barrier.wait(timeout=10)
            try:
                auth_service.rotate_refresh(session, token)
                outcome = "ok"
            except ApiError as exc:
                outcome = exc.code
            with results_lock:
                results.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
        assert not thread.is_alive()

    # Exactly one rotation may win. The loser is a replay, which revokes the
    # family, so no active session may remain afterward.
    assert sorted(results) == ["ok", "refresh_invalid"]
    with session_factory() as session:
        rows = session.scalars(select(RefreshSession)).all()
        assert rows
        assert all(row.revoked_at is not None for row in rows)


def test_logout_revokes_the_cookie_session(
    client: TestClient, accounts: None
) -> None:
    cookie_name = get_settings().refresh_cookie_name
    login = _login(client)
    assert login.status_code == 200
    token = login.cookies.get(cookie_name)
    assert token

    logout = client.post("/api/v1/auth/logout", headers=CSRF_HEADERS)
    assert logout.status_code == 200
    assert logout.json() == {"status": "ok"}
    assert "max-age=0" in logout.headers.get("set-cookie", "").lower()

    reused = _refresh(client, token)
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_invalid"


def test_logout_with_access_token_revokes_every_session(
    client: TestClient, accounts: None, session_factory
) -> None:
    cookie_name = get_settings().refresh_cookie_name
    first = _login(client)
    assert first.status_code == 200
    first_token = first.cookies.get(cookie_name)
    assert first_token

    second = _login(client)
    assert second.status_code == 200
    second_token = second.cookies.get(cookie_name)
    assert second_token and second_token != first_token

    logout = client.post(
        "/api/v1/auth/logout",
        headers={
            **CSRF_HEADERS,
            "Authorization": f"Bearer {second.json()['access_token']}",
        },
    )
    assert logout.status_code == 200

    # The access token is session-bound, so it is rejected immediately too.
    protected = client.get(
        "/api/v1/tickets",
        headers={"Authorization": f"Bearer {second.json()['access_token']}"},
    )
    assert protected.status_code == 401
    assert protected.json()["error"]["code"] == "invalid_token"

    # Both independently issued refresh sessions are dead.
    assert _refresh(client, first_token).status_code == 401
    assert _refresh(client, second_token).status_code == 401

    with session_factory() as session:
        sessions = session.scalars(select(RefreshSession)).all()
        assert len(sessions) >= 2
        assert all(row.revoked_at is not None for row in sessions)


def test_me_reads_the_role_from_the_database(
    client: TestClient, accounts: None, session_factory
) -> None:
    token = api_login(client, ACCOUNT_SPECS[AUTHOR_AGENT][0])

    with session_factory() as session:
        session.execute(
            update(UserAccount)
            .where(UserAccount.agent_id == AUTHOR_AGENT)
            .values(role=AccountRole.REVIEWER)
        )
        session.commit()

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "reviewer"
    assert "replies:review" in body["permissions"]


def test_failed_logins_are_rate_limited(client: TestClient) -> None:
    email = f"nobody-{uuid.uuid4().hex}@ticketflow.test"
    settings = get_settings()

    statuses = []
    for _ in range(settings.login_max_attempts):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "definitely-wrong-123"},
            headers=CSRF_HEADERS,
        )
        statuses.append(response.status_code)

    assert statuses == [401] * settings.login_max_attempts

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "definitely-wrong-123"},
        headers=CSRF_HEADERS,
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "too_many_attempts"
