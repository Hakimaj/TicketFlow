"""Authentication contracts.

Password hashes, refresh-token hashes and signing material are never part of a
response model.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import MIN_PASSWORD_LENGTH
from app.models.enums import AccountRole


class LoginRequest(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=254,
        description="Account email. Case-insensitive; surrounding whitespace trimmed.",
    )
    password: str = Field(
        min_length=8,
        max_length=200,
        description="Account password. Never logged or echoed.",
    )

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@"):
            raise ValueError("A valid email address is required.")
        return normalized


class AccountProfile(BaseModel):
    id: str = Field(description="Stable account UUID.")
    email: str
    display_name: str
    role: AccountRole
    agent_id: str | None = Field(
        default=None,
        description="Linked support agent when the account has one.",
    )
    agent_name: str | None = None
    must_change_password: bool = Field(
        default=False,
        description=(
            "True until a provisioned account replaces its initial password. "
            "Operational endpoints reject such sessions with "
            "`403 password_change_required`."
        ),
    )
    permissions: list[str] = Field(
        description="Server-derived permission strings for UI affordances."
    )


class AuthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJ...",
                "token_type": "bearer",
                "expires_in": 900,
                "user": {
                    "id": "0d4f...",
                    "email": "admin@ticketflow.local",
                    "display_name": "Abebe Kebede",
                    "role": "admin",
                    "agent_id": "AG-01",
                    "agent_name": "Abebe Kebede",
                    "permissions": [
                        "tickets:read",
                        "tickets:write",
                        "replies:review",
                    ],
                },
            }
        }
    )

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds.")
    user: AccountProfile


class PasswordChangeRequest(BaseModel):
    """Self-service password change (also used to clear a forced change)."""

    current_password: str = Field(
        min_length=1, max_length=200, description="Never logged or echoed."
    )
    new_password: str = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=200,
        description=(
            f"New password, at least {MIN_PASSWORD_LENGTH} characters."
        ),
    )


class LogoutResponse(BaseModel):
    status: str = "ok"
