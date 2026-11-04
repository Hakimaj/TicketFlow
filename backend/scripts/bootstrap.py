"""Create the first administrator (and optional demo accounts) safely.

Usage (from ``backend/``)::

    python -m scripts.bootstrap

Credentials are **never** committed. They come from the environment:

- ``BOOTSTRAP_ADMIN_EMAIL`` / ``BOOTSTRAP_ADMIN_PASSWORD`` create the first
  administrator. The password must be at least 12 characters.
- ``DEMO_ACCOUNTS_ENABLED=true`` additionally creates the local development
  accounts (agent / reviewer / admin) linked to seeded agents, using
  ``DEMO_ACCOUNT_PASSWORD``. Demo accounts are refused outside
  ``APP_ENV=development``.

The command is idempotent: an existing account is reported as skipped and its
password is **never** overwritten. A linked agent must already exist. Nothing
secret (password, hash, token) is printed.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import MIN_PASSWORD_LENGTH
from app.db.session import build_engine, build_session_factory, session_scope
from app.models.agent import Agent
from app.models.auth import UserAccount
from app.models.enums import AccountRole
from app.services.auth import create_account

DEMO_ACCOUNTS: list[dict[str, str]] = [
    {
        "email": "agent@ticketflow.local",
        "display_name": "Dawit Mengistu",
        "role": AccountRole.AGENT,
        "agent_id": "AG-03",
    },
    {
        "email": "reviewer@ticketflow.local",
        "display_name": "Abebe Kebede",
        "role": AccountRole.REVIEWER,
        "agent_id": "AG-01",
    },
    {
        "email": "admin@ticketflow.local",
        "display_name": "Bereket Solomon",
        "role": AccountRole.ADMIN,
        "agent_id": "AG-08",
    },
]



@dataclass
class BootstrapReport:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {"created": self.created, "skipped": self.skipped}


def _existing_emails(session: Session) -> set[str]:
    return {email.lower() for email in session.scalars(select(UserAccount.email))}


def _require_agent(session: Session, agent_id: str | None) -> Agent | None:
    if agent_id is None:
        return None
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise SystemExit(
            f"Agent {agent_id} does not exist. Run `python -m scripts.seed` "
            "first so accounts can be linked to real agents."
        )
    return agent


def _ensure_account(
    session: Session,
    *,
    report: BootstrapReport,
    email: str,
    password: str,
    display_name: str,
    role: AccountRole,
    agent_id: str | None,
) -> None:
    normalized = email.strip().lower()
    if normalized in _existing_emails(session):
        report.skipped.append(normalized)
        return
    _require_agent(session, agent_id)
    create_account(
        session,
        email=normalized,
        password=password,
        display_name=display_name,
        role=role,
        agent_id=agent_id,
    )
    session.flush()
    report.created.append(normalized)


def _validated_password(value: str | None, *, label: str) -> str:
    if not value:
        raise SystemExit(f"{label} is required.")
    if len(value) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"{label} must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    return value


def run(session: Session) -> BootstrapReport:
    settings = get_settings()
    report = BootstrapReport()

    admin_email = settings.bootstrap_admin_email
    admin_password = settings.bootstrap_admin_password
    if admin_email or admin_password:
        if not (admin_email and admin_password):
            raise SystemExit(
                "Set both BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD."
            )
        if (
            settings.app_env == "production"
            and os.getenv("ALLOW_BOOTSTRAP_ADMIN") != "true"
        ):
            raise SystemExit(
                "Refusing to create an administrator in production without "
                "ALLOW_BOOTSTRAP_ADMIN=true."
            )
        _ensure_account(
            session,
            report=report,
            email=admin_email,
            password=_validated_password(
                admin_password, label="BOOTSTRAP_ADMIN_PASSWORD"
            ),
            display_name="TicketFlow Administrator",
            role=AccountRole.ADMIN,
            agent_id=None,
        )

    if settings.demo_accounts_enabled:
        if settings.app_env != "development":
            raise SystemExit(
                "DEMO_ACCOUNTS_ENABLED is only allowed with APP_ENV=development."
            )
        password = _validated_password(
            os.getenv("DEMO_ACCOUNT_PASSWORD"), label="DEMO_ACCOUNT_PASSWORD"
        )
        for spec in DEMO_ACCOUNTS:
            _ensure_account(
                session,
                report=report,
                email=spec["email"],
                password=password,
                display_name=spec["display_name"],
                role=spec["role"],
                agent_id=spec["agent_id"],
            )

    if not report.created and not report.skipped:
        raise SystemExit(
            "Nothing to do. Provide BOOTSTRAP_ADMIN_EMAIL/BOOTSTRAP_ADMIN_PASSWORD "
            "or set DEMO_ACCOUNTS_ENABLED=true."
        )
    return report


def main() -> int:
    settings = get_settings()
    engine = build_engine(settings)
    factory = build_session_factory(engine)
    try:
        with session_scope(factory) as session:
            report = run(session)
    finally:
        engine.dispose()
    print(json.dumps(report.as_dict(), indent=2))
    print(
        f"Bootstrap complete: {len(report.created)} account(s) created, "
        f"{len(report.skipped)} existing account(s) left unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
