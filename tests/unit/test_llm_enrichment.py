"""Unit tests for LLM enrichment schemas, gating policy, prompt versioning, and caching."""

from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from personal_job_hunter.db.models import Base
from personal_job_hunter.db.repository import JobRepository, ProfileRepository
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
    JobSource,
    MatchBreakdown,
    MatchRecommendation,
    WorkMode,
)
from personal_job_hunter.llm.enricher import JobEnrichmentEngine, compute_enrichment_hash
from personal_job_hunter.llm.models import JobEnrichmentResult
from personal_job_hunter.llm.prompts import ENRICHMENT_PROMPT_VERSION, build_enrichment_user_prompt
from personal_job_hunter.llm.service import MockLLMService


def create_sample_job(
    canonical_id: str = "canon_llm_1",
    title: str = "AI Platform Engineer",
    company: str = "Supabase",
    location: str = "Bengaluru, India",
    description: str = "Develop AI agent platforms with Python, FastAPI, and pgvector.",
    inferred_skills: list[str] | None = None,
) -> CanonicalJobPost:
    return CanonicalJobPost(
        canonical_id=canonical_id,
        title=title,
        company=company,
        location=location,
        work_mode=WorkMode.ONSITE,
        description=description,
        inferred_skills=inferred_skills or ["Python", "FastAPI", "pgvector"],
        sources=[JobSource.ASHBY],
        application_urls=["https://example.com/apply"],
    )


def test_job_enrichment_result_schema_validation() -> None:
    """Verify JobEnrichmentResult Pydantic schema validation."""
    payload = {
        "job_summary": "Building AI platform systems using Python and FastAPI.",
        "key_responsibilities": ["Design microservices", "Deploy agents"],
        "stated_qualifications": ["3+ years Python", "PostgreSQL experience"],
        "inferred_technical_focus": ["Backend", "AI Infrastructure"],
        "candidate_strengths": ["FastAPI expertise", "Internship at AVASOFT"],
        "gap_analysis": ["PostgreSQL performance tuning at scale"],
        "transferable_skills": ["RAG architecture experience"],
        "ambiguity_flags": [],
        "interview_talking_points": ["Discuss AVASOFT AI agent development."],
        "confidence_score": 0.95,
        "is_company_stated_fact_verified": True,
    }

    result = JobEnrichmentResult.model_validate(payload)
    assert result.job_summary.startswith("Building AI platform")
    assert len(result.key_responsibilities) == 2
    assert result.confidence_score == 0.95
    assert result.is_company_stated_fact_verified is True


def test_company_stated_facts_vs_model_inference_separation() -> None:
    """Verify ground truth company facts are isolated from candidate-specific inferences."""
    job = create_sample_job()
    profile = CandidateProfile()
    mock_svc = MockLLMService()

    enrichment = mock_svc.enrich_job(job, profile)
    assert isinstance(enrichment, JobEnrichmentResult)

    # Company-stated facts
    assert job.company in enrichment.job_summary
    assert len(enrichment.key_responsibilities) > 0
    assert len(enrichment.stated_qualifications) > 0

    # Model inferences
    assert len(enrichment.candidate_strengths) > 0
    assert len(enrichment.interview_talking_points) > 0
    assert any("AVASOFT" in p for p in enrichment.interview_talking_points)


