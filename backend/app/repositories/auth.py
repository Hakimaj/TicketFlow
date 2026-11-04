"""Database access for accounts and refresh sessions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.models.auth import RefreshSession, UserAccount


def get_user_by_email(db: Session, email: str) -> UserAccount | None:
    return db.scalars(
        select(UserAccount)
        .options(joinedload(UserAccount.agent))
        .where(UserAccount.email == email)
    ).one_or_none()


def get_user_by_id(db: Session, account_id: uuid.UUID) -> UserAccount | None:
    return db.scalars(
        select(UserAccount)
        .options(joinedload(UserAccount.agent))
        .where(UserAccount.id == account_id)
    ).one_or_none()


def add_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
    session_id: uuid.UUID | None = None,
) -> RefreshSession:
    session = RefreshSession(
        id=session_id or uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(session)
    return session


def get_session_by_id(
    db: Session, session_id: uuid.UUID, *, for_update: bool = False
) -> RefreshSession | None:
    """Load a session, optionally locking its row for rotation.

    The lock is deliberately taken without eager joins: PostgreSQL cannot
    apply ``FOR UPDATE`` cleanly to nullable joined rows. Related account data
    is loaded lazily inside the caller's transaction.
    """
    stmt = select(RefreshSession).where(RefreshSession.id == session_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).one_or_none()


def get_session_by_hash(
    db: Session, token_hash: str, *, for_update: bool = False
) -> RefreshSession | None:
    stmt = (
        select(RefreshSession)
        .options(joinedload(RefreshSession.user).joinedload(UserAccount.agent))
        .where(
            RefreshSession.token_hash == token_hash,
            RefreshSession.revoked_at.is_(None),
        )
    )
    if for_update:
        # Legacy reset only; current tokens lock through ``get_session_by_id``.
        stmt = stmt.with_for_update(of=RefreshSession)
    return db.scalars(stmt).one_or_none()


def revoke_session(db: Session, session: RefreshSession, now: datetime) -> None:
    # Replace the stored hash so a leaked copy of the token cannot be matched
    # again. Keep it within the 64-character column and unique per session.
    session.revoked_at = now
    session.token_hash = f"revoked:{uuid.uuid4().hex}"


def revoke_all_for_user(
    db: Session, user_id: uuid.UUID, now: datetime
) -> None:
    # ``get_session_by_hash`` ignores revoked rows, so copied tokens can never
    # be used again even though the stored hash remains for audit.
    db.execute(
        update(RefreshSession)
        .where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
