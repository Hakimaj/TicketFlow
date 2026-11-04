"""Prepare an isolated PostgreSQL database for API-mode end-to-end tests.

Usage (from ``backend/``)::

    E2E_ACCOUNT_PASSWORD=... python -m scripts.e2e_prepare

The script drops and recreates ``ticketflow_e2e`` (never the development or
test database), migrates it to ``head`` with Alembic, seeds the demonstration
dataset and creates one account per role. The password comes from
``E2E_ACCOUNT_PASSWORD``; nothing secret is printed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_E2E_URL = (
    "postgresql+psycopg://ticketflow:ticketflow_local_dev_only"
    "@127.0.0.1:5432/ticketflow_e2e"
)

E2E_ACCOUNTS: list[dict[str, str]] = [
    {
        "email": "e2e-agent@ticketflow.test",
        "display_name": "Dawit Mengistu",
        "role": "agent",
        "agent_id": "AG-03",
    },
    {
        "email": "e2e-reviewer@ticketflow.test",
        "display_name": "Abebe Kebede",
        "role": "reviewer",
        "agent_id": "AG-01",
    },
    {
        "email": "e2e-admin@ticketflow.test",
        "display_name": "Bereket Solomon",
        "role": "admin",
        "agent_id": "AG-08",
    },
]

MIN_PASSWORD_LENGTH = 12


def _recreate_database(url: str) -> None:
    db_url = make_url(url)
    database = db_url.database or "ticketflow_e2e"
    if not re.fullmatch(r"[A-Za-z0-9_]+_e2e", database):
        raise SystemExit(
            f"Refusing to recreate database {database!r}: the name must match "
            "[A-Za-z0-9_]+_e2e so the development database cannot be dropped."
        )

    admin_engine = create_engine(
        db_url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},
    )
    with admin_engine.connect() as connection:
        connection.execute(
            text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
        )
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    admin_engine.dispose()


def _migrate(url: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "Alembic upgrade failed for the e2e database:\n"
            f"{result.stdout}\n{result.stderr}"
        )


def main() -> int:
    url = os.environ.get("E2E_DATABASE_URL", DEFAULT_E2E_URL).strip()
    password = os.environ.get("E2E_ACCOUNT_PASSWORD", "")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"E2E_ACCOUNT_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    # Settings read DATABASE_URL from the environment, which takes precedence
    # over backend/.env. Set it before importing any application module.
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("DEMO_ACCOUNTS_ENABLED", "false")

    _recreate_database(url)
    _migrate(url)

    from app.core.config import get_settings
    from app.db.session import build_engine, build_session_factory, session_scope
    from app.models.auth import UserAccount
    from app.models.enums import AccountRole
    from app.seed import seed_demo_data
    from app.services.auth import create_account

    get_settings.cache_clear()
    settings = get_settings()
    engine = build_engine(settings)
    factory = build_session_factory(engine)
    try:
        with session_scope(factory) as session:
            seed_demo_data(session)
            existing = {
                email
                for email in session.scalars(select(UserAccount.email))
            }
            created: list[str] = []
            for spec in E2E_ACCOUNTS:
                if spec["email"] in existing:
                    continue
                create_account(
                    session,
                    email=spec["email"],
                    password=password,
                    display_name=spec["display_name"],
                    role=AccountRole(spec["role"]),
                    agent_id=spec["agent_id"],
                )
                created.append(spec["email"])
    finally:
        engine.dispose()

    print(
        json.dumps(
            {
                "database": make_url(url).database,
                "accounts_created": created,
                "accounts_total": len(E2E_ACCOUNTS),
                "migrated": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
