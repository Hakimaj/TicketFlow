"""Shared model helpers: UTC timestamps and typed PostgreSQL enums."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_type(enum_cls: type[Enum], name: str) -> SAEnum:
    """Map a Python enum to a native PostgreSQL enum using its *values*.

    ``values_callable`` is essential: by default SQLAlchemy stores member
    *names* (``NEW``), which would not match the frontend contract (``new``).
    """
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
        native_enum=True,
    )


class TimestampMixin:
    """`created_at` / `updated_at` in UTC, with an automatic update hook."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )
