"""Unit tests for deterministic deduplication and canonical identity engine."""

from personal_job_hunter.domain.deduplication import (
    deduplicate_jobs,
    generate_candidate_group_key,
    normalize_url,
)
from personal_job_hunter.domain.models import (
    JobSource,
    UnifiedJobPost,
)


def test_url_normalization_tracking_params() -> None:
    """Verify URL normalizer strips only tracking params and preserves structural params."""
    # Tracking params stripped
    raw1 = "https://jobs.lever.co/cred/abc-123/?utm_source=linkedin&utm_campaign=hiring&ref=feed"
    assert normalize_url(raw1) == "https://jobs.lever.co/cred/abc-123"

    # Structural params preserved (e.g. ?gh_jid=)
    raw2 = "https://jobs.elastic.co/jobs?gh_jid=8154997&utm_medium=social"
    assert normalize_url(raw2) == "https://jobs.elastic.co/jobs?gh_jid=8154997"

    # Fragment stripped
    raw3 = "https://jobs.ashbyhq.com/openai/123#application-form"
    assert normalize_url(raw3) == "https://jobs.ashbyhq.com/openai/123"

    # Trailing slashes stripped
    raw4 = "https://boards.greenhouse.io/postman/jobs/7762102003/"
    assert normalize_url(raw4) == "https://boards.greenhouse.io/postman/jobs/7762102003"


def test_exact_duplicate_merge() -> None:
    """Verify exact duplicates are merged and provenance is preserved."""
    post1 = UnifiedJobPost(
        source=JobSource.GREENHOUSE,
        job_id="gh_101",
        job_url="https://job-boards.greenhouse.io/postman/jobs/101",
        official_application_url="https://job-boards.greenhouse.io/postman/jobs/101",
        title="AI Engineer",
        company="Postman",
        location="Bengaluru",
        description="Short description",
        inferred_skills=["Python"],
    )
    post2 = UnifiedJobPost(
        source=JobSource.GREENHOUSE,
        job_id="gh_101",
        job_url="https://job-boards.greenhouse.io/postman/jobs/101",
        official_application_url="https://job-boards.greenhouse.io/postman/jobs/101",
        title="AI Engineer",
        company="Postman",
        location="Bengaluru",
        description="Much longer comprehensive description with full requirements",
        inferred_skills=["Python", "FastAPI", "Docker"],
    )

    res = deduplicate_jobs([post1, post2])
    assert res.total_input_records == 2
    assert res.unique_canonical_jobs == 1
    assert res.confirmed_duplicates_merged == 1

    canon = res.canonical_jobs[0]
    assert len(canon.source_records) == 2
    assert canon.description == "Much longer comprehensive description with full requirements"
    assert "FastAPI" in canon.inferred_skills
    assert "Python" in canon.inferred_skills


def test_same_source_duplicate_via_job_id() -> None:
    """Verify duplicates with different URLs but identical source + job_id are merged."""
    post1 = UnifiedJobPost(
        source=JobSource.LEVER,
        job_id="lever_cred_999",
        job_url="https://jobs.lever.co/cred/999",
        official_application_url="https://jobs.lever.co/cred/999/apply",
        title="Backend Engineer",
        company="Cred",
        location="Bengaluru",
        description="Desc",
    )
    post2 = UnifiedJobPost(
        source=JobSource.LEVER,
        job_id="lever_cred_999",
        job_url="https://internal-proxy.lever.co/cred/999",
        official_application_url="https://internal-proxy.lever.co/cred/999/apply",
        title="Backend Engineer",
        company="Cred",
        location="Bengaluru",
        description="Desc",
    )

    res = deduplicate_jobs([post1, post2])
    assert res.unique_canonical_jobs == 1
    assert res.confirmed_duplicates_merged == 1
    assert len(res.canonical_jobs[0].source_records) == 2


