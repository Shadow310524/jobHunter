"""Unit tests for calibrated candidate profile matcher and scoring engine (Phase 5B)."""

from personal_job_hunter.domain.matcher import (
    evaluate_experience_compatibility,
    evaluate_location_compatibility,
    evaluate_role_relevance,
    evaluate_technical_skills,
    match_all_jobs,
    match_job,
)
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobSource,
    MatchRecommendation,
    MatchWeights,
    WorkMode,
)


def create_sample_job(
    title: str = "AI Engineer",
    location: str = "Bengaluru, Karnataka, India",
    description: str = "Building LLM agents with Python, FastAPI, and Docker.",
    inferred_skills: list[str] | None = None,
    experience_text: str | None = None,
    inferred_experience: str | None = None,
    work_mode: WorkMode = WorkMode.ONSITE,
    is_remote: bool = False,
) -> CanonicalJobPost:
    """Helper to construct CanonicalJobPost instances for testing."""
    return CanonicalJobPost(
        canonical_id="canon_test_1",
        title=title,
        company="TestCompany",
        location=location,
        work_mode=work_mode,
        is_remote=is_remote,
        description=description,
        raw_experience_text=experience_text,
        inferred_experience_level=inferred_experience,
        inferred_skills=inferred_skills or [],
        sources=[JobSource.GREENHOUSE],
        application_urls=["https://example.com/apply"],
    )


def test_excellent_match_ai_engineer_bangalore() -> None:
    """Verify excellent match for AI Platform role in Bangalore receives APPLY recommendation."""
    job = create_sample_job(
        title="AI Platform Engineer",
        location="Bengaluru, India",
        description=(
            "Develop GenAI agents using Python, FastAPI, LangChain, "
            "PostgreSQL, and AWS Bedrock. 0-2 years experience."
        ),
        inferred_skills=["Python", "FastAPI", "PostgreSQL", "LangChain", "Docker"],
        inferred_experience="Fresher / 0-2 years (Target)",
    )
    result = match_job(job)

    assert result.recommendation == MatchRecommendation.APPLY
    assert result.overall_score >= 80.0
    assert result.breakdown.role_score == 100.0
    assert result.breakdown.location_score == 100.0
    assert result.breakdown.experience_eligible is True
    assert "Python" in result.breakdown.matched_skills
    assert "FastAPI" in result.breakdown.matched_skills


def test_senior_stretch_job_classification() -> None:
    """Verify senior position (3+ years) with good skills is tagged STRETCH rather than APPLY."""
    job = create_sample_job(
        title="Senior AI Engineer",
        location="Bengaluru, India",
        description="Lead AI systems in Python, PyTorch, Docker. 5+ years experience required.",
        inferred_skills=["Python", "PyTorch", "Docker"],
        inferred_experience="Senior / 3+ years (Stretch)",
    )
    result = match_job(job)

    # Senior title has experience_eligible = False, placing it in STRETCH
    assert result.breakdown.experience_eligible is False
    assert result.recommendation == MatchRecommendation.STRETCH


def test_support_sustaining_role_skip() -> None:
    """Verify operational / support / sustaining engineering roles are skipped."""
    job = create_sample_job(
        title="Associate Linux Support Engineer",
        location="Bengaluru, India",
        description="Resolve customer tickets on Linux and Python environments.",
        inferred_skills=["Linux", "Python"],
    )
    result = match_job(job)

    assert result.breakdown.role_score == 35.0
    assert result.recommendation == MatchRecommendation.SKIP


def test_disqualified_non_technical_role_skip() -> None:
    """Verify non-technical role receives role_score 0 and SKIP."""
    job = create_sample_job(
        title="Sales Development Representative",
        location="Bengaluru, India",
        description="Cold outreach and lead generation.",
    )
    result = match_job(job)

    assert result.breakdown.role_score == 0.0
    assert result.recommendation == MatchRecommendation.SKIP


def test_disqualified_foreign_onsite_location_skip() -> None:
    """Verify foreign on-site role with no remote option is disqualified."""
    job = create_sample_job(
        title="AI Engineer",
        location="London, United Kingdom",
        description="Build Python AI agents in our central London office.",
        is_remote=False,
    )
    result = match_job(job)

    assert result.breakdown.location_score == 0.0
    assert result.breakdown.location_eligible is False
    assert result.recommendation == MatchRecommendation.SKIP


