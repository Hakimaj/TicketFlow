"""Health endpoint contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LivenessResponse(BaseModel):
    """Process is up. Says nothing about database availability."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "TicketFlow API",
                "version": "0.1.0",
            }
        }
    )

    status: Literal["ok"]
    service: str
    version: str


class ReadinessChecks(BaseModel):
    database: Literal["ok", "unavailable"] = Field(
        description="Result of a lightweight `SELECT 1` against PostgreSQL."
    )


class ReadinessResponse(BaseModel):
    """Dependency readiness. `503` is returned when the database is unusable."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"status": "ready", "checks": {"database": "ok"}}
        }
    )

    status: Literal["ready", "unavailable"]
    checks: ReadinessChecks
