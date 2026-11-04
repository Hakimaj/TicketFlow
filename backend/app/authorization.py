"""Shared role → permission policy.

Authorization is expressed as explicit permission dependencies instead of
role-string comparisons scattered across route handlers. Route modules import
the dependencies from here, so the policy has exactly one home.

Frontend visibility rules are a usability aid only; these checks are the
security boundary.

Permission matrix (enforced in ``tests/test_authorization.py``):

============================  =====  ========  =====
Operation                     Agent  Reviewer  Admin
============================  =====  ========  =====
Read tickets/queues           yes    yes       yes
Read notes/activities         yes    yes       yes
Triage mutations/assignment   yes    yes       yes
Internal notes                yes    yes       yes
Reply draft create/edit       yes    yes       yes
Reply submit                  yes    yes       yes
Approve / request changes     no     yes       yes
Demo-send an approved reply   yes    yes       yes
Manage accounts               no     no        yes
============================  =====  ========  =====

Reply authorship still blocks self-approval for every role; see
``app.services.replies``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.api.deps import CurrentAccount, get_current_account
from app.core.errors import ApiError
from app.models.auth import UserAccount
from app.services.auth import permissions_for

__all__ = [
    "CanCreateTickets",
    "CanDraftReplies",
    "CanManageAccounts",
    "CanReadOperations",
    "CanReviewReplies",
    "CanSendDemo",
    "CanTriage",
    "CurrentAccount",
    "require_roles",
]


def _permission_dependency(*required: str):
    def dependency(account: CurrentAccount) -> UserAccount:
        granted = set(permissions_for(account.role))
        if any(permission not in granted for permission in required):
            raise ApiError(
                status_code=403,
                code="forbidden",
                message=(
                    "Your account is not allowed to perform this action."
                ),
            )
        return account

    return Depends(dependency)


def require_roles(*roles: str):
    """Dependency asserting one of ``roles`` (used for account management)."""
    allowed = set(roles)

    def dependency(account: CurrentAccount) -> UserAccount:
        if account.role.value not in allowed:
            raise ApiError(
                status_code=403,
                code="forbidden",
                message=(
                    "Your account is not allowed to perform this action."
                ),
            )
        return account

    return Depends(dependency)


#: Any signed-in, active account may read operational data.
CanReadOperations = _permission_dependency("tickets:read")

#: Creating a new ticket from staff intake.
CanCreateTickets = _permission_dependency("tickets:write")

#: Triage mutations, assignment and internal notes.
CanTriage = _permission_dependency("tickets:write", "notes:write")

#: Creating, editing and submitting reply drafts.
CanDraftReplies = _permission_dependency("replies:write")

#: Human review decisions (approve / request changes).
CanReviewReplies = _permission_dependency("replies:review")

#: Explicit demo sending of an already approved reply.
CanSendDemo = _permission_dependency("replies:send")

#: Account administration. The documented permission is `accounts:manage`,
#: which today is granted only to the admin role; the check stays
#: permission-based so roles and permissions do not diverge.
CanManageAccounts = _permission_dependency("accounts:manage")
