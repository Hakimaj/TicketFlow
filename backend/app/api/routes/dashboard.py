"""Ticket dashboard summary endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.authorization import CanReadOperations
from app.schemas.common import ErrorResponse
from app.schemas.dashboard import DashboardSummary
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    responses={
        500: {"model": ErrorResponse, "description": "Unexpected server error."},
        503: {"model": ErrorResponse, "description": "Database unavailable."},
    },
    dependencies=[CanReadOperations],
    summary="Ticket dashboard summary",
    description=(
        "Aggregates computed in SQL. Active means status `new`, `open` or "
        "`pending`; unassigned and urgent/high are restricted to active "
        "tickets. `needs_review_tickets` is the ticket-level status and stays "
        "separate from reply approvals. Reply counts are per logical reply, not "
        "per revision: `pending_reply_approvals`, `draft_replies`, "
        "`approved_replies_awaiting_send` and `sent_replies_demo`. The last "
        "one counts simulated demo sends, not customer deliveries. "
        "`generated_at` is the server request time."
    ),
)
def get_summary(
    db: DbSession,
    trend_days: Annotated[
        int | None,
        Query(
            ge=1,
            le=3650,
            description=(
                "Optional UTC-day trend window. When supplied, the response "
                "also includes `received_trend`, `priority_summary` and "
                "`agent_workload`, all derived from persisted timestamps. "
                "`resolved` is a proxy: terminal tickets are keyed by their "
                "last `updated_at`, not by an explicit resolution event."
            ),
        ),
    ] = None,
) -> DashboardSummary:
    return dashboard_service.get_summary(db, trend_days=trend_days)