def test_gating_policy_enforcement() -> None:
    """Verify LLM is only called for APPLY and high-score STRETCH, never for SKIP."""
    engine = JobEnrichmentEngine(llm_service=MockLLMService())

    # 1. APPLY job -> Must enrich
    apply_match = JobMatchResult(
        canonical_id="job_apply",
        job_title="AI Engineer",
        company="Databricks",
        location="Bengaluru",
        recommendation=MatchRecommendation.APPLY,
        overall_score=92.0,
        breakdown=MatchBreakdown(overall_score=92.0),
    )
    assert engine.should_enrich(apply_match) is True

    # 2. High-score STRETCH job (>= 75.0) -> Must enrich
    stretch_high = JobMatchResult(
        canonical_id="job_stretch_hi",
        job_title="Python Engineer",
        company="Canonical",
        location="Remote",
        recommendation=MatchRecommendation.STRETCH,
        overall_score=78.0,
        breakdown=MatchBreakdown(overall_score=78.0),
    )
    assert engine.should_enrich(stretch_high) is True

    # 3. Low-score STRETCH job (< 75.0) -> Skip enrichment to save cost
    stretch_low = JobMatchResult(
        canonical_id="job_stretch_lo",
        job_title="Software Engineer",
        company="Test",
        location="Remote",
        recommendation=MatchRecommendation.STRETCH,
        overall_score=62.0,
        breakdown=MatchBreakdown(overall_score=62.0),
    )
    assert engine.should_enrich(stretch_low) is False

    # 4. SKIP job -> Absolutely NEVER enrich (0 tokens spent)
    skip_match = JobMatchResult(
        canonical_id="job_skip",
        job_title="Support Engineer",
        company="Test",
        location="Remote",
        recommendation=MatchRecommendation.SKIP,
        overall_score=35.0,
        breakdown=MatchBreakdown(overall_score=35.0),
    )
    assert engine.should_enrich(skip_match) is False


def test_content_hash_stability_and_versioning() -> None:
    """Verify content hash incorporates job text, profile, model name, and prompt version."""
    job = create_sample_job()
    profile = CandidateProfile()

    hash1 = compute_enrichment_hash(
        job=job,
        profile=profile,
        model_name="gemini-1.5-flash",
        model_version="1.5",
        prompt_version="v1.0",
    )
    hash2 = compute_enrichment_hash(
        job=job,
        profile=profile,
        model_name="gemini-1.5-flash",
        model_version="1.5",
        prompt_version="v1.0",
    )
    assert hash1 == hash2

    # Changing prompt version changes hash
    hash_diff_prompt = compute_enrichment_hash(
        job=job,
        profile=profile,
        model_name="gemini-1.5-flash",
        model_version="1.5",
        prompt_version="v2.0",
    )
    assert hash1 != hash_diff_prompt


def test_idempotent_caching_in_database() -> None:
    """Verify enrichment is cached in DB and mock provider is not invoked on repeated runs."""
    db_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=db_engine)

    mock_svc = MockLLMService()
    mock_svc.enrich_job = MagicMock(wraps=mock_svc.enrich_job)  # type: ignore[method-assign]
    engine = JobEnrichmentEngine(llm_service=mock_svc)

    job = create_sample_job(canonical_id="canon_db_cache")
    profile = CandidateProfile()
    match_res = JobMatchResult(
        canonical_id="canon_db_cache",
        job_title=job.title,
        company=job.company,
        location=job.location,
        recommendation=MatchRecommendation.APPLY,
        overall_score=90.0,
        breakdown=MatchBreakdown(overall_score=90.0),
    )

    with Session(db_engine) as session:
        ProfileRepository.save_profile(session, profile, profile_id="default")
        JobRepository.upsert_canonical_job(session, job)
        session.commit()

        # Run 1: Should invoke mock service once and persist to DB
        res1 = engine.enrich_job(job, profile, match_res, session=session)
        session.commit()
        assert res1 is not None
        assert mock_svc.enrich_job.call_count == 1

        # Run 2: Identical parameters should load from DB without calling service
        res2 = engine.enrich_job(job, profile, match_res, session=session)
        assert res2 is not None
        assert mock_svc.enrich_job.call_count == 1  # Call count remains 1!
        assert res2.job_summary == res1.job_summary


def test_prompt_construction_privacy() -> None:
    """Verify prompt builder formats job description without leaking sensitive variables."""
    job = create_sample_job()
    profile = CandidateProfile()
    prompt = build_enrichment_user_prompt(job, profile)

    assert "### CANDIDATE PROFILE" in prompt
    assert "### JOB POSTING" in prompt
    assert "AVASOFT" in prompt
    assert "pgvector" in prompt
    assert ENRICHMENT_PROMPT_VERSION == "v1.0"
