"""Idempotent demonstration data.

The records mirror the frontend fixtures in ``frontend/src/data`` (agents,
tickets, replies, activity) with the same public IDs, categories, priorities,
statuses, assignments and reply↔ticket pairings. Only fictional data is used.

Seeding is **explicit** (CLI or tests); the API never seeds at startup and never
overwrites existing rows. Running the seeder again with the same data is a
no-op, so it is safe to run after every migration.

Background filler tickets generated randomly in the frontend are intentionally
not ported yet; they are not required by the read-only endpoints and would
complicate an honest, reviewable fixture set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.labels import CATEGORY_TEAM
from app.models.activity import TicketActivity
from app.models.agent import Agent
from app.models.enums import (
    ActivityAction,
    ActivityActorType,
    AgentRole,
    ReplyReviewDecision,
    ReplyState,
    SupportTeam,
    TicketCategory,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)
from app.models.reply import CustomerReply, ReplyReview, ReplyRevision
from app.models.requester import Requester
from app.models.ticket import Ticket

AGENT_SEEDS: list[dict[str, Any]] = [
    {
        "id": "AG-01",
        "name": "Abebe Kebede",
        "role": AgentRole.SUPERVISOR,
        "team": SupportTeam.CUSTOMER_SUPPORT,
        "email": "abebe.k@ticketflow.example",
        "is_demo_user": True,
    },
    {
        "id": "AG-02",
        "name": "Hana Tesfaye",
        "role": AgentRole.AGENT,
        "team": SupportTeam.BILLING_TEAM,
        "email": "hana.t@ticketflow.example",
    },
    {
        "id": "AG-03",
        "name": "Dawit Mengistu",
        "role": AgentRole.AGENT,
        "team": SupportTeam.LOGISTICS_TEAM,
        "email": "dawit.m@ticketflow.example",
    },
    {
        "id": "AG-04",
        "name": "Selam Girma",
        "role": AgentRole.AGENT,
        "team": SupportTeam.TECHNICAL_SUPPORT,
        "email": "selam.g@ticketflow.example",
    },
    {
        "id": "AG-05",
        "name": "Yonas Abate",
        "role": AgentRole.AGENT,
        "team": SupportTeam.RETURNS_TEAM,
        "email": "yonas.a@ticketflow.example",
    },
    {
        "id": "AG-06",
        "name": "Meron Haile",
        "role": AgentRole.AGENT,
        "team": SupportTeam.CUSTOMER_SUPPORT,
        "email": "meron.h@ticketflow.example",
    },
    {
        "id": "AG-07",
        "name": "Liya Tadesse",
        "role": AgentRole.AGENT,
        "team": SupportTeam.CUSTOMER_SUPPORT,
        "email": "liya.t@ticketflow.example",
    },
    {
        "id": "AG-08",
        "name": "Bereket Solomon",
        "role": AgentRole.ADMIN,
        "team": None,
        "email": "bereket.s@ticketflow.example",
    },
]

TICKET_SEEDS: list[dict[str, Any]] = [
    {
        "id": "TF-1051",
        "subject": "Charged twice from Telebirr for order #ET-88412",
        "description": "I paid for one order but two notifications of 1,450 birr from Telebirr came in within a minute. I need one payment reversed.",
        "requester_name": "Marta Alemu",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.BILLING,
        "priority": TicketPriority.URGENT,
        "status": TicketStatus.OPEN,
        "assigned_agent_id": "AG-02",
        "created_hours_ago": 1,
        "updated_hours_ago": 0.4,
    },
    {
        "id": "TF-1050",
        "subject": "Parcel #ETD-2214 stuck at Addis Ababa hub for 6 days",
        "description": 'Tracking says "arrived at hub" since last Monday. It was supposed to reach Bahir Dar this week for a birthday gift.',
        "requester_name": "Abel Tesfaye",
        "channel": TicketChannel.EMAIL,
        "category": TicketCategory.DELIVERY,
        "priority": TicketPriority.URGENT,
        "status": TicketStatus.NEW,
        "assigned_agent_id": None,
        "created_hours_ago": 2,
        "updated_hours_ago": 2,
    },
    {
        "id": "TF-1049",
        "subject": "Delivery notice for an order I do not recognise",
        "description": "I received an SMS that my parcel from the Awassa market store is arriving tomorrow, but I have not placed any order this month.",
        "requester_name": "Genet Mulugeta",
        "channel": TicketChannel.PHONE,
        "category": TicketCategory.GENERAL,
        "priority": TicketPriority.HIGH,
        "status": TicketStatus.NEEDS_REVIEW,
        "assigned_agent_id": None,
        "created_hours_ago": 3,
        "updated_hours_ago": 2.6,
        "suggested_category": None,
        "suggested_priority": None,
        "review_note": "Could be a wrong-number SMS or account takeover. Classifier confidence 41% — needs human triage before routing.",
    },
    {
        "id": "TF-1048",
        "subject": "Checkout freezes after selecting Chapa as payment method",
        "description": "On desktop Chrome the payment step spins forever after I pick Chapa. Same basket works on my phone, so it looks browser-related.",
        "requester_name": "Samuel Bekele",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.TECHNICAL,
        "priority": TicketPriority.HIGH,
        "status": TicketStatus.OPEN,
        "assigned_agent_id": "AG-04",
        "created_hours_ago": 5,
        "updated_hours_ago": 1.2,
    },
    {
        "id": "TF-1047",
        "subject": "Exchange dress ordered for Meskel — size M to L",
        "description": "The dress arrived with the tag still attached but the size runs small. I would like a straight exchange rather than a refund.",
        "requester_name": "Tigist Fikru",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.RETURNS,
        "priority": TicketPriority.NORMAL,
        "status": TicketStatus.PENDING,
        "assigned_agent_id": "AG-05",
        "created_hours_ago": 8,
        "updated_hours_ago": 3,
    },
    {
        "id": "TF-1046",
        "subject": "VAT line on invoice #INV-55103 does not match my subtotal",
        "description": "My subtotal was 3,200 birr and the invoice shows VAT of 512 birr instead of 480. The difference is small but our finance team needs correct documents.",
        "requester_name": "Dagimawi Assefa",
        "channel": TicketChannel.EMAIL,
        "category": TicketCategory.BILLING,
        "priority": TicketPriority.HIGH,
        "status": TicketStatus.NEW,
        "assigned_agent_id": None,
        "created_hours_ago": 9,
        "updated_hours_ago": 9,
    },
    {
        "id": "TF-1045",
        "subject": "Parcel going to the wrong address — Bahir Dar instead of Gondar",
        "description": "I moved recently and the checkout still had my old address. The courier label shows Bahir Dar. Please correct it before dispatch.",
        "requester_name": "Hirut Wolde",
        "channel": TicketChannel.CHAT,
        "category": TicketCategory.DELIVERY,
        "priority": TicketPriority.NORMAL,
        "status": TicketStatus.OPEN,
        "assigned_agent_id": "AG-03",
        "created_hours_ago": 11,
        "updated_hours_ago": 6,
    },
    {
        "id": "TF-1044",
        "subject": "App logs me out constantly after update 4.12",
        "description": "Since the Android update every session lasts about a minute. Cleared cache and reinstalled, still the same.",
        "requester_name": "Nahom Girma",
        "channel": TicketChannel.EMAIL,
        "category": TicketCategory.TECHNICAL,
        "priority": TicketPriority.NORMAL,
        "status": TicketStatus.RESOLVED,
        "assigned_agent_id": "AG-04",
        "created_hours_ago": 30,
        "updated_hours_ago": 14,
    },
    {
        "id": "TF-1043",
        "subject": "Do you deliver to Hawassa on Sundays?",
        "description": "I want to send a cake box to my sister in Hawassa this Sunday. What are the weekend delivery options and fees?",
        "requester_name": "Betelhem Alemu",
        "channel": TicketChannel.CHAT,
        "category": TicketCategory.GENERAL,
        "priority": TicketPriority.LOW,
        "status": TicketStatus.OPEN,
        "assigned_agent_id": None,
        "created_hours_ago": 14,
        "updated_hours_ago": 14,
    },
    {
        "id": "TF-1042",
        "subject": "Refund to Telebirr wallet not received after 10 days",
        "description": "Ticket said refund was processed on the 8th but nothing has reached my wallet and my bank says they see nothing.",
        "requester_name": "Solomon Tsegaye",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.BILLING,
        "priority": TicketPriority.NORMAL,
        "status": TicketStatus.PENDING,
        "assigned_agent_id": "AG-02",
        "created_hours_ago": 36,
        "updated_hours_ago": 20,
    },
    {
        "id": "TF-1041",
        "subject": "Perishable grocery order arrived completely thawed",
        "description": "The frozen items in my grocery basket arrived at room temperature. The insulated liner was open. I have photos of the packaging.",
        "requester_name": "Amina Yusuf",
        "channel": TicketChannel.PHONE,
        "category": TicketCategory.DELIVERY,
        "priority": TicketPriority.URGENT,
        "status": TicketStatus.OPEN,
        "assigned_agent_id": "AG-03",
        "created_hours_ago": 40,
        "updated_hours_ago": 18,
    },
    {
        "id": "TF-1040",
        "subject": "Request pickup for return of cracked screen protector",
        "description": "The tempered glass arrived already cracked. I repacked it with the order slip. Please schedule a courier pickup.",
        "requester_name": "Yared Bekele",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.RETURNS,
        "priority": TicketPriority.NORMAL,
        "status": TicketStatus.NEW,
        "assigned_agent_id": None,
        "created_hours_ago": 44,
        "updated_hours_ago": 44,
    },
    {
        "id": "TF-1039",
        "subject": "Need detailed payment receipts for my expense report",
        "description": "My company reimburses purchases. I need receipts with VAT breakdowns for orders from the last 30 days.",
        "requester_name": "Fikru Mengesha",
        "channel": TicketChannel.EMAIL,
        "category": TicketCategory.BILLING,
        "priority": TicketPriority.LOW,
        "status": TicketStatus.OPEN,
        "assigned_agent_id": "AG-02",
        "created_hours_ago": 52,
        "updated_hours_ago": 40,
    },
    {
        "id": "TF-1038",
        "subject": "Account shows a different person’s name after sign-in",
        "description": "I signed in with my phone number and the account header shows another customer’s name and saved addresses. I am worried my number is linked to someone else’s profile.",
        "requester_name": "Kalkidan Bekele",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.TECHNICAL,
        "priority": TicketPriority.HIGH,
        "status": TicketStatus.NEEDS_REVIEW,
        "assigned_agent_id": None,
        "created_hours_ago": 56,
        "updated_hours_ago": 55,
        "suggested_category": TicketCategory.TECHNICAL,
        "suggested_priority": TicketPriority.URGENT,
        "review_note": "Possible account merge issue. Escalating for supervisor triage before any routing — do not reply to the customer yet.",
    },
    {
        "id": "TF-1037",
        "subject": "Courier demanded extra cash on delivery",
        "description": "The rider asked for 300 birr on top of the label, which I had already paid online. I paid to avoid losing the parcel, but this needs checking.",
        "requester_name": "Zewditu Assefa",
        "channel": TicketChannel.PHONE,
        "category": TicketCategory.DELIVERY,
        "priority": TicketPriority.HIGH,
        "status": TicketStatus.PENDING,
        "assigned_agent_id": "AG-03",
        "created_hours_ago": 70,
        "updated_hours_ago": 55,
    },
    {
        "id": "TF-1036",
        "subject": "Card declined but money left my Telebirr balance",
        "description": "Checkout said payment failed twice, yet my wallet shows two 2,300 birr holds. One order is in my account, the other one vanished.",
        "requester_name": "Rahel Desta",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.BILLING,
        "priority": TicketPriority.HIGH,
        "status": TicketStatus.RESOLVED,
        "assigned_agent_id": "AG-02",
        "created_hours_ago": 96,
        "updated_hours_ago": 60,
    },
    {
        "id": "TF-1035",
        "subject": "Order status notifications duplicated on iPhone",
        "description": "Every tracking push notification arrives twice with a few seconds gap. Phone restarted, notifications re-enabled, no change.",
        "requester_name": "Eyob Ayele",
        "channel": TicketChannel.EMAIL,
        "category": TicketCategory.TECHNICAL,
        "priority": TicketPriority.NORMAL,
        "status": TicketStatus.OPEN,
        "assigned_agent_id": "AG-04",
        "created_hours_ago": 120,
        "updated_hours_ago": 96,
    },
    {
        "id": "TF-1034",
        "subject": "Tracking shows delivered one day before parcel arrived",
        "description": "The tracking page marked my order delivered last Tuesday, but courier the handed it over on Wednesday evening.",
        "requester_name": "Hiwot Tadesse",
        "channel": TicketChannel.CHAT,
        "category": TicketCategory.DELIVERY,
        "priority": TicketPriority.NORMAL,
        "status": TicketStatus.RESOLVED,
        "assigned_agent_id": "AG-03",
        "created_hours_ago": 150,
        "updated_hours_ago": 130,
    },
    {
        "id": "TF-1033",
        "subject": "How do promo codes combine with free shipping?",
        "description": "I have a 10% code from the newsletter and a free-shipping offer. Can I use both on one basket?",
        "requester_name": "Mulugeta Gebre",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.GENERAL,
        "priority": TicketPriority.LOW,
        "status": TicketStatus.CLOSED,
        "assigned_agent_id": "AG-06",
        "created_hours_ago": 170,
        "updated_hours_ago": 160,
    },
    {
        "id": "TF-1032",
        "subject": "Exchange hoodie for smaller size — tag still attached",
        "description": "Size L is too loose, I would like S. Original packaging kept. Should I wait for pickup or drop it at the Piassa service point?",
        "requester_name": "Lemma Woldu",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.RETURNS,
        "priority": TicketPriority.LOW,
        "status": TicketStatus.PENDING,
        "assigned_agent_id": "AG-05",
        "created_hours_ago": 190,
        "updated_hours_ago": 170,
    },
    {
        "id": "TF-1031",
        "subject": "Update phone number on my account",
        "description": "I changed mobile providers. Old number still receives verification codes which worries me.",
        "requester_name": "Selamawit Negash",
        "channel": TicketChannel.CHAT,
        "category": TicketCategory.GENERAL,
        "priority": TicketPriority.NORMAL,
        "status": TicketStatus.OPEN,
        "assigned_agent_id": "AG-07",
        "created_hours_ago": 210,
        "updated_hours_ago": 200,
    },
    {
        "id": "TF-1030",
        "subject": "Premium subscription charged twice this month",
        "description": "My card was charged 99 birr twice for the same subscription period. Last month worked fine.",
        "requester_name": "Mekonnen Ayele",
        "channel": TicketChannel.EMAIL,
        "category": TicketCategory.BILLING,
        "priority": TicketPriority.URGENT,
        "status": TicketStatus.RESOLVED,
        "assigned_agent_id": "AG-02",
        "created_hours_ago": 240,
        "updated_hours_ago": 210,
    },
    {
        "id": "TF-1029",
        "subject": "Box arrived crushed — kitchen glasses broken",
        "description": "The outer box was torn and three glasses are in pieces. I sent photos through the app. Need replacement or refund.",
        "requester_name": "Tsion Habte",
        "channel": TicketChannel.WEB_FORM,
        "category": TicketCategory.DELIVERY,
        "priority": TicketPriority.HIGH,
        "status": TicketStatus.OPEN,
        "assigned_agent_id": "AG-03",
        "created_hours_ago": 260,
        "updated_hours_ago": 250,
    },
    {
        "id": "TF-1028",
        "subject": "Password reset email never arrives",
        "description": "Requested a reset link five times over two days, checked spam. Nothing comes. My email is correct because order updates arrive.",
        "requester_name": "Biruk Alemayehu",
        "channel": TicketChannel.CHAT,
        "category": TicketCategory.TECHNICAL,
        "priority": TicketPriority.NORMAL,
        "status": TicketStatus.NEW,
        "assigned_agent_id": None,
        "created_hours_ago": 280,
        "updated_hours_ago": 280,
    },
]

REPLY_SEEDS: list[dict[str, Any]] = [
    {
        "id": "REP-101",
        "ticket_id": "TF-1051",
        "author_id": "AG-02",
        "body": "Dear Marta,\n\nThank you for reaching out regarding the duplicate transaction for order #ET-88412.\n\nOur billing team has confirmed the duplicate charge of 1,450 ETB with the payment gateway. The duplicate reference has been submitted for reversal, which typically reflects back in your Telebirr wallet within 24 to 48 hours.\n\nPlease reply directly to this ticket if you have any questions.\n\nBest regards,\nHana Tesfaye\nBilling Specialist",
        "state": ReplyState.PENDING_APPROVAL,
        "version": 1,
        "created_hours_ago": 0.8,
        "updated_hours_ago": 0.5,
        "submitted_hours_ago": 0.5,
    },
    {
        "id": "REP-102",
        "ticket_id": "TF-1048",
        "author_id": "AG-04",
        "body": "Dear Samuel,\n\nThank you for reporting the checkout freeze when selecting Chapa. Our technical team investigated the timeout and deployed a fix to the payment integration service.\n\nPlease attempt your checkout once more in Chrome. If the spinner persists, reply directly and we will escalate it immediately.\n\nBest regards,\nSelam Girma\nTechnical Support",
        "state": ReplyState.PENDING_APPROVAL,
        "version": 1,
        "created_hours_ago": 1.5,
        "updated_hours_ago": 1.2,
        "submitted_hours_ago": 1.2,
    },
    {
        "id": "REP-103",
        "ticket_id": "TF-1045",
        "author_id": "AG-03",
        "body": "Dear Hirut,\n\nWe have updated the delivery address on your parcel from Bahir Dar to your new Gondar address as requested. Our dispatch team has corrected the courier label, and delivery to Gondar is scheduled for tomorrow.\n\nThank you for notifying us promptly.\n\nBest regards,\nDawit Mengistu\nLogistics Team",
        "state": ReplyState.APPROVED,
        "version": 1,
        "created_hours_ago": 3.5,
        "updated_hours_ago": 2.0,
        "submitted_hours_ago": 2.8,
        "reviewer_id": "AG-01",
        "reviewer_name": "Abebe Kebede",
        "reviewed_hours_ago": 2.0,
    },
    {
        "id": "REP-104",
        "ticket_id": "TF-1047",
        "author_id": "AG-05",
        "body": "Dear Tigist,\n\nWe received your request to exchange the Meskel dress from size M to size L. Please keep the dress in its original packaging with all tags attached.\n\nOur courier will collect the package once the replacement size is confirmed in our inventory, and we will confirm the pickup window with you.\n\nBest regards,\nYonas Abate\nReturns Team",
        "state": ReplyState.CHANGES_REQUESTED,
        "version": 1,
        "created_hours_ago": 4.5,
        "updated_hours_ago": 3.0,
        "submitted_hours_ago": 3.8,
        "reviewer_id": "AG-01",
        "reviewer_name": "Abebe Kebede",
        "reviewed_hours_ago": 3.0,
        "reviewer_feedback": "Please confirm that size L is actually in stock and state the expected pickup window before instructing the customer to pack the item.",
    },
    {
        "id": "REP-105",
        "ticket_id": "TF-1044",
        "author_id": "AG-04",
        "body": "Dear Nahom,\n\nThank you for reporting the repeated sign-outs after the Android 4.12 update. Our mobile team traced the issue to an expired session token and has released hotfix 4.12.1.\n\nPlease update the TicketFlow app from the Play Store and sign in once more. If the session still expires, reply directly and we will escalate it immediately.\n\nBest regards,\nSelam Girma\nTechnical Support",
        "state": ReplyState.SENT,
        "version": 1,
        "created_hours_ago": 16,
        "updated_hours_ago": 13,
        "submitted_hours_ago": 15,
        "reviewer_id": "AG-01",
        "reviewer_name": "Abebe Kebede",
        "reviewed_hours_ago": 14,
        "sent_hours_ago": 13,
        "sent_by_actor_name": "Abebe Kebede",
    },
]

# Seeded human review decisions. They give the seeded approved/sent replies a
# stored decision for their exact revision, so the demo-send gate works against
# seeded data exactly as it does for newly created replies.
REVIEW_SEEDS: list[dict[str, Any]] = [
    {
        "reply_id": "REP-103",
        "version": 1,
        "decision": ReplyReviewDecision.APPROVED,
        "reviewer_id": "AG-01",
        "comment": None,
        "hours_ago": 2.0,
    },
    {
        "reply_id": "REP-104",
        "version": 1,
        "decision": ReplyReviewDecision.CHANGES_REQUESTED,
        "reviewer_id": "AG-01",
        "comment": (
            "Please confirm that size L is actually in stock and state the "
            "expected pickup window before instructing the customer to pack "
            "the item."
        ),
        "hours_ago": 3.0,
    },
    {
        "reply_id": "REP-105",
        "version": 1,
        "decision": ReplyReviewDecision.APPROVED,
        "reviewer_id": "AG-01",
        "comment": None,
        "hours_ago": 14.0,
    },
]

ACTIVITY_SEEDS: list[dict[str, Any]] = [
    {
        "id": "ACT-041",
        "ticket_id": "TF-1051",
        "actor_name": "Billing gateway webhook",
        "actor_type": ActivityActorType.AUTOMATION,
        "action": ActivityAction.CREATED,
        "detail": "Payment duplication flagged by gateway reconciliation job.",
        "hours_ago": 1,
    },
    {
        "id": "ACT-040",
        "ticket_id": "TF-1051",
        "actor_name": "Hana Tesfaye",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.ASSIGNED,
        "detail": "Claimed for Billing triage; duplicate-charge form sent to requester.",
        "hours_ago": 0.4,
    },
    {
        "id": "ACT-039",
        "ticket_id": "TF-1049",
        "actor_name": "Classification service",
        "actor_type": ActivityActorType.AUTOMATION,
        "action": ActivityAction.REVIEW_FLAGGED,
        "detail": "Low confidence (41%) between General and Delivery. Queued for human triage.",
        "hours_ago": 2.6,
    },
    {
        "id": "ACT-042",
        "ticket_id": "TF-1051",
        "reply_id": "REP-101",
        "actor_name": "Hana Tesfaye",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.REPLY_SUBMITTED,
        "detail": "Customer reply submitted for supervisor approval.",
        "hours_ago": 0.5,
    },
    {
        "id": "ACT-038",
        "ticket_id": "TF-1048",
        "reply_id": "REP-102",
        "actor_name": "Selam Girma",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.REPLIED_DRAFT,
        "detail": "Draft reply prepared: cache/extension checklist for Chapa checkout.",
        "hours_ago": 1.5,
    },
    {
        "id": "ACT-043",
        "ticket_id": "TF-1048",
        "reply_id": "REP-102",
        "actor_name": "Selam Girma",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.REPLY_SUBMITTED,
        "detail": "Customer reply submitted for supervisor approval.",
        "hours_ago": 1.2,
    },
    {
        "id": "ACT-044",
        "ticket_id": "TF-1047",
        "reply_id": "REP-104",
        "actor_name": "Abebe Kebede",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.REPLY_CHANGES_REQUESTED,
        "detail": "Changes requested on customer reply (v1); feedback retained in the review context.",
        "hours_ago": 3,
    },
    {
        "id": "ACT-037",
        "ticket_id": "TF-1047",
        "actor_name": "Yonas Abate",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.STATUS_CHANGED,
        "detail": "Status New → Pending. Awaiting requester confirmation of exchange size.",
        "hours_ago": 3,
    },
    {
        "id": "ACT-036",
        "ticket_id": "TF-1046",
        "actor_name": "Abebe Kebede",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.ASSIGNED,
        "detail": "Route to Billing team; VAT invoice mismatch pattern seen twice this week.",
        "hours_ago": 8.5,
    },
    {
        "id": "ACT-035",
        "ticket_id": "TF-1045",
        "reply_id": "REP-103",
        "actor_name": "Abebe Kebede",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.REPLY_APPROVED,
        "detail": "Customer reply (v1) approved for demo sending; no message was delivered.",
        "hours_ago": 2,
    },
    {
        "id": "ACT-046",
        "ticket_id": "TF-1044",
        "reply_id": "REP-105",
        "actor_name": "Abebe Kebede",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.REPLY_APPROVED,
        "detail": "Customer reply (v1) approved for demo sending; no message was delivered.",
        "hours_ago": 14,
    },
    {
        "id": "ACT-045",
        "ticket_id": "TF-1044",
        "reply_id": "REP-105",
        "actor_name": "Abebe Kebede",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.REPLIED_SENT,
        "detail": "Customer reply marked as sent in demo mode; no external delivery occurred.",
        "hours_ago": 13,
    },
    {
        "id": "ACT-034",
        "ticket_id": "TF-1044",
        "actor_name": "Selam Girma",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.RESOLVED,
        "detail": "Workaround released in hotfix 4.12.1; session persistence verified.",
        "hours_ago": 12.5,
    },
    {
        "id": "ACT-033",
        "ticket_id": "TF-1041",
        "actor_name": "Dawit Mengistu",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.ESCALATED,
        "detail": "Cold-chain failure escalated to logistics supervisor; refund pre-approved.",
        "hours_ago": 18,
    },
    {
        "id": "ACT-032",
        "ticket_id": "TF-1038",
        "actor_name": "Abebe Kebede",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.REVIEW_FLAGGED,
        "detail": "Held for supervisor review — possible account merge; no customer reply yet.",
        "hours_ago": 55,
    },
    {
        "id": "ACT-031",
        "ticket_id": "TF-1036",
        "actor_name": "Hana Tesfaye",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.RESOLVED,
        "detail": "Second hold released by Chapa after merchant reference shared.",
        "hours_ago": 60,
    },
    {
        "id": "ACT-030",
        "ticket_id": "TF-1037",
        "actor_name": "Classification service",
        "actor_type": ActivityActorType.AUTOMATION,
        "action": ActivityAction.CATEGORIZED,
        "detail": "Category Delivery, priority High (confidence 88%).",
        "hours_ago": 69,
    },
    {
        "id": "ACT-029",
        "ticket_id": "TF-1030",
        "actor_name": "Hana Tesfaye",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.RESOLVED,
        "detail": "Duplicate subscription charge reversed; confirmation sent to requester.",
        "hours_ago": 210,
    },
    {
        "id": "ACT-028",
        "ticket_id": "TF-1029",
        "actor_name": "Marta Alemu",
        "actor_type": ActivityActorType.AGENT,
        "action": ActivityAction.MERGED,
        "detail": "Merged duplicate report TF-1027 into this incident.",
        "hours_ago": 248,
    },
]


@dataclass
class SeedReport:
    """Counts of rows created vs. already present (reruns create nothing)."""

    created: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)

    def _add(self, bucket: dict[str, int], table: str, count: int) -> None:
        bucket[table] = bucket.get(table, 0) + count

    def record_created(self, table: str, count: int = 1) -> None:
        self._add(self.created, table, count)

    def record_skipped(self, table: str, count: int = 1) -> None:
        self._add(self.skipped, table, count)

    def as_dict(self) -> dict[str, Any]:
        return {"created": dict(self.created), "skipped": dict(self.skipped)}


def requester_email(name: str) -> str:
    """Same deterministic fictional address scheme as the frontend fixtures."""
    first, last = name.split(" ")[0], name.split(" ")[1]
    return f"{first.lower()}.{last.lower()}@myetmail.example"


def _ticket_timestamps(
    anchor: datetime, seed: dict[str, Any]
) -> dict[str, datetime | None]:
    created_at = anchor - timedelta(hours=seed["created_hours_ago"])
    updated_at = anchor - timedelta(hours=seed["updated_hours_ago"])
    terminal = seed["status"] in (TicketStatus.RESOLVED, TicketStatus.CLOSED)
    due_at: datetime | None = None
    if not terminal and seed["priority"] in (
        TicketPriority.URGENT,
        TicketPriority.HIGH,
    ):
        # 8 working-hour target, measured from the last update (frontend rule).
        due_at = anchor + timedelta(hours=8 - seed["updated_hours_ago"])
    return {"created_at": created_at, "updated_at": updated_at, "due_at": due_at}


def seed_demo_data(session: Session, *, anchor: datetime | None = None) -> SeedReport:
    """Insert the demonstration fixtures if they are missing.

    Idempotent by stable public identifier (agent ID, requester email, ticket
    ID, reply ID, activity ID). Existing rows are never updated or deleted, so
    reruns cannot clobber local changes.
    """
    anchor = (anchor or datetime.now(UTC)).replace(microsecond=0)
    report = SeedReport()

    # --- Agents ---------------------------------------------------------
    existing_agents = set(session.scalars(select(Agent.id)).all())
    for seed in AGENT_SEEDS:
        if seed["id"] in existing_agents:
            report.record_skipped("agents")
            continue
        session.add(Agent(**seed))
        existing_agents.add(seed["id"])
        report.record_created("agents")
    session.flush()

    # --- Requesters -----------------------------------------------------
    requester_ids: dict[str, Any] = {}
    for seed in TICKET_SEEDS:
        name = seed["requester_name"]
        email = requester_email(name)
        requester = session.scalar(select(Requester).where(Requester.email == email))
        if requester is None:
            requester = Requester(name=name, email=email)
            session.add(requester)
            session.flush()
            report.record_created("requesters")
        else:
            report.record_skipped("requesters")
        requester_ids[seed["id"]] = requester.id

    # --- Tickets --------------------------------------------------------
    ticket_ids: dict[str, Any] = {}
    existing_tickets = set(session.scalars(select(Ticket.public_id)).all())
    for seed in TICKET_SEEDS:
        public_id = seed["id"]
        if public_id in existing_tickets:
            report.record_skipped("tickets")
            ticket = session.scalar(
                select(Ticket).where(Ticket.public_id == public_id)
            )
            ticket_ids[public_id] = ticket.id
            continue

        timestamps = _ticket_timestamps(anchor, seed)
        category = seed["category"]
        ticket = Ticket(
            public_id=public_id,
            subject=seed["subject"],
            description=seed["description"],
            requester_id=requester_ids[public_id],
            channel=seed["channel"],
            category=category,
            priority=seed["priority"],
            status=seed["status"],
            assigned_team=CATEGORY_TEAM[category],
            assigned_agent_id=seed["assigned_agent_id"],
            due_at=timestamps["due_at"],
            suggested_category=seed.get("suggested_category", category),
            suggested_priority=seed.get("suggested_priority", seed["priority"]),
            review_note=seed.get("review_note"),
            created_at=timestamps["created_at"],
            updated_at=timestamps["updated_at"],
        )
        session.add(ticket)
        session.flush()
        ticket_ids[public_id] = ticket.id
        existing_tickets.add(public_id)
        report.record_created("tickets")

    # --- Replies --------------------------------------------------------
    reply_ids: dict[str, Any] = {}
    existing_replies = set(session.scalars(select(CustomerReply.public_id)).all())
    for seed in REPLY_SEEDS:
        public_id = seed["id"]
        if public_id in existing_replies:
            report.record_skipped("customer_replies")
            reply = session.scalar(
                select(CustomerReply).where(CustomerReply.public_id == public_id)
            )
            reply_ids[public_id] = reply.id
            continue

        reply = CustomerReply(
            public_id=public_id,
            ticket_id=ticket_ids[seed["ticket_id"]],
            author_id=seed["author_id"],
            body=seed["body"],
            state=seed["state"],
            version=seed["version"],
            submitted_at=anchor - timedelta(hours=seed["submitted_hours_ago"]),
            submitted_version=(
                seed["version"]
                if "submitted_hours_ago" in seed
                else None
            ),
            approved_version=(
                seed["version"]
                if seed["state"]
                in (ReplyState.APPROVED, ReplyState.SENT)
                else None
            ),
            reviewed_at=(
                anchor - timedelta(hours=seed["reviewed_hours_ago"])
                if "reviewed_hours_ago" in seed
                else None
            ),
            reviewer_id=seed.get("reviewer_id"),
            reviewer_name=seed.get("reviewer_name"),
            reviewer_feedback=seed.get("reviewer_feedback"),
            sent_at=(
                anchor - timedelta(hours=seed["sent_hours_ago"])
                if "sent_hours_ago" in seed
                else None
            ),
            sent_by_actor_name=seed.get("sent_by_actor_name"),
            created_at=anchor - timedelta(hours=seed["created_hours_ago"]),
            updated_at=anchor - timedelta(hours=seed["updated_hours_ago"]),
        )
        session.add(reply)
        session.flush()
        reply_ids[public_id] = reply.id
        existing_replies.add(public_id)
        report.record_created("customer_replies")

    # --- Reply revisions (immutable snapshots) ---------------------------
    for seed in REPLY_SEEDS:
        reply_id = reply_ids[seed["id"]]
        revision_id = session.scalar(
            select(ReplyRevision.id).where(
                ReplyRevision.reply_id == reply_id,
                ReplyRevision.version == seed["version"],
            )
        )
        if revision_id is not None:
            report.record_skipped("reply_revisions")
            continue
        session.add(
            ReplyRevision(
                reply_id=reply_id,
                version=seed["version"],
                body=seed["body"],
                author_id=seed["author_id"],
                created_at=anchor - timedelta(hours=seed["created_hours_ago"]),
            )
        )
        session.flush()
        report.record_created("reply_revisions")

    # --- Review decisions (append-only) ----------------------------------
    agent_names = {
        agent_id: name
        for agent_id, name in session.execute(
            select(Agent.id, Agent.name)
        ).all()
    }
    for seed in REVIEW_SEEDS:
        reply_id = reply_ids[seed["reply_id"]]
        revision = session.scalar(
            select(ReplyRevision).where(
                ReplyRevision.reply_id == reply_id,
                ReplyRevision.version == seed["version"],
            )
        )
        if revision is None:  # pragma: no cover - revision loop above
            continue
        existing = session.scalar(
            select(ReplyReview.id).where(
                ReplyReview.reply_id == reply_id,
                ReplyReview.version == seed["version"],
                ReplyReview.decision == seed["decision"],
            )
        )
        if existing is not None:
            report.record_skipped("reply_reviews")
            continue
        session.add(
            ReplyReview(
                reply_id=reply_id,
                revision_id=revision.id,
                version=seed["version"],
                decision=seed["decision"],
                reviewer_id=seed["reviewer_id"],
                reviewer_name=agent_names[seed["reviewer_id"]],
                comment=seed["comment"],
                created_at=anchor - timedelta(hours=seed["hours_ago"]),
            )
        )
        report.record_created("reply_reviews")

    # --- Activity -------------------------------------------------------
    agent_ids_by_name = {
        name: agent_id
        for agent_id, name in session.execute(
            select(Agent.id, Agent.name)
        ).all()
    }
    existing_activities = set(
        session.scalars(select(TicketActivity.public_id)).all()
    )
    for seed in ACTIVITY_SEEDS:
        public_id = seed["id"]
        if public_id in existing_activities:
            report.record_skipped("ticket_activities")
            continue
        session.add(
            TicketActivity(
                public_id=public_id,
                ticket_id=ticket_ids[seed["ticket_id"]],
                reply_id=(
                    reply_ids.get(seed["reply_id"]) if seed.get("reply_id") else None
                ),
                reply_version=1 if seed.get("reply_id") else None,
                actor_id=agent_ids_by_name.get(seed["actor_name"]),
                actor_name=seed["actor_name"],
                actor_type=seed["actor_type"],
                action=seed["action"],
                detail=seed["detail"],
                is_internal_note=seed["action"] is ActivityAction.NOTE_ADDED,
                created_at=anchor - timedelta(hours=seed["hours_ago"]),
            )
        )
        existing_activities.add(public_id)
        report.record_created("ticket_activities")

    session.flush()
    return report