def test_remote_india_location_score() -> None:
    """Verify Remote India location receives 100 location score."""
    job = create_sample_job(
        title="Backend Developer",
        location="Remote - India",
        description="Python backend services.",
        is_remote=True,
    )
    score, eligible, reasons = evaluate_location_compatibility(job, CandidateProfile())
    assert score == 100.0
    assert eligible is True


def test_tier_one_indian_hub_location_score() -> None:
    """Verify Hyderabad or Pune receives secondary tier location score (80)."""
    job = create_sample_job(
        title="Python Engineer",
        location="Hyderabad, Telangana, India",
        description="Python services.",
    )
    score, eligible, _ = evaluate_location_compatibility(job, CandidateProfile())
    assert score == 80.0
    assert eligible is True


def test_worldwide_remote_stretch_only() -> None:
    """Verify Worldwide Remote without explicit India entity is not marked eligible for APPLY."""
    job = create_sample_job(
        title="Python Engineer",
        location="Home based - Worldwide",
        description="Python services.",
        is_remote=True,
    )
    score, eligible, _ = evaluate_location_compatibility(job, CandidateProfile())
    assert score == 50.0
    assert eligible is False


def test_missing_experience_information_graceful() -> None:
    """Verify jobs with no stated experience receive neutral score and remain eligible."""
    job = create_sample_job(
        title="Software Engineer",
        location="Bengaluru",
        description="Join our engineering team to write software.",
    )
    score, eligible, _ = evaluate_experience_compatibility(job, CandidateProfile())
    assert score == 75.0
    assert eligible is True


def test_ai_role_without_ai_skills_capped() -> None:
    """Verify AI role with only generic Python/Git skills has technical score capped."""
    job = create_sample_job(
        title="AI Engineer",
        location="Bengaluru",
        description="Write standard Python scripts and manage Git repos.",
        inferred_skills=["Python", "Git"],
    )
    # Role is AI Tier 1 (100 pts)
    tech_score, matched, missing, reasons = evaluate_technical_skills(
        job, CandidateProfile(), role_score=100.0
    )
    assert tech_score <= 60.0


def test_generic_software_engineer_vs_ai_role() -> None:
    """Verify AI specific role scores higher than generic software engineer."""
    ai_job = create_sample_job(title="GenAI Engineer")
    swe_job = create_sample_job(title="Software Engineer")

    profile = CandidateProfile()
    ai_score, _, _ = evaluate_role_relevance(ai_job, profile)
    swe_score, _, _ = evaluate_role_relevance(swe_job, profile)

    assert ai_score == 100.0
    assert swe_score == 70.0


def test_false_positive_keyword_avoidance() -> None:
    """Verify substrings in words (like 'affairs', 'email') don't trigger false matches."""
    job = create_sample_job(
        title="Public Affairs Manager",
        description="Manage email campaigns and social affairs.",
    )
    score, matched, _ = evaluate_role_relevance(job, CandidateProfile())
    assert score == 0.0
    assert "ai" not in matched


def test_custom_weights_override() -> None:
    """Verify configurable weights alter overall score calculation."""
    job = create_sample_job(
        title="AI Engineer",
        location="Bengaluru",
        description="Python, FastAPI, and LangChain.",
        inferred_skills=["Python", "FastAPI", "LangChain"],
    )

    res_std = match_job(job)

    custom_weights = MatchWeights(
        role_weight=0.10,
        technical_weight=0.80,
        experience_weight=0.05,
        location_weight=0.05,
    )
    res_custom = match_job(job, weights=custom_weights)

    assert res_std.overall_score != res_custom.overall_score


def test_match_all_jobs_sorted_descending() -> None:
    """Verify match_all_jobs returns list sorted in descending score order."""
    job1 = create_sample_job(
        title="AI Platform Engineer",
        description="Python, FastAPI, LangChain, AWS Bedrock. 0-1 years.",
        inferred_skills=["Python", "FastAPI", "LangChain"],
    )
    job2 = create_sample_job(
        title="Software Engineer",
        description="C++ and Ruby systems.",
        inferred_skills=["C++", "Ruby"],
    )

    results = match_all_jobs([job2, job1])
    assert len(results) == 2
    assert results[0].overall_score >= results[1].overall_score
    assert results[0].job_title == "AI Platform Engineer"
