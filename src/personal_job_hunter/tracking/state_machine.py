"""HITL Application Tracking State Machine and Transition Guardrails."""

from datetime import UTC, datetime
from typing import Any

from personal_job_hunter.domain.models import ApplicationStatus


class InvalidStateTransitionError(Exception):
    """Raised when an illegal lifecycle state transition is attempted."""


# Allowed transition matrix enforcing strict Human-in-the-Loop workflow
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.DISCOVERED: {
        ApplicationStatus.PENDING_HUMAN_REVIEW,
        ApplicationStatus.ARCHIVED,
    },
    ApplicationStatus.PENDING_HUMAN_REVIEW: {
        ApplicationStatus.READY_TO_APPLY,  # Human decision: APPROVE
        ApplicationStatus.REJECTED_BY_HUMAN,  # Human decision: REJECT
        ApplicationStatus.ARCHIVED,
    },
    ApplicationStatus.READY_TO_APPLY: {
        ApplicationStatus.APPLIED,  # Human submitted application
        ApplicationStatus.REJECTED_BY_HUMAN,  # Revoked approval
        ApplicationStatus.ARCHIVED,
    },
    ApplicationStatus.APPLIED: {
        ApplicationStatus.INTERVIEWING,  # Screening / technical rounds
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED_BY_COMPANY,
        ApplicationStatus.ARCHIVED,
    },
    ApplicationStatus.INTERVIEWING: {
        ApplicationStatus.INTERVIEWING,  # Subsequent rounds
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED_BY_COMPANY,
        ApplicationStatus.ARCHIVED,
    },
    ApplicationStatus.OFFER: {
        ApplicationStatus.ARCHIVED,
    },
    ApplicationStatus.REJECTED_BY_COMPANY: {
        ApplicationStatus.ARCHIVED,
    },
    ApplicationStatus.REJECTED_BY_HUMAN: {
        ApplicationStatus.PENDING_HUMAN_REVIEW,  # Re-evaluate
        ApplicationStatus.ARCHIVED,
    },
    ApplicationStatus.ARCHIVED: {
        ApplicationStatus.PENDING_HUMAN_REVIEW,  # Un-archive
    },
}


def validate_state_transition(
    current_status: ApplicationStatus | str,
    new_status: ApplicationStatus | str,
) -> None:
    """Validate whether transitioning from current_status to new_status is permitted.

    Raises:
        InvalidStateTransitionError if the transition violates the HITL workflow.
    """
    curr = (
        current_status
        if isinstance(current_status, ApplicationStatus)
        else ApplicationStatus(current_status)
    )
    target = (
        new_status if isinstance(new_status, ApplicationStatus) else ApplicationStatus(new_status)
    )

    allowed_targets = VALID_TRANSITIONS.get(curr, set())
    if target not in allowed_targets:
        raise InvalidStateTransitionError(
            f"Illegal state transition from '{curr.value}' to '{target.value}'. "
            f"Allowed transitions: {[t.value for t in allowed_targets]}"
        )


def create_transition_event(
    from_status: str,
    to_status: str,
    action: str,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an immutable audit event for an application transition."""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "from_status": from_status,
        "to_status": to_status,
        "action": action,
        "notes": notes or "",
        "metadata": metadata or {},
    }
