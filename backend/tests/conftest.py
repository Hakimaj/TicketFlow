"""Test fixtures.

These tests run against a **real PostgreSQL** instance (Docker Compose) in a
dedicated ``*_test`` database created and migrated from scratch for the test
session. Nothing touches the development database.

Start the database first::

    docker compose up -d db
"""

from __future__ import annotations

import os
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
TEST_DATABASE_URL: URL = _base_url.set(database=TEST_DATABASE_NAME)

# Every app module reads the URL through Settings; point it at the test DB
# before the application or Alembic is imported anywhere else.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(hide_password=False)
os.environ["APP_ENV"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://127.0.0.1:5173"
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
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
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
        connection.execute(
            text(
                "TRUNCATE TABLE ticket_activities, ticket_notes, "
                "customer_replies, tickets, requesters, agents "
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



@pytest.fixture()
def db_session(session_factory, clean_db) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
