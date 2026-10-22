"""Typed API error primitives.

Routes raise :class:`ApiError`; the exception handlers in
``app.api.errors`` turn it into a predictable JSON envelope without leaking
SQL, stack traces or credentials.
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """An expected, client-safe API failure."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def not_found(code: str, message: str) -> ApiError:
    return ApiError(status_code=404, code=code, message=message)


def service_unavailable(code: str, message: str) -> ApiError:
    return ApiError(status_code=503, code=code, message=message)
