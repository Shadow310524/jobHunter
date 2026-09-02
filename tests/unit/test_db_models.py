"""Unit tests for database models and schema definitions."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from personal_job_hunter.db.models import (
    ApplicationModel,
    Base,
    CandidateProfileModel,
    CanonicalJobModel,
    JobMatchScoreModel,
    SourceProvenanceModel,
)


def test_schema_creation_and_models() -> None:
    """Verify all database tables and relationships create cleanly."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        # 1. Candidate Profile
        profile = CandidateProfileModel(
            id="default",
            name="Harish Renganathan",
            degree="B.Tech in AI & ML",
            graduation_year=2026,
            cgpa=8.2,
            current_role="AI Platform Engineer Intern",
            company_internship="AVASOFT",
            internship_duration="Dec 2025 - Apr 2026",
            core_skills=["Python", "FastAPI", "PostgreSQL"],
            secondary_skills=["Docker", "Linux"],
            target_roles=["AI Platform Engineer"],
            primary_locations=["Bangalore"],
            secondary_locations=["Hyderabad"],
        )
        session.add(profile)

        # 2. Canonical Job
        job = CanonicalJobModel(
            canonical_id="canon_123",
            title="AI Platform Engineer",
            company="Supabase",
            location="Remote, Global",
            secondary_locations=[],
            work_mode="Remote",
            is_remote=True,
            description="Build AI platform.",
            inferred_skills=["Python", "PostgreSQL"],
            application_urls=["https://jobs.ashbyhq.com/supabase/123"],
        )
        session.add(job)

        # 3. Source Provenance
        prov = SourceProvenanceModel(
            canonical_id="canon_123",
            source="ashby",
            source_job_id="ashby_123",
            job_url="https://jobs.ashbyhq.com/supabase/123",
            official_application_url="https://jobs.ashbyhq.com/supabase/123/apply",
            raw_metadata={"board": "supabase"},
        )
        session.add(prov)

        # 4. Match Score
        score = JobMatchScoreModel(
            canonical_id="canon_123",
            profile_id="default",
            recommendation="APPLY",
            overall_score=95.0,
            role_score=100.0,
            technical_score=95.0,
            experience_score=90.0,
            location_score=90.0,
            matched_skills=["Python", "PostgreSQL"],
            missing_skills=[],
            matched_role_keywords=["ai platform"],
            experience_eligible=True,
            location_eligible=True,
            score_reasons=["High fit"],
        )
        session.add(score)

        # 5. Application
        app = ApplicationModel(
            canonical_id="canon_123",
            status="NOT_APPLIED",
            notes="Ready for review",
        )
        session.add(app)
        session.commit()

        # Query and verify
        saved_job = session.get(CanonicalJobModel, "canon_123")
        assert saved_job is not None
        assert saved_job.title == "AI Platform Engineer"
        assert len(saved_job.source_records) == 1
        assert saved_job.source_records[0].source == "ashby"
        assert len(saved_job.match_scores) == 1
        assert saved_job.match_scores[0].overall_score == 95.0
        assert saved_job.application is not None
        assert saved_job.application.status == "NOT_APPLIED"
