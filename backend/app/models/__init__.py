"""ORM models. Importing this package registers every table on ``Base``."""

from app.db.base import Base
from app.models.activity import TicketActivity
from app.models.agent import Agent
from app.models.auth import RefreshSession, UserAccount
from app.models.common import TimestampMixin, enum_type, utcnow
from app.models.note import NOTE_MAX_LENGTH, TicketNote
from app.models.enums import (
    ActivityAction,
    ActivityActorType,
    AccountRole,
    AgentRole,
    ReplyReviewDecision,
    ReplyState,
    SupportTeam,
    TicketCategory,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)
from app.models.reply import (
    REPLY_MAX_LENGTH,
    REVIEW_COMMENT_MAX_LENGTH,
    CustomerReply,
    ReplyRevision,
    ReplyReview,
)
from app.models.requester import Requester
from app.models.ticket import Ticket

__all__ = [
    "AccountRole",
    "ActivityAction",
    "ActivityActorType",
    "Agent",
    "AgentRole",
    "Base",
    "CustomerReply",
    "NOTE_MAX_LENGTH",
    "REPLY_MAX_LENGTH",
    "REVIEW_COMMENT_MAX_LENGTH",
    "ReplyReview",
    "ReplyReviewDecision",
    "RefreshSession",
    "ReplyRevision",
    "ReplyState",
    "UserAccount",
    "Requester",
    "SupportTeam",
    "Ticket",
    "TicketActivity",
    "TicketCategory",
    "TicketNote",
    "TicketChannel",
    "TicketPriority",
    "TicketStatus",
    "TimestampMixin",
    "enum_type",
    "utcnow",
]
