"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Iterator[Session]:
    """Yield a request-scoped session and always close it.

    Read-only endpoints do not commit; any exception is rolled back before the
    session is returned to the pool so a failed request cannot leak an open
    transaction into the next one.
    """
    session_factory = request.app.state.session_factory
    db: Session = session_factory()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