def test_same_company_title_location_genuinely_different_jobs_not_merged() -> None:
    """Verify two distinct jobs with same title/company/location are NOT merged (flagged only)."""
    # E.g. Company hiring two separate SDE II - AI roles with different job IDs/URLs
    post1 = UnifiedJobPost(
        source=JobSource.GREENHOUSE,
        job_id="gh_inmobi_111",
        job_url="https://job-boards.greenhouse.io/inmobi/jobs/111",
        official_application_url="https://job-boards.greenhouse.io/inmobi/jobs/111",
        title="SDE II - AI",
        company="Inmobi",
        location="Bangalore",
        description="Ad tech optimization role",
    )
    post2 = UnifiedJobPost(
        source=JobSource.GREENHOUSE,
        job_id="gh_inmobi_222",
        job_url="https://job-boards.greenhouse.io/inmobi/jobs/222",
        official_application_url="https://job-boards.greenhouse.io/inmobi/jobs/222",
        title="SDE II - AI",
        company="Inmobi",
        location="Bangalore",
        description="Computer vision models role",
    )

    res = deduplicate_jobs([post1, post2])
    # Must remain 2 distinct canonical jobs!
    assert res.unique_canonical_jobs == 2
    assert res.confirmed_duplicates_merged == 0

    # Must be tagged in a potential duplicate group
    assert res.potential_duplicate_groups_count == 1
    assert res.potential_duplicate_jobs_count == 2
    assert res.canonical_jobs[0].duplicate_candidate_group is not None
    assert (
        res.canonical_jobs[0].duplicate_candidate_group
        == res.canonical_jobs[1].duplicate_candidate_group
    )


def test_cross_source_candidate_matching_not_auto_merged() -> None:
    """Verify cross-source identical postings are flagged rather than falsely merged."""
    # Greenhouse posting vs Ashby posting for same role but different URLs/IDs
    gh_post = UnifiedJobPost(
        source=JobSource.GREENHOUSE,
        job_id="gh_custom_555",
        job_url="https://boards.greenhouse.io/custom/555",
        official_application_url="https://boards.greenhouse.io/custom/555",
        title="Applied AI Engineer",
        company="TechCorp",
        location="Bengaluru, India",
        description="Greenhouse description",
    )
    ashby_post = UnifiedJobPost(
        source=JobSource.ASHBY,
        job_id="ashby_custom_777",
        job_url="https://jobs.ashbyhq.com/custom/777",
        official_application_url="https://jobs.ashbyhq.com/custom/777/apply",
        title="Applied AI Engineer",
        company="TechCorp",
        location="Bengaluru, India",
        description="Ashby description",
    )

    res = deduplicate_jobs([gh_post, ashby_post])
    assert res.unique_canonical_jobs == 2
    assert res.confirmed_duplicates_merged == 0
    assert res.potential_duplicate_groups_count == 1
    assert res.potential_duplicate_jobs_count == 2


def test_candidate_group_key_generation() -> None:
    """Verify candidate group key normalization."""
    key1 = generate_candidate_group_key("Postman, Inc.", "Senior Engineer - AI", "Bengaluru, India")
    key2 = generate_candidate_group_key("postman inc", "senior engineer ai", "bengaluru india")
    assert key1 == key2
    assert key1 == "cand::postman_inc::senior_engineer_ai::bengaluru_india"


def test_empty_missing_location_url_graceful_handling() -> None:
    """Verify empty URLs or missing locations do not crash the deduplication engine."""
    post1 = UnifiedJobPost(
        source=JobSource.GREENHOUSE,
        job_id="gh_none_1",
        job_url="",
        official_application_url="",
        title="Software Engineer",
        company="Startup",
        location="",
        description="Desc",
    )
    post2 = UnifiedJobPost(
        source=JobSource.GREENHOUSE,
        job_id="gh_none_2",
        job_url="",
        official_application_url="",
        title="Software Engineer",
        company="Startup",
        location="",
        description="Desc",
    )

    res = deduplicate_jobs([post1, post2])
    assert res.unique_canonical_jobs == 2
    assert res.confirmed_duplicates_merged == 0
