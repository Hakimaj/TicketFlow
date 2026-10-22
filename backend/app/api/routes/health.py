"""Liveness and readiness probes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response
from sqlalchemy import text

from app.schemas.health import LivenessResponse, ReadinessChecks, ReadinessResponse

logger = logging.getLogger("ticketflow.health")

router = APIRouter(tags=["health"])


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description=(
        "Returns 200 while the API process is running. Does not check the "
        "database; use `/health/ready` for dependency readiness."
    ),
)
def liveness(request: Request) -> LivenessResponse:
    settings = request.app.state.settings
    return LivenessResponse(
        status="ok", service=settings.app_name, version=settings.app_version
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        503: {
            "model": ReadinessResponse,
            "description": "The API cannot reach the configured database.",
        }
    },
    summary="Readiness probe",
    description=(
        "Runs a lightweight `SELECT 1` against PostgreSQL. Returns 503 when "
        "the database is unreachable, so a load balancer never routes traffic "
        "to an instance that cannot serve ticket data."
    ),
)
def readiness(request: Request, response: Response) -> ReadinessResponse:
    engine = getattr(request.app.state, "engine", None)
    try:
        if engine is None:
            raise RuntimeError("Database engine is not initialised.")
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        # Never surface driver messages, hostnames, credentials or SQL.
        logger.warning("Readiness check failed: database is not reachable.")
        response.status_code = 503
        return ReadinessResponse(
            status="unavailable",
            checks=ReadinessChecks(database="unavailable"),
        )
    return ReadinessResponse(status="ready", checks=ReadinessChecks(database="ok"))
