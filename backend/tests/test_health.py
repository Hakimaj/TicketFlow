"""Health probes, CORS behaviour, OpenAPI exposure and error envelopes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def test_liveness_returns_process_status(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "TicketFlow API",
        "version": "0.1.0",
    }
    assert "database" not in response.text.lower()


def test_readiness_ok_when_database_reachable(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_readiness_503_when_database_unreachable() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://ticketflow:secret-value@127.0.0.1:1/none",
        cors_origins="http://localhost:5173",
    )
    app = create_app(settings)
    with TestClient(app) as broken_client:
        response = broken_client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"database": "unavailable"},
    }
    body = response.text.lower()
    # No credentials, driver text, host details or SQL in the public response.
    assert "secret-value" not in body
    assert "127.0.0.1" not in body
    assert "traceback" not in body
    assert "select 1" not in body


def test_liveness_still_works_when_database_unreachable() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://ticketflow:secret@127.0.0.1:1/none",
    )
    with TestClient(create_app(settings)) as broken_client:
        assert broken_client.get("/api/v1/health/live").status_code == 200


def test_cors_allows_configured_origin_only(client: TestClient) -> None:
    allowed = client.options(
        "/api/v1/tickets",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    methods = allowed.headers["access-control-allow-methods"]
    assert {"GET", "POST", "PATCH"} <= {part.strip() for part in methods.split(",")}

    denied = client.options(
        "/api/v1/tickets",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert denied.headers.get("access-control-allow-origin") is None


def test_openapi_and_docs_are_available(client: TestClient) -> None:
    schema = client.get("/api/v1/openapi.json")
    assert schema.status_code == 200
    document = schema.json()
    assert "/api/v1/tickets" in document["paths"]
    assert "/api/v1/tickets/{ticket_id}" in document["paths"]
    assert "/api/v1/health/live" in document["paths"]
    assert "/api/v1/health/ready" in document["paths"]
    for path in (
        "/api/v1/tickets/{ticket_id}/status",
        "/api/v1/tickets/{ticket_id}/priority",
        "/api/v1/tickets/{ticket_id}/category",
        "/api/v1/tickets/{ticket_id}/assignment",
        "/api/v1/tickets/{ticket_id}/notes",
        "/api/v1/tickets/{ticket_id}/activities",
        "/api/v1/activities",
        "/api/v1/agents",
        "/api/v1/dashboard/summary",
    ):
        assert path in document["paths"]

    list_params = document["paths"]["/api/v1/tickets"]["get"]["parameters"]
    names = {parameter["name"] for parameter in list_params}
    assert {
        "page",
        "page_size",
        "search",
        "status",
        "priority",
        "category",
        "assigned_agent_id",
        "unassigned",
        "sort_by",
        "sort_dir",
    } <= names

    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "The requested resource was not found.",
        }
    }


def test_method_not_allowed_uses_error_envelope(client: TestClient) -> None:
    response = client.post("/api/v1/tickets")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("database_url", "sqlite:///ticketflow.db"),
        ("database_url", ""),
        ("cors_origins", "*"),
        ("cors_origins", " , "),
    ],
)
def test_settings_reject_unsafe_values(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="test", **{field: value})


def test_settings_parse_cors_origin_list() -> None:
    settings = Settings(
        app_env="test",
        cors_origins="http://localhost:5173/, http://127.0.0.1:5173",
    )
    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    assert settings.is_test is True
