"""QueueStorm — customer-support ticket classifier.

A small FastAPI service that classifies one CRM ticket at a time and returns
a JSON verdict. Rules-based, no LLM, no GPU. See PUKU.md for the full brief.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums (must match exactly per PUKU.md / §4 of the brief)
# ---------------------------------------------------------------------------

CaseType = Literal[
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "phishing_or_social_engineering",
    "other",
]

Severity = Literal["low", "medium", "high", "critical"]

Department = Literal[
    "customer_support",
    "dispute_resolution",
    "payments_ops",
    "fraud_risk",
]

Channel = Literal["app", "sms", "call_center", "merchant_portal"]
Locale = Literal["bn", "en", "mixed"]

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class Ticket(BaseModel):
    ticket_id: str = Field(..., min_length=1)
    channel: Optional[Channel] = None
    locale: Optional[Locale] = None
    message: str = Field(..., min_length=1)


class Classification(BaseModel):
    ticket_id: str
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    human_review_required: bool
    confidence: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Safety rule — agent_summary must NEVER request PIN / OTP / password / card
# ---------------------------------------------------------------------------

_SAFETY_FORBIDDEN_PHRASES = (
    "send me your pin",
    "send me your otp",
    "send me your password",
    "send me your card",
    "share your pin",
    "share your otp",
    "share your password",
    "share your card",
    "provide your pin",
    "provide your otp",
    "provide your password",
    "provide your card number",
    "provide your cvv",
    "tell me your pin",
    "tell me your otp",
    "tell me your password",
    "tell me your card",
    "give me your pin",
    "give me your otp",
    "give me your password",
    "give me your card",
)


def _safety_check(summary: str) -> None:
    """Hard reject any summary that asks the customer for sensitive data."""
    lowered = summary.lower()
    for phrase in _SAFETY_FORBIDDEN_PHRASES:
        if phrase in lowered:
            raise HTTPException(
                status_code=500,
                detail=f"Safety rule violated: summary asks for forbidden phrase '{phrase}'",
            )


# ---------------------------------------------------------------------------
# Keyword-based classifier
# ---------------------------------------------------------------------------

# High-signal phrases ordered by priority. Order matters — earlier rules win
# because they have the strongest signal (e.g. phishing > wrong_transfer).
_RULES: list[tuple[CaseType, re.Pattern[str]]] = [
    # Phishing / social engineering — critical, always highest priority.
    (
        "phishing_or_social_engineering",
        re.compile(
            r"(otp|pin|password|cvv|card\s*number|one[\s-]?time\s*password|"
            r"verification\s*code|security\s*code|share\s*(your|the)\s*(otp|pin|password|code)|"
            r"bksh?|nagad|rocket|bank\s*agent|customer\s*care\s*officer|"
            r"click\s*(this|the)\s*link|kyc\s*update|account\s*(will\s*be|has\s*been)\s*(blocked|suspended|locked)|"
            r"ওটিপি|পিন|পাসওয়ার্ড|ভেরিফিকেশন\s*কোড|"
            r"বিকাশ|নগদ|রকেট|"
            r"কাস্টমার\s*কেয়ার|"
            r"অ্যাকাউন্ট\s*(ব্লক|সাসপেন্ড))",
            re.IGNORECASE,
        ),
    ),
    # Wrong transfer — money to the wrong recipient.
    (
        "wrong_transfer",
        re.compile(
            r"(wrong\s*(number|account|recipient|person|number\s*typo|নম্বরে|নাম্বারে|অ্যাকাউন্টে)|"
            r"sent\s*to\s*(the\s*)?wrong|"
            r"transferred?\s*to\s*(the\s*)?wrong|"
            r"mistaken(?:ly)?\s*sent|"
            r"sent\s*by\s*mistake|"
            r"sent\s*to\s*wrong\s*number|"
            r"transfer(ed)?\s*to\s*a?\s*wrong|"
            r"ভুল\s*(নম্বরে|নাম্বারে|অ্যাকাউন্টে|জনে)|"
            r"ভুলভাবে\s*(পাঠি|টাকা)|"
            r"wrong\s*transfer)",
            re.IGNORECASE,
        ),
    ),
    # Payment failed but balance deducted — payments_ops, high severity.
    (
        "payment_failed",
        re.compile(
            r"(payment\s*failed|transaction\s*failed|failed\s*but\s*(balance|amount|money)\s*(was\s*)?(deducted|debited|charged)|"
            r"balance\s*(was\s*)?(deducted|debited|charged)\s*but|"
            r"amount\s*(was\s*)?(deducted|debited)\s*but|"
            r"money\s*(was\s*)?(deducted|taken|charged)\s*but|"
            r"double\s*(charged|debited|deducted)|"
            r"charged\s*twice|"
            r"shows\s*deducted|"
            r"but\s*i\s*didn'?t\s*receive|"
            r"পেমেন্ট\s*ব্যর্থ|"
            r"টাকা\s*(কেটে|কাটা|কেটে\s*নিয়ে|কেটে\s*ফেল)\s*(হয়ে\s*)?(গেছে|গেছে\s*কিন্তু)|"
            r"টাকা\s*কাটা\s*হয়ে\s*গেছে)",
            re.IGNORECASE,
        ),
    ),
    # Refund request — customer wants money back.
    (
        "refund_request",
        re.compile(
            r"(refund|return\s*(my|the)\s*money|please\s*refund|i\s*want\s*(my\s*money\s*back|a\s*refund)|"
            r"money\s*back|reimburse|"
            r"cancel\s*(and\s*refund|my\s*order|the\s*order)|"
            r"i\s*changed\s*my\s*mind|"
            r"টাকা\s*(ফেরত|ফেরত\s*দিন|ফেরত\s*চাই)|"
            r"রিফান্ড)",
            re.IGNORECASE,
        ),
    ),
]

_DEFAULT_CONFIDENCE = 0.6  # used when no rule matches and we fall back to "other"


def classify_case_type(message: str) -> tuple[CaseType, float]:
    """Return (case_type, confidence). Confidence reflects rule strength."""
    for case_type, pattern in _RULES:
        m = pattern.search(message)
        if m:
            # Stronger / earlier rules get a higher confidence.
            if case_type == "phishing_or_social_engineering":
                confidence = 0.95
            elif case_type == "wrong_transfer":
                confidence = 0.92
            elif case_type == "payment_failed":
                confidence = 0.9
            else:  # refund_request
                confidence = 0.88
            return case_type, confidence
    return "other", _DEFAULT_CONFIDENCE


def severity_for(case_type: CaseType, message: str) -> Severity:
    """Pick severity from case_type + message cues."""
    if case_type == "phishing_or_social_engineering":
        return "critical"
    if case_type == "wrong_transfer":
        # Larger amounts or explicit urgency bump to high; default to high.
        amount_match = re.search(
            r"\b([0-9]{2,7})\s*(taka|tk|BDT|inr|rs|rupees?)?\b", message, re.IGNORECASE
        )
        if amount_match:
            try:
                amount = int(amount_match.group(1))
                if amount >= 1000:
                    return "high"
            except ValueError:
                pass
        return "high"
    if case_type == "payment_failed":
        return "high"
    if case_type == "refund_request":
        return "low"
    # other: app crashes / minor issues → low; anything with urgency → medium
    if re.search(r"(urgent(?:ly)?|immediately|asap|right\s*now|তাড়াতাড়ি|এখনই)", message, re.IGNORECASE):
        return "medium"
    return "low"


def department_for(case_type: CaseType) -> Department:
    if case_type == "wrong_transfer":
        return "dispute_resolution"
    if case_type == "payment_failed":
        return "payments_ops"
    if case_type == "phishing_or_social_engineering":
        return "fraud_risk"
    return "customer_support"


def _neutral_summary(case_type: CaseType, severity: Severity) -> str:
    """One or two neutral sentences describing the ticket.

    Intentionally avoids asking the customer for anything — the safety rule
    forbids requesting PIN/OTP/password/card numbers in this field.
    """
    if case_type == "wrong_transfer":
        return (
            "Customer reports that funds were sent to an unintended recipient. "
            "Dispute resolution has been notified and will contact the customer."
        )
    if case_type == "payment_failed":
        return (
            "Customer reports a failed transaction with the balance appearing as deducted. "
            "Payments operations will verify the ledger and respond."
        )
    if case_type == "refund_request":
        return (
            "Customer is requesting a refund for a recent transaction. "
            "Customer support will review and follow up."
        )
    if case_type == "phishing_or_social_engineering":
        return (
            "Customer reports a suspicious interaction where sensitive credentials were solicited. "
            "Fraud risk has been escalated for human review."
        )
    # other
    return (
        "Customer reports a general app or service issue. "
        "Customer support will triage and respond."
    )


def human_review_required(case_type: CaseType, severity: Severity) -> bool:
    return severity == "critical" or case_type == "phishing_or_social_engineering"


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="QueueStorm", version="1.0.0")


@app.get("/health")
def health() -> dict:
    """Liveness probe — must respond within 10 seconds per the brief."""
    return {"status": "ok", "service": "queuestorm"}


@app.post("/sort-ticket", response_model=Classification)
def sort_ticket(ticket: Ticket) -> Classification:
    case_type, confidence = classify_case_type(ticket.message)
    severity = severity_for(case_type, ticket.message)
    department = department_for(case_type)
    summary = _neutral_summary(case_type, severity)
    _safety_check(summary)
    review = human_review_required(case_type, severity)

    return Classification(
        ticket_id=ticket.ticket_id,
        case_type=case_type,
        severity=severity,
        department=department,
        agent_summary=summary,
        human_review_required=review,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Static frontend — served from ./static at the site root.
# ---------------------------------------------------------------------------

import os

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))