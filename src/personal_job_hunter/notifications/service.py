"""Notification service implementations ($0.00 cost local/console/file)."""

import json
import logging
from pathlib import Path

from personal_job_hunter.notifications.base import BaseNotificationService, NotificationEvent

logger = logging.getLogger("notifications")


class ConsoleNotificationService:
    """Delivers human-readable alerts directly to the console/stdout."""

    def notify(self, event: NotificationEvent) -> bool:
        """Print stylized event alert to console."""
        print(f"\n[NOTIFICATION] [{event.event_type.value}] {event.title}")
        print(f"  {event.message}")
        if event.link:
            print(f"  Link: {event.link}")
        return True


class FileLogNotificationService:
    """Appends JSON event alerts to a local audit file."""

    def __init__(self, log_path: Path | str = Path("data/notifications.jsonl")) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def notify(self, event: NotificationEvent) -> bool:
        """Append event to file."""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")
            return True
        except Exception as e:
            logger.warning("Failed to write notification to %s: %s", self.log_path, e)
            return False


class CompositeNotificationService:
    """Dispatches notifications to multiple registered handlers."""

    def __init__(self, services: list[BaseNotificationService]) -> None:
        self.services = services

    def notify(self, event: NotificationEvent) -> bool:
        success = True
        for svc in self.services:
            try:
                res = svc.notify(event)
                if not res:
                    success = False
            except Exception as e:
                logger.warning("Notification handler %s failed: %s", type(svc).__name__, e)
                success = False
        return success


def get_default_notification_service() -> BaseNotificationService:
    """Factory returning composite console + file notification service."""
    return CompositeNotificationService(
        [
            ConsoleNotificationService(),
            FileLogNotificationService(),
        ]
    )
