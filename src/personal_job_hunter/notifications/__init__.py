"""Notification package: alerting protocols, events, and services."""

from personal_job_hunter.notifications.base import (
    BaseNotificationService,
    NotificationEvent,
    NotificationType,
)
from personal_job_hunter.notifications.service import (
    CompositeNotificationService,
    ConsoleNotificationService,
    FileLogNotificationService,
    get_default_notification_service,
)

__all__ = [
    "BaseNotificationService",
    "CompositeNotificationService",
    "ConsoleNotificationService",
    "FileLogNotificationService",
    "NotificationEvent",
    "NotificationType",
    "get_default_notification_service",
]
