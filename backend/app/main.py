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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import activities, agents, dashboard, health, notes, tickets
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_session_factory

logger = logging.getLogger("ticketflow.app")

DESCRIPTION = """
Support-operations API for TicketFlow.

Phase 6 adds persistent triage mutations, internal notes, activity history,
agent lookup and ticket dashboard aggregates on top of the Phase 5 PostgreSQL
foundation. The customer reply workflow, analytics and authentication are
**not** implemented and are not exposed here.

There is no authentication yet: write endpoints are intended for local
development only and must not be exposed publicly. `actor_id` fields are
development metadata, not verified identities.

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
                "name": "dashboard",
                "description": "SQL-derived ticket summary metrics.",
            },
        ],
    )
    # The app state must be readable in the window before lifespan runs
    # (e.g. ASGI inspection in tests), so set a safe default here too.
    app.state.settings = app_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "HEAD", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
        max_age=600,
    )

    register_exception_handlers(app)

    app.include_router(health.router, prefix=app_settings.api_v1_prefix)
    app.include_router(tickets.router, prefix=app_settings.api_v1_prefix)
    app.include_router(notes.router, prefix=app_settings.api_v1_prefix)
    app.include_router(activities.ticket_router, prefix=app_settings.api_v1_prefix)
    app.include_router(activities.global_router, prefix=app_settings.api_v1_prefix)
    app.include_router(agents.router, prefix=app_settings.api_v1_prefix)
    app.include_router(dashboard.router, prefix=app_settings.api_v1_prefix)
    return app


app = create_app()
