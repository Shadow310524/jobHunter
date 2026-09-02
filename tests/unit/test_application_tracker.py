"""Unit tests for HITL application tracking, state machine transitions, and review inbox."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from personal_job_hunter.db.models import Base
from personal_job_hunter.db.repository import (
    ApplicationRepository,
    JobRepository,
    ProfileRepository,
)
from personal_job_hunter.domain.models import (
    ApplicationStatus,
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
    JobSource,
    MatchBreakdown,
    MatchRecommendation,
    WorkMode,
)
from personal_job_hunter.tracking.manager import ApplicationTracker
from personal_job_hunter.tracking.state_machine import (
    InvalidStateTransitionError,
    validate_state_transition,
)


@pytest.fixture
def test_db_session() -> Generator[Session, None, None]:
    """Provide isolated in-memory DB session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


def create_sample_job(canonical_id: str = "canon_track_1") -> CanonicalJobPost:
    return CanonicalJobPost(
        canonical_id=canonical_id,
        title="AI Platform Engineer",
        company="Databricks",
        location="Bengaluru, India",
        work_mode=WorkMode.HYBRID,
        description="Build LLM agents.",
        sources=[JobSource.GREENHOUSE],
        application_urls=["https://example.com/apply"],
    )


def test_state_machine_valid_and_invalid_transitions() -> None:
    """Verify state machine strictly enforces HITL workflow transitions."""
    # Valid linear lifecycle
    validate_state_transition(
        ApplicationStatus.PENDING_HUMAN_REVIEW, ApplicationStatus.READY_TO_APPLY
    )
    validate_state_transition(ApplicationStatus.READY_TO_APPLY, ApplicationStatus.APPLIED)
    validate_state_transition(ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEWING)
    validate_state_transition(ApplicationStatus.INTERVIEWING, ApplicationStatus.OFFER)

    # Invalid jump transitions (e.g. auto-submitting without human approval)
    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(ApplicationStatus.PENDING_HUMAN_REVIEW, ApplicationStatus.APPLIED)

    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(ApplicationStatus.DISCOVERED, ApplicationStatus.OFFER)


def test_pipeline_job_sync_and_review_inbox(test_db_session: Session) -> None:
    """Verify pipeline syncs eligible jobs to review inbox while excluding SKIP jobs."""
    profile = CandidateProfile()
    job1 = create_sample_job(canonical_id="job_apply")
    job2 = create_sample_job(canonical_id="job_skip")

    ProfileRepository.save_profile(test_db_session, profile, profile_id="default")
    JobRepository.upsert_canonical_jobs_batch(test_db_session, [job1, job2])

    match1 = JobMatchResult(
        canonical_id="job_apply",
        job_title="AI Platform Engineer",
        company="Databricks",
        location="Bengaluru",
        recommendation=MatchRecommendation.APPLY,
        overall_score=92.0,
        breakdown=MatchBreakdown(overall_score=92.0),
    )
    match2 = JobMatchResult(
        canonical_id="job_skip",
        job_title="Support Engineer",
        company="Databricks",
        location="Bengaluru",
        recommendation=MatchRecommendation.SKIP,
        overall_score=35.0,
        breakdown=MatchBreakdown(overall_score=35.0),
    )
    JobRepository.save_match_scores_batch(test_db_session, [match1, match2])

    # Sync
    synced = ApplicationTracker.sync_pipeline_jobs(test_db_session, [job1, job2], [match1, match2])
    test_db_session.commit()

    assert synced == 1  # Only job_apply was synced

    inbox = ApplicationRepository.get_review_inbox(test_db_session)
    assert len(inbox) == 1
    assert inbox[0][1].canonical_id == "job_apply"
    assert inbox[0][0].status == ApplicationStatus.PENDING_HUMAN_REVIEW.value


def test_human_approval_to_applied_to_offer_workflow(test_db_session: Session) -> None:
    """Verify complete end-to-end human review and lifecycle tracking."""
    job = create_sample_job(canonical_id="job_workflow_1")
    JobRepository.upsert_canonical_job(test_db_session, job)
    test_db_session.commit()

    # Step 1: Initial state is PENDING_HUMAN_REVIEW
    app = ApplicationRepository.create_or_get_application(test_db_session, "job_workflow_1")
    assert app.status == ApplicationStatus.PENDING_HUMAN_REVIEW.value

    # Step 2: Human Approves -> READY_TO_APPLY
    app_approved = ApplicationTracker.approve_for_apply(
        test_db_session, "job_workflow_1", notes="Looks fantastic!"
    )
    test_db_session.commit()
    assert app_approved.status == ApplicationStatus.READY_TO_APPLY.value
    assert app_approved.human_feedback == "APPROVE"

    # Step 3: Human Submits Application -> APPLIED
    now = datetime.now(UTC)
    app_applied = ApplicationTracker.mark_as_applied(
        test_db_session, "job_workflow_1", notes="Applied on company portal.", applied_at=now
    )
    test_db_session.commit()
    assert app_applied.status == ApplicationStatus.APPLIED.value
    assert app_applied.applied_at is not None

    # Step 4: Schedule Interview -> INTERVIEWING
    app_interview = ApplicationTracker.schedule_interview(
        test_db_session, "job_workflow_1", interview_date=now, notes="Round 1 with Hiring Manager."
    )
    test_db_session.commit()
    assert app_interview.status == ApplicationStatus.INTERVIEWING.value
    assert app_interview.interview_date is not None

    # Step 5: Offer Received -> OFFER
    app_offer = ApplicationTracker.record_offer(
        test_db_session, "job_workflow_1", notes="Offer letter received!"
    )
    test_db_session.commit()
    assert app_offer.status == ApplicationStatus.OFFER.value
    assert len(app_offer.events_log) >= 5  # Audited transitions


def test_human_rejection_workflow(test_db_session: Session) -> None:
    """Verify candidate rejection moves job to REJECTED_BY_HUMAN."""
    job = create_sample_job(canonical_id="job_reject_1")
    JobRepository.upsert_canonical_job(test_db_session, job)
    test_db_session.commit()

    app_rejected = ApplicationTracker.reject_by_human(
        test_db_session, "job_reject_1", reason="Requires non-India relocation."
    )
    test_db_session.commit()
    assert app_rejected.status == ApplicationStatus.REJECTED_BY_HUMAN.value
    assert app_rejected.human_feedback == "REJECT"


def test_application_stats_aggregation(test_db_session: Session) -> None:
    """Verify application statistics summary aggregation."""
    j1 = create_sample_job(canonical_id="j1")
    j2 = create_sample_job(canonical_id="j2")
    j3 = create_sample_job(canonical_id="j3")
    JobRepository.upsert_canonical_jobs_batch(test_db_session, [j1, j2, j3])
    test_db_session.commit()

    ApplicationTracker.approve_for_apply(test_db_session, "j1")
    ApplicationTracker.reject_by_human(test_db_session, "j2")
    ApplicationRepository.create_or_get_application(test_db_session, "j3")
    test_db_session.commit()

    stats = ApplicationRepository.get_application_stats(test_db_session)
    assert stats.get(ApplicationStatus.READY_TO_APPLY.value) == 1
    assert stats.get(ApplicationStatus.REJECTED_BY_HUMAN.value) == 1
    assert stats.get(ApplicationStatus.PENDING_HUMAN_REVIEW.value) == 1
