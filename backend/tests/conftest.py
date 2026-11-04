"""Test fixtures.

These tests run against a **real PostgreSQL** instance (Docker Compose) in a
dedicated ``*_test`` database created and migrated from scratch for the test
session. Nothing touches the development database.

Start the database first::

    docker compose up -d db
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

# Importing Settings reads backend/.env if present; do it before overriding env.
from app.core.config import Settings, get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Fixed anchor keeps seeded timestamps deterministic across runs.
FIXED_ANCHOR = datetime(2026, 10, 21, 12, 0, 0, tzinfo=UTC)

_base_settings = Settings()
_base_url = make_url(_base_settings.database_url)
TEST_DATABASE_NAME = os.environ.get(
    "TEST_DATABASE_NAME", f"{_base_url.database or 'ticketflow'}_test"
)
# The fixture drops this database. Refuse any name that could be a real
# development/production database or inject SQL through the identifier.
if not re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DATABASE_NAME):
    raise RuntimeError(
        "Refusing to use unsafe test database name "
        f"{TEST_DATABASE_NAME!r}: it must match [A-Za-z0-9_]+_test."
    )
TEST_DATABASE_URL: URL = _base_url.set(database=TEST_DATABASE_NAME)

# Every app module reads the URL through Settings; point it at the test DB
# before the application or Alembic is imported anywhere else.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(hide_password=False)
os.environ["APP_ENV"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://127.0.0.1:5173"
# Deterministic, test-only signing secret (never a production value).
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-production-0000"
os.environ["DEMO_ACCOUNTS_ENABLED"] = "false"
get_settings.cache_clear()

from app.core.config import get_settings as _get_settings  # noqa: E402
from app.db.session import build_engine, build_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="session")
def _database() -> Iterator[URL]:
    """Create a clean test database and migrate it with Alembic."""
    admin_url = _base_url.set(database="postgres")
    admin_engine = create_engine(
        admin_url,
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},
    )
    with admin_engine.connect() as connection:
        connection.execute(
            text(f'DROP DATABASE IF EXISTS "{TEST_DATABASE_NAME}" WITH (FORCE)')
        )
        connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))
    admin_engine.dispose()

    result = _run_alembic("upgrade", "head")
    if result.returncode != 0:
        raise RuntimeError(
            "Alembic upgrade failed for the test database:\n"
            f"{result.stdout}\n{result.stderr}"
        )

    yield TEST_DATABASE_URL


@pytest.fixture(scope="session")
def db_engine(_database: URL):
    engine = build_engine(_get_settings())
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def session_factory(db_engine) -> sessionmaker[Session]:
    return build_session_factory(db_engine)


@pytest.fixture(scope="session")
def app(_database: URL):
    return create_app(_get_settings())


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_db(db_engine) -> None:
    """Empty every table before a test that must not see leftover rows."""
    with db_engine.begin() as connection:
        # Truncate cascades wait on locks held by other pooled app sessions;
        # give the maintenance statement room beyond the engine-wide 10s
        # statement timeout (this SET is transaction-local and self-lifted).
        connection.execute(text("SET LOCAL statement_timeout = 60000"))
        connection.execute(
            text(
                "TRUNCATE TABLE refresh_sessions, user_accounts, "
                "ticket_activities, ticket_notes, customer_replies, "
                "tickets, requesters, agents "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture()
def seeded(clean_db, session_factory) -> None:
    """Clean database + the demonstration fixtures at a fixed timestamp."""
    from app.seed import seed_demo_data

    with session_factory() as session:
        seed_demo_data(session, anchor=FIXED_ANCHOR)
        session.commit()



# ---------------------------------------------------------------------------
# Authenticated API fixtures
# ---------------------------------------------------------------------------

TEST_PASSWORD = "TicketflowTest!123"

# agent id -> (email, display name, account role)
ACCOUNT_SPECS: dict[str, tuple[str, str, str]] = {
    "AG-03": ("author@ticketflow.test", "Dawit Mengistu", "agent"),
    "AG-01": ("reviewer@ticketflow.test", "Abebe Kebede", "reviewer"),
    "AG-08": ("admin@ticketflow.test", "Bereket Solomon", "admin"),
}

AUTHOR_AGENT = "AG-03"
REVIEWER_AGENT = "AG-01"
ADMIN_AGENT = "AG-08"


def api_login(
    client, email: str, password: str = TEST_PASSWORD
) -> str:
    """Log in through the real endpoint and return the access token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Requested-With": "ticketflow"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def use_account(client, agent_id: str) -> None:
    """Switch the shared test client to another account's access token."""
    client.headers["Authorization"] = (
        f"Bearer {client.ticketflow_tokens[agent_id]}"
    )


def principal_for(session_factory, agent_id: str):
    """Verified Principal for direct service-layer tests."""
    from sqlalchemy import select as _select

    from app.models.auth import UserAccount
    from app.services.auth import Principal

    with session_factory() as session:
        account = session.scalar(
            _select(UserAccount).where(UserAccount.agent_id == agent_id)
        )
        assert account is not None, agent_id
        return Principal(account_id=account.id, agent=account.agent)


def _create_test_accounts(session_factory) -> None:
    """Idempotently create one account per seed agent."""
    from sqlalchemy import select as _select

    from app.models.auth import UserAccount
    from app.models.enums import AccountRole
    from app.services.auth import create_account

    with session_factory() as session:
        for agent_id, (email, display_name, role) in ACCOUNT_SPECS.items():
            existing = session.scalar(
                _select(UserAccount).where(UserAccount.agent_id == agent_id)
            )
            if existing is not None:
                continue
            create_account(
                session,
                email=email,
                password=TEST_PASSWORD,
                display_name=display_name,
                role=AccountRole(role),
                agent_id=agent_id,
            )
        session.commit()


@pytest.fixture()
def accounts(seeded: None, session_factory) -> None:
    """Test accounts for direct service-layer tests that need a Principal."""
    _create_test_accounts(session_factory)


@pytest.fixture()
def auth_client(accounts: None, client):
    """Seeded database plus authenticated accounts for every agent role.

    The client defaults to the reviewer account (``AG-01``) so existing
    attribution expectations stay stable. Helpers switch tokens with
    ``use_account`` when a test needs a different actor.
    """
    tokens = {
        agent_id: api_login(client, spec[0])
        for agent_id, spec in ACCOUNT_SPECS.items()
    }
    client.ticketflow_tokens = tokens
    client.cookies.clear()
    use_account(client, REVIEWER_AGENT)
    try:
        yield client
    finally:
        client.headers.pop("Authorization", None)
        del client.ticketflow_tokens


@pytest.fixture()
def db_session(session_factory, clean_db) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
