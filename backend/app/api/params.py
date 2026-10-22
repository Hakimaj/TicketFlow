"""Reusable, validated path parameters."""

from __future__ import annotations

from typing import Annotated

from fastapi import Path

TicketIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=32,
        description="Public ticket identifier, e.g. `TF-1051`.",
        examples=["TF-1051"],
    ),
]
