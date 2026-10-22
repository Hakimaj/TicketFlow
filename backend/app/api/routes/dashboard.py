"""Ticket dashboard summary endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
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
    summary="Ticket dashboard summary",
    description=(
        "Ticket-only aggregates computed in SQL. Active means status `new`, "
        "`open` or `pending`; unassigned and urgent/high are restricted to "
        "active tickets. `needs_review_tickets` is the ticket-level status and "
        "is unrelated to customer reply approvals, which are not exposed until "
        "the reply workflow API exists. `generated_at` is the server time of "
        "the request."
    ),
)
def get_summary(db: DbSession) -> DashboardSummary:
    return dashboard_service.get_summary(db)
