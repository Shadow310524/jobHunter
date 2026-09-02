"""Unit tests for FastAPI endpoints, schemas, filtering, and HITL actions."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from personal_job_hunter.api.app import app
from personal_job_hunter.api.dependencies import get_db
from personal_job_hunter.db.models import Base
from personal_job_hunter.db.repository import (
    ApplicationRepository,
    EnrichmentRepository,
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


@pytest.fixture
def client_and_session() -> Generator[tuple[TestClient, Session], None, None]:
    """Provide TestClient with in-memory database override."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    session = Session(bind=test_engine)

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db

    # Seed test data
    profile = CandidateProfile()
    ProfileRepository.save_profile(session, profile)

    job1 = CanonicalJobPost(
        canonical_id="job_api_1",
        title="AI Engineer",
        company="Databricks",
        location="Bengaluru, India",
        work_mode=WorkMode.REMOTE,
        is_remote=True,
        description="Build LLM platform systems with Python and FastAPI.",
        inferred_skills=["Python", "FastAPI", "LLM"],
        sources=[JobSource.GREENHOUSE],
        application_urls=["https://databricks.com/apply/1"],
    )
    job2 = CanonicalJobPost(
        canonical_id="job_api_2",
        title="Support Engineer",
        company="Databricks",
        location="Bengaluru, India",
        work_mode=WorkMode.ONSITE,
        is_remote=False,
        description="Sustaining support engineering.",
        inferred_skills=["Support"],
        sources=[JobSource.GREENHOUSE],
        application_urls=["https://databricks.com/apply/2"],
    )
    JobRepository.upsert_canonical_jobs_batch(session, [job1, job2])

    match1 = JobMatchResult(
        canonical_id="job_api_1",
        job_title=job1.title,
        company=job1.company,
        location=job1.location,
        recommendation=MatchRecommendation.APPLY,
        overall_score=92.5,
        breakdown=MatchBreakdown(overall_score=92.5, role_score=100.0),
    )
    match2 = JobMatchResult(
        canonical_id="job_api_2",
        job_title=job2.title,
        company=job2.company,
        location=job2.location,
        recommendation=MatchRecommendation.SKIP,
        overall_score=35.0,
        breakdown=MatchBreakdown(overall_score=35.0, role_score=35.0),
    )
    JobRepository.save_match_scores_batch(session, [match1, match2])

    # Add enrichment
    EnrichmentRepository.upsert_enrichment(
        session=session,
        canonical_id="job_api_1",
        model_name="gemini-1.5-flash",
        model_version="1.5",
        prompt_version="v1.0",
        content_hash="hash_123",
        enrichment_data={
            "job_summary": "Databricks AI platform role.",
            "candidate_strengths": ["Strong Python & FastAPI experience."],
            "gap_analysis": [],
            "interview_talking_points": ["Discuss AVASOFT internship."],
        },
    )

    # Initialize tracking
    ApplicationRepository.create_or_get_application(
        session, "job_api_1", initial_status=ApplicationStatus.PENDING_HUMAN_REVIEW.value
    )
    session.commit()

    with TestClient(app) as test_client:
        yield test_client, session

    app.dependency_overrides.clear()
    session.close()


def test_get_stats_endpoint(client_and_session: tuple[TestClient, Session]) -> None:
    """Verify GET /api/stats returns accurate aggregated metrics."""
    client, _ = client_and_session
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_canonical_jobs"] == 2
    assert data["recommendations_breakdown"]["APPLY"] == 1
    assert data["recommendations_breakdown"]["SKIP"] == 1


def test_list_jobs_and_filtering(client_and_session: tuple[TestClient, Session]) -> None:
    """Verify GET /api/jobs with recommendation and search filters."""
    client, _ = client_and_session

    # 1. Filter by recommendation=APPLY
    resp_apply = client.get("/api/jobs?recommendation=APPLY")
    assert resp_apply.status_code == 200
    jobs = resp_apply.json()
    assert len(jobs) == 1
    assert jobs[0]["canonical_id"] == "job_api_1"

    # 2. Search query
    resp_search = client.get("/api/jobs?search=Support")
    assert resp_search.status_code == 200
    assert len(resp_search.json()) == 1
    assert resp_search.json()[0]["canonical_id"] == "job_api_2"


def test_get_job_detail_and_enrichment(client_and_session: tuple[TestClient, Session]) -> None:
    """Verify GET /api/jobs/{id} and /enrichment."""
    client, _ = client_and_session

    resp = client.get("/api/jobs/job_api_1")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["title"] == "AI Engineer"
    assert detail["match_score"]["recommendation"] == "APPLY"
    assert detail["enrichment"]["job_summary"] == "Databricks AI platform role."

    resp_enr = client.get("/api/jobs/job_api_1/enrichment")
    assert resp_enr.status_code == 200
    assert "candidate_strengths" in resp_enr.json()


def test_application_lifecycle_actions_via_api(
    client_and_session: tuple[TestClient, Session],
) -> None:
    """Verify human review approve -> mark applied -> interview -> offer lifecycle."""
    client, _ = client_and_session

    # Step 1: Approve -> READY_TO_APPLY
    resp_app = client.post(
        "/api/applications/job_api_1/approve", json={"notes": "Approved by candidate."}
    )
    assert resp_app.status_code == 200
    assert resp_app.json()["status"] == "READY_TO_APPLY"

    # Step 2: Mark Applied -> APPLIED
    resp_applied = client.post(
        "/api/applications/job_api_1/mark-applied",
        json={"notes": "Submitted on company portal."},
    )
    assert resp_applied.status_code == 200
    assert resp_applied.json()["status"] == "APPLIED"

    # Step 3: Interview Scheduled -> INTERVIEWING
    resp_int = client.post(
        "/api/applications/job_api_1/interview",
        json={"notes": "Technical Round 1 scheduled."},
    )
    assert resp_int.status_code == 200
    assert resp_int.json()["status"] == "INTERVIEWING"

    # Step 4: Offer Received -> OFFER
    resp_off = client.post(
        "/api/applications/job_api_1/offer", json={"notes": "Offer letter received!"}
    )
    assert resp_off.status_code == 200
    assert resp_off.json()["status"] == "OFFER"


def test_illegal_state_transition_prevention_via_api(
    client_and_session: tuple[TestClient, Session],
) -> None:
    """Verify attempting to directly mark applied from review raises 400 Bad Request."""
    client, _ = client_and_session

    # Attempting to mark as applied while still in PENDING_HUMAN_REVIEW
    resp = client.post(
        "/api/applications/job_api_1/mark-applied", json={"notes": "Bypassing approval"}
    )
    assert resp.status_code == 400
    assert "Illegal state transition" in resp.json()["detail"]


def test_review_inbox_endpoint(client_and_session: tuple[TestClient, Session]) -> None:
    """Verify GET /api/jobs/review returns pending jobs."""
    client, _ = client_and_session
    resp = client.get("/api/jobs/review")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["canonical_id"] == "job_api_1"
