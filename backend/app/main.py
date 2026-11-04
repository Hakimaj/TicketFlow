"""TicketFlow API application factory.

Run locally with::

    uvicorn app.main:app --reload --port 8000

The engine is created in the lifespan hook, so importing the app never opens a
database connection and `/health/live` still answers when PostgreSQL is down.
No tables are created at startup: schema changes go through Alembic.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_current_account, get_password_current_account
from app.api.errors import register_exception_handlers
from app.api.routes import (
    accounts,
    activities,
    agents,
    auth,
    dashboard,
    health,
    notes,
    replies,
    tickets,
)
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_session_factory

logger = logging.getLogger("ticketflow.app")

DESCRIPTION = """
Support-operations API for TicketFlow.

Phase 8 adds authenticated accounts, role-based authorization, trusted audit
attribution and self-approval prevention on top of the persistent ticket,
reply, note, activity, agent and dashboard APIs. Phase 10 adds staff ticket
intake, administrator account provisioning and optimistic concurrency on
ticket triage (`expected_version`).

All operational endpoints require a Bearer access token; only health probes and
the authentication endpoints are public. Access tokens are short-lived and held
in frontend memory, while refresh tokens rotate in an HttpOnly cookie and are
stored only as hashes.

Demo sending records a simulated action only. No email, SMS or other message is
ever delivered.

Every error response uses the same envelope: `{"error": {"code", "message"}}`,
with optional `details` for validation failures.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(app_settings)
        app.state.settings = app_settings
        app.state.engine = engine
        app.state.session_factory = build_session_factory(engine)
        logger.info(
            "TicketFlow API starting (env=%s, version=%s)",
            app_settings.app_env,
            app_settings.app_version,
        )
        try:
            yield
        finally:
            engine.dispose()
            logger.info("TicketFlow API stopped")

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_url=f"{app_settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {
                "name": "health",
                "description": "Liveness and database readiness probes.",
            },
            {
                "name": "tickets",
                "description": "Ticket queues, detail and triage mutations.",
            },
            {
                "name": "notes",
                "description": "Staff-only internal notes (not customer replies).",
            },
            {
                "name": "activities",
                "description": "Ticket-specific and global audit history.",
            },
            {
                "name": "agents",
                "description": "Operational agent roster for assignment controls.",
            },
            {
                "name": "auth",
                "description": (
                    "Sign-in, refresh rotation, logout and current-account "
                    "identity. Access tokens are short-lived."
                ),
            },
            {
                "name": "replies",
                "description": (
                    "Persistent customer reply drafts, revisions, human "
                    "approval and demo sending (no real delivery)."
                ),
            },
            {
                "name": "dashboard",
                "description": (
                    "SQL-derived ticket and reply-workflow summary metrics."
                ),
            },
            {
                "name": "accounts",
                "description": (
                    "Administrator-only account provisioning and lifecycle "
                    "(no credential material is ever returned)."
                ),
            },
        ],
    )
    # The app state must be readable in the window before lifespan runs
    # (e.g. ASGI inspection in tests), so set a safe default here too.
    app.state.settings = app_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "HEAD", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
        ],
        max_age=600,
    )

    register_exception_handlers(app)

    app.include_router(health.router, prefix=app_settings.api_v1_prefix)
    app.include_router(auth.router, prefix=app_settings.api_v1_prefix)

    # Every operational router requires a verified account whose password is
    # no longer the administrator-issued initial one. Authorization is enforced
    # separately per operation (roles/permissions), not just here.
    authenticated = [
        Depends(get_current_account),
        Depends(get_password_current_account),
    ]
    for router in (
        tickets.router,
        notes.router,
        replies.ticket_router,
        # Fixed `/replies/approvals` must be registered before the dynamic
        # `/replies/{reply_id}` router.
        replies.approvals_router,
        replies.reply_router,
        activities.ticket_router,
        activities.global_router,
        agents.router,
        dashboard.router,
        accounts.router,
    ):
        app.include_router(
            router,
            prefix=app_settings.api_v1_prefix,
            dependencies=authenticated,
        )
    return app


app = create_app()
