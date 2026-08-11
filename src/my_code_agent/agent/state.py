from enum import StrEnum
from typing import TypedDict

from pydantic import BaseModel


class Intent(StrEnum):
    BILLING = "billing"
    QUESTION = "question"
    BUG = "bug"
    FEATURE = "feature"
    COMPLEX = "complex"


class Urgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NodeName(StrEnum):
    """LangGraph node names used as goto targets."""
    SEARCH_DOCUMENT = "search_document"
    HUMAN_REVIEW = "human_review"
    BUG_TRACKING = "bug_tracking"
    DRAFT_RESPONSE = "draft_response"
    SEND_REPLY = "send_reply"
    READ_EMAIL = "read_email"
    CLASSIFY_INTENT = "classify_intent"



class EmailClassification(BaseModel):
    intent: Intent
    urgency: Urgency
    topic: str
    summary: str



class EmailAgentState(BaseModel):
    sender_email: str
    email_content: str
    email_id: str

    classification: EmailClassification | None

    # search results
    search_results: list[str] | None
    customer_history: dict | None

    # generated content
    draft_response: str | None
    message: list[str] | None


