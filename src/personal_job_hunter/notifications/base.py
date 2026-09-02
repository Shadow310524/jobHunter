"""Notification service protocol and payload schemas."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class NotificationType(StrEnum):
    """Event types triggering notifications."""

    NEW_HIGH_PRIORITY_JOB = "NEW_HIGH_PRIORITY_JOB"
    REVIEW_INBOX_PENDING = "REVIEW_INBOX_PENDING"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    OFFER_RECEIVED = "OFFER_RECEIVED"
    PIPELINE_COMPLETED = "PIPELINE_COMPLETED"


class NotificationEvent(BaseModel):
    """Payload representing an actionable event notification."""

    event_type: NotificationType
    title: str
    message: str
    link: str | None = None
    canonical_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BaseNotificationService(Protocol):
    """Protocol defining notification delivery contracts."""

    def notify(self, event: NotificationEvent) -> bool:
        """Deliver a notification event."""
        ...
