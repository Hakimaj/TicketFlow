"""Exception handlers producing one predictable JSON error envelope.

Rules:
- expected failures raise :class:`ApiError`;
- validation failures list field-level messages but never echo model input;
- database failures become ``503`` with a generic message (only the exception
  class is logged, never SQL parameters or exception text);
- unexpected failures become ``500`` without a traceback or SQL in the body.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ApiError

logger = logging.getLogger("ticketflow.api")

_DEFAULT_MESSAGES = {
    400: "The request could not be processed.",
    404: "The requested resource was not found.",
    405: "That HTTP method is not allowed for this endpoint.",
    409: "The request conflicts with the current state.",
    422: "Request validation failed.",
}


def _envelope(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body, headers=headers)


_LOCATION_PREFIXES = ("query", "path", "body", "header", "cookie")


def _field_from_loc(loc: tuple[Any, ...]) -> str:
    """Map a Pydantic error location to the offending field name.

    Only the leading location marker is removed. A field that is itself
    named ``body`` (the reply contract) must keep that name in the details.
    """
    parts = [str(part) for part in loc]
    if parts and parts[0] in _LOCATION_PREFIXES:
        parts = parts[1:]
    return ".".join(parts) or "request"


async def _api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return _envelope(
        exc.status_code,
        exc.code,
        exc.message,
        exc.details,
        exc.headers,
    )


async def _validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "field": _field_from_loc(error.get("loc", ())),
            "message": str(error.get("msg", "Invalid value.")),
        }
        for error in exc.errors()
    ]
    return _envelope(
        422, "validation_error", "Request validation failed.", details
    )


async def _http_exception_handler(
    _: Request, exc: StarletteHTTPException
) -> JSONResponse:
    # Route-level HTTPException details are developer-authored strings; prefer
    # a stable generic message for unexpected statuses.
    if exc.status_code == 404:
        code, message = "not_found", "The requested resource was not found."
    elif exc.status_code == 405:
        code, message = "method_not_allowed", _DEFAULT_MESSAGES[405]
    else:
        code = "http_error"
        message = _DEFAULT_MESSAGES.get(
            exc.status_code, "The request could not be processed."
        )
    return _envelope(exc.status_code, code, message)


async def _operational_error_handler(
    _: Request, exc: OperationalError
) -> JSONResponse:
    logger.error("Database operation failed: %s", type(exc).__name__)
    return _envelope(
        503,
        "database_unavailable",
        "The database is currently unavailable. Please retry shortly.",
    )


async def _sqlalchemy_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    # Do not log the exception text: SQLAlchemy can include statement
    # parameters such as note bodies or credential hashes.
    logger.error("Unhandled database error (%s)", type(exc).__name__)
    return _envelope(
        500, "internal_error", "An unexpected server error occurred."
    )


async def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    # Same rule for unexpected errors: log only the exception class, never its
    # message or a traceback that could embed request data.
    logger.error("Unhandled server error (%s)", type(exc).__name__)
    return _envelope(
        500, "internal_error", "An unexpected server error occurred."
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(OperationalError, _operational_error_handler)
    app.add_exception_handler(SQLAlchemyError, _sqlalchemy_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
