"""Unit tests for database repositories, idempotency, and transactional persistence."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from personal_job_hunter.db.models import Base
from personal_job_hunter.db.persistence import persist_pipeline_to_database
from personal_job_hunter.db.repository import JobRepository, ProfileRepository
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
    JobSource,
    MatchBreakdown,
    MatchRecommendation,
    SourceProvenance,
    WorkMode,
)


@pytest.fixture
def in_memory_session() -> Generator[Session, None, None]:
    """Fixture providing a fresh in-memory database session for test isolation."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


def test_profile_repository_save_and_update(in_memory_session: Session) -> None:
    """Verify candidate profile insert and idempotent update."""
    profile = CandidateProfile(name="Harish Renganathan", cgpa=8.2)
    saved = ProfileRepository.save_profile(in_memory_session, profile, profile_id="default")
    in_memory_session.commit()

    assert saved.name == "Harish Renganathan"
    assert saved.cgpa == 8.2

    # Update profile
    profile.cgpa = 8.5
    updated = ProfileRepository.save_profile(in_memory_session, profile, profile_id="default")
    in_memory_session.commit()

    assert updated.cgpa == 8.5
    fetched = ProfileRepository.get_profile(in_memory_session, "default")
    assert fetched is not None
    assert fetched.cgpa == 8.5


def test_canonical_job_upsert_and_provenance_idempotency(in_memory_session: Session) -> None:
    """Verify canonical job upsert and provenance sync prevents duplicate records."""
    prov1 = SourceProvenance(
        source=JobSource.GREENHOUSE,
        source_job_id="gh_101",
        job_url="https://example.com/101",
        official_application_url="https://example.com/101/apply",
        raw_metadata={"dept": "AI"},
    )
    job = CanonicalJobPost(
        canonical_id="canon_101",
        title="AI Engineer",
        company="Databricks",
        location="Bengaluru, India",
        work_mode=WorkMode.HYBRID,
        description="Initial short description.",
        inferred_skills=["Python", "PyTorch"],
        sources=[JobSource.GREENHOUSE],
        source_records=[prov1],
        application_urls=["https://example.com/101/apply"],
    )

    # First insert
    JobRepository.upsert_canonical_job(in_memory_session, job)
    in_memory_session.commit()

    saved = JobRepository.get_canonical_job(in_memory_session, "canon_101")
    assert saved is not None
    assert saved.title == "AI Engineer"
    assert len(saved.source_records) == 1

    # Second upsert with updated description and added provenance
    prov2 = SourceProvenance(
        source=JobSource.LEVER,
        source_job_id="lever_202",
        job_url="https://lever.co/202",
        official_application_url="https://lever.co/202/apply",
    )
    job.description = "Much longer updated description with more details."
    job.source_records.append(prov2)
    job.sources.append(JobSource.LEVER)

    JobRepository.upsert_canonical_job(in_memory_session, job)
    in_memory_session.commit()

    updated = JobRepository.get_canonical_job(in_memory_session, "canon_101")
    assert updated is not None
    assert updated.description == "Much longer updated description with more details."
    # Exactly 2 provenance records, no duplicates
    assert len(updated.source_records) == 2

    # Re-running the exact same upsert does NOT create duplicate provenance rows
    JobRepository.upsert_canonical_job(in_memory_session, job)
    in_memory_session.commit()

    rechecked = JobRepository.get_canonical_job(in_memory_session, "canon_101")
    assert rechecked is not None
    assert len(rechecked.source_records) == 2


def test_match_score_persistence_and_queries(in_memory_session: Session) -> None:
    """Verify match score persistence and ranked job queries."""
    # Create profile and job first
    ProfileRepository.save_profile(in_memory_session, CandidateProfile(), profile_id="default")
    job1 = CanonicalJobPost(
        canonical_id="canon_1",
        title="AI Platform Engineer",
        company="Supabase",
        location="Remote, Global",
        description="Desc 1",
        sources=[JobSource.ASHBY],
    )
    job2 = CanonicalJobPost(
        canonical_id="canon_2",
        title="Python Engineer",
        company="Canonical",
        location="Bengaluru",
        description="Desc 2",
        sources=[JobSource.GREENHOUSE],
    )
    JobRepository.upsert_canonical_jobs_batch(in_memory_session, [job1, job2])

    # Save scores
    score1 = JobMatchResult(
        canonical_id="canon_1",
        job_title="AI Platform Engineer",
        company="Supabase",
        location="Remote, Global",
        recommendation=MatchRecommendation.APPLY,
        overall_score=95.0,
        breakdown=MatchBreakdown(
            technical_score=100.0,
            role_score=100.0,
            experience_score=90.0,
            location_score=80.0,
            overall_score=95.0,
            matched_skills=["Python", "PostgreSQL"],
        ),
    )
    score2 = JobMatchResult(
        canonical_id="canon_2",
        job_title="Python Engineer",
        company="Canonical",
        location="Bengaluru",
        recommendation=MatchRecommendation.STRETCH,
        overall_score=75.0,
        breakdown=MatchBreakdown(
            technical_score=80.0,
            role_score=70.0,
            experience_score=80.0,
            location_score=80.0,
            overall_score=75.0,
            matched_skills=["Python"],
        ),
    )
    JobRepository.save_match_scores_batch(in_memory_session, [score1, score2], profile_id="default")
    in_memory_session.commit()

    # Query all ranked jobs
    ranked = JobRepository.get_ranked_jobs(in_memory_session, profile_id="default")
    assert len(ranked) == 2
    assert ranked[0][0].canonical_id == "canon_1"
    assert ranked[0][1].overall_score == 95.0

    # Query filtered by recommendation
    apply_only = JobRepository.get_ranked_jobs(
        in_memory_session, recommendation="APPLY", profile_id="default"
    )
    assert len(apply_only) == 1
    assert apply_only[0][0].company == "Supabase"


def test_persist_pipeline_to_database_idempotent() -> None:
    """Verify persist_pipeline_to_database is completely idempotent across runs."""
    db_url = "sqlite:///:memory:"
    job = CanonicalJobPost(
        canonical_id="canon_pipe_1",
        title="AI Engineer",
        company="Databricks",
        location="Remote - India",
        description="AI agents.",
        sources=[JobSource.GREENHOUSE],
    )
    score = JobMatchResult(
        canonical_id="canon_pipe_1",
        job_title="AI Engineer",
        company="Databricks",
        location="Remote - India",
        recommendation=MatchRecommendation.APPLY,
        overall_score=92.0,
        breakdown=MatchBreakdown(
            technical_score=90.0,
            role_score=100.0,
            experience_score=90.0,
            location_score=100.0,
            overall_score=92.0,
        ),
    )

    # Run 1
    res1 = persist_pipeline_to_database(
        canonical_jobs=[job],
        match_results=[score],
        profile=CandidateProfile(),
        db_url=db_url,
    )
    assert res1["status"] == "SUCCESS"
    assert res1["canonical_jobs_upserted"] == 1
    assert res1["total_canonical_jobs_in_db"] == 1

    # Run 2 (simulate duplicate re-run with same data)
    res2 = persist_pipeline_to_database(
        canonical_jobs=[job],
        match_results=[score],
        profile=CandidateProfile(),
        db_url=db_url,
    )
    assert res2["status"] == "SUCCESS"
    assert res2["total_canonical_jobs_in_db"] == 1
