"""Shared response envelopes and serialization helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def serialize_utc_datetime(value: datetime) -> str:
    """Serialize as ISO 8601 UTC with a trailing ``Z``.

    Matches the frontend fixtures (`Date.prototype.toISOString`) so
    ``new Date(value)`` parses identically once the app switches to the API.
    Naive values are treated as UTC, never as local time.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


UtcDatetime = Annotated[
    datetime,
    PlainSerializer(serialize_utc_datetime, return_type=str, when_used="json"),
]


class ErrorDetail(BaseModel):
    field: str = Field(description="Offending query/path/body field, when known.")
    message: str


class ErrorBody(BaseModel):
    code: str = Field(description="Stable, machine-readable error code.")
    message: str = Field(description="Client-safe human-readable message.")
    details: list[ErrorDetail] | None = Field(
        default=None,
        description="Field-level validation details; omitted for non-validation errors.",
    )


class ErrorResponse(BaseModel):
    """Every non-2xx response uses this envelope."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "ticket_not_found",
                    "message": "Ticket TF-9999 was not found.",
                }
            }
        }
    )

    error: ErrorBody


class PageMeta(BaseModel):
    page: int = Field(ge=1, description="1-based page number.")
    page_size: int = Field(ge=1, description="Items requested per page.")
    total: int = Field(ge=0, description="Total matching records.")
    page_count: int = Field(ge=0, description="Total pages for this query.")
