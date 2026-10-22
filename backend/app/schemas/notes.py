"""Internal note contracts.

Notes are staff-only records. They are not customer replies and are never
embedded in ticket detail or activity summaries.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.models.note import NOTE_MAX_LENGTH
from app.schemas.common import PageMeta, UtcDatetime


class NoteAuthor(BaseModel):
    id: str
    name: str


class NoteCreate(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=NOTE_MAX_LENGTH,
        description="Internal note text. Surrounding whitespace is trimmed.",
    )
    actor_id: str | None = Field(
        default=None,
        max_length=16,
        description=(
            "Development-only actor identifier. **Untrusted** until "
            "authentication exists; defaults to the seeded demo agent."
        ),
    )

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Internal note content cannot be empty.")
        if len(trimmed) > NOTE_MAX_LENGTH:
            raise ValueError(
                f"Internal note content must be at most {NOTE_MAX_LENGTH} characters."
            )
        return trimmed

    @field_validator("actor_id")
    @classmethod
    def _normalize_actor_id(cls, value: str | None) -> str | None:
        return value.strip().upper() if value and value.strip() else None


class NoteResponse(BaseModel):
    id: str = Field(description="Persisted note UUID.")
    ticket_id: str = Field(description="Public ticket identifier, e.g. `TF-1051`.")
    content: str
    author: NoteAuthor
    created_at: UtcDatetime
    updated_at: UtcDatetime


class NoteListResponse(BaseModel):
    items: list[NoteResponse]
    pagination: PageMeta
