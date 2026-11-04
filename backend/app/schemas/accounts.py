"""Account-administration contracts.

Every response is a deliberate projection: password hashes, refresh-token
hashes and session identifiers never leave the server.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import MIN_PASSWORD_LENGTH
from app.models.enums import AccountRole
from app.schemas.common import PageMeta, UtcDatetime


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if (
        "@" not in normalized
        or normalized.startswith("@")
        or normalized.endswith("@")
    ):
        raise ValueError("A valid account email address is required.")
    return normalized


def _normalize_display_name(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("A display name is required.")
    return trimmed


class AdminAccountSummary(BaseModel):
    """Safe account record for the administration table."""

    id: str = Field(description="Stable account UUID used by every endpoint.")
    email: str
    display_name: str
    role: AccountRole
    is_active: bool = Field(description="Inactive accounts cannot sign in.")
    must_change_password: bool = Field(
        description=(
            "True while the account still uses the initial password an "
            "administrator provisioned."
        )
    )
    agent_id: str | None = Field(description="Linked support agent, if any.")
    agent_name: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class AccountListResponse(BaseModel):
    items: list[AdminAccountSummary]
    pagination: PageMeta


class AccountCreate(BaseModel):
    """Provision a new account.

    The initial password is transmitted once to this admin-authorized endpoint,
    hashed with Argon2id immediately and never echoed back or logged. The new
    account must replace it before it can use operational endpoints.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "new.agent@ticketflow.local",
                "display_name": "Hana Tesfaye",
                "role": "agent",
                "agent_id": "AG-05",
                "password": "a-strong-initial-password",
            }
        }
    )

    email: str = Field(
        min_length=3,
        max_length=254,
        description="Case-insensitive; stored lower-case and unique.",
    )
    display_name: str = Field(min_length=2, max_length=160)
    role: AccountRole = Field(description="`agent`, `reviewer` or `admin`.")
    password: str = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=200,
        description=(
            f"Initial password, at least {MIN_PASSWORD_LENGTH} characters. "
            "Hashed with Argon2id; never stored or returned in clear text."
        ),
    )
    agent_id: str | None = Field(
        default=None,
        description=(
            "Support agent to link. Required for operational attribution: an "
            "account without an agent cannot triage tickets."
        ),
    )
    is_active: bool = Field(
        default=True,
        description="Inactive accounts cannot sign in or refresh sessions.",
    )

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("display_name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _normalize_display_name(value)

    @field_validator("agent_id")
    @classmethod
    def _agent(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip().upper()
        if not trimmed:
            raise ValueError("agent_id must be omitted or a non-empty agent ID.")
        return trimmed


class AccountUpdate(BaseModel):
    """Update the properties an administrator may change.

    Omitted fields stay untouched. ``agent_id`` must be sent explicitly as
    `null` to unlink an agent; role and activation changes are refused for the
    acting administrator's own account.
    """

    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    role: AccountRole | None = None
    agent_id: str | None = Field(
        default=None, description="Send `null` explicitly to unlink the agent."
    )
    is_active: bool | None = None

    @field_validator("display_name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_display_name(value)

    @field_validator("agent_id")
    @classmethod
    def _agent(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip().upper()
        if not trimmed:
            raise ValueError("agent_id must be null to unlink, or an agent ID.")
        return trimmed


__all__ = [
    "AccountCreate",
    "AccountListResponse",
    "AccountUpdate",
    "AdminAccountSummary",
]
