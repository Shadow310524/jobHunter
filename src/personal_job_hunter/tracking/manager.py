"""Application Tracking Manager coordinating state transitions and human-in-the-loop actions."""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from personal_job_hunter.db.models import ApplicationModel
from personal_job_hunter.db.repository import ApplicationRepository
from personal_job_hunter.domain.models import ApplicationStatus, CanonicalJobPost, JobMatchResult
from personal_job_hunter.tracking.state_machine import validate_state_transition

logger = logging.getLogger("application_tracker")


class ApplicationTracker:
    """Manages application lifecycle states with strict HITL guardrails."""

    @staticmethod
    def sync_pipeline_jobs(
        session: Session,
        jobs: list[CanonicalJobPost],
        match_results: list[JobMatchResult],
    ) -> int:
        """Seed/sync application records for pipeline jobs that pass review threshold."""
        synced_count = 0
        for match_res in match_results:
            # Only create review items for non-SKIP jobs (APPLY or STRETCH)
            if match_res.recommendation != "SKIP":
                ApplicationRepository.create_or_get_application(
                    session=session,
                    canonical_id=match_res.canonical_id,
                    initial_status=ApplicationStatus.PENDING_HUMAN_REVIEW.value,
                )
                synced_count += 1
        session.flush()
        return synced_count

    @staticmethod
    def approve_for_apply(
        session: Session, canonical_id: str, notes: str | None = None
    ) -> ApplicationModel:
        """Human decision: Approve job for application (READY_TO_APPLY)."""
        app = ApplicationRepository.get_application(session, canonical_id)
        if not app:
            app = ApplicationRepository.create_or_get_application(session, canonical_id)

        validate_state_transition(app.status, ApplicationStatus.READY_TO_APPLY)

        return ApplicationRepository.update_status(
            session=session,
            canonical_id=canonical_id,
            new_status=ApplicationStatus.READY_TO_APPLY.value,
            action="HUMAN_APPROVED",
            human_feedback="APPROVE",
            notes=notes or "Approved during human review. Ready for application submission.",
        )

    @staticmethod
    def reject_by_human(
        session: Session, canonical_id: str, reason: str | None = None
    ) -> ApplicationModel:
        """Human decision: Reject job (REJECTED_BY_HUMAN / CLOSED)."""
        app = ApplicationRepository.get_application(session, canonical_id)
        if not app:
            app = ApplicationRepository.create_or_get_application(session, canonical_id)

        validate_state_transition(app.status, ApplicationStatus.REJECTED_BY_HUMAN)

        return ApplicationRepository.update_status(
            session=session,
            canonical_id=canonical_id,
            new_status=ApplicationStatus.REJECTED_BY_HUMAN.value,
            action="HUMAN_REJECTED",
            human_feedback="REJECT",
            notes=reason or "Rejected by candidate during review.",
        )

    @staticmethod
    def mark_as_applied(
        session: Session,
        canonical_id: str,
        notes: str | None = None,
        applied_at: datetime | None = None,
    ) -> ApplicationModel:
        """Human action: Record that the application was submitted (APPLIED)."""
        app = ApplicationRepository.get_application(session, canonical_id)
        if not app:
            raise ValueError(f"No application record found for canonical ID '{canonical_id}'")

        validate_state_transition(app.status, ApplicationStatus.APPLIED)

        submission_time = applied_at or datetime.now(UTC)
        return ApplicationRepository.update_status(
            session=session,
            canonical_id=canonical_id,
            new_status=ApplicationStatus.APPLIED.value,
            action="HUMAN_SUBMITTED_APPLICATION",
            applied_at=submission_time,
            notes=notes or "Application submitted manually by candidate.",
        )

    @staticmethod
    def schedule_interview(
        session: Session,
        canonical_id: str,
        interview_date: datetime | None = None,
        notes: str | None = None,
    ) -> ApplicationModel:
        """Record scheduled interview round (INTERVIEWING)."""
        app = ApplicationRepository.get_application(session, canonical_id)
        if not app:
            raise ValueError(f"No application record found for canonical ID '{canonical_id}'")

        validate_state_transition(app.status, ApplicationStatus.INTERVIEWING)

        return ApplicationRepository.update_status(
            session=session,
            canonical_id=canonical_id,
            new_status=ApplicationStatus.INTERVIEWING.value,
            action="INTERVIEW_SCHEDULED",
            interview_date=interview_date,
            notes=notes or "Interview scheduled.",
        )

    @staticmethod
    def record_offer(
        session: Session, canonical_id: str, notes: str | None = None
    ) -> ApplicationModel:
        """Record job offer received (OFFER)."""
        app = ApplicationRepository.get_application(session, canonical_id)
        if not app:
            raise ValueError(f"No application record found for canonical ID '{canonical_id}'")

        validate_state_transition(app.status, ApplicationStatus.OFFER)

        return ApplicationRepository.update_status(
            session=session,
            canonical_id=canonical_id,
            new_status=ApplicationStatus.OFFER.value,
            action="OFFER_RECEIVED",
            notes=notes or "Job offer received!",
        )

    @staticmethod
    def record_company_rejection(
        session: Session, canonical_id: str, notes: str | None = None
    ) -> ApplicationModel:
        """Record company rejection received (REJECTED_BY_COMPANY)."""
        app = ApplicationRepository.get_application(session, canonical_id)
        if not app:
            raise ValueError(f"No application record found for canonical ID '{canonical_id}'")

        validate_state_transition(app.status, ApplicationStatus.REJECTED_BY_COMPANY)

        return ApplicationRepository.update_status(
            session=session,
            canonical_id=canonical_id,
            new_status=ApplicationStatus.REJECTED_BY_COMPANY.value,
            action="COMPANY_REJECTED",
            notes=notes or "Company closed requisition or sent rejection.",
        )
