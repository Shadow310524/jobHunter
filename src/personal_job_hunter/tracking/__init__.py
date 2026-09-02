"""Application tracking package: HITL review, lifecycle state machine, and CLI."""

from personal_job_hunter.tracking.cli import (
    list_applications_by_status_cli,
    print_status_summary,
    review_inbox_cli,
)
from personal_job_hunter.tracking.manager import ApplicationTracker
from personal_job_hunter.tracking.state_machine import (
    VALID_TRANSITIONS,
    InvalidStateTransitionError,
    create_transition_event,
    validate_state_transition,
)

__all__ = [
    "VALID_TRANSITIONS",
    "ApplicationTracker",
    "InvalidStateTransitionError",
    "create_transition_event",
    "list_applications_by_status_cli",
    "print_status_summary",
    "review_inbox_cli",
    "validate_state_transition",
]
