"""Unit tests for UnifiedJobPost domain model and source normalizers."""

from typing import Any

import pytest

from personal_job_hunter.domain.models import JobSource, UnifiedJobPost, WorkMode
from personal_job_hunter.domain.normalizers import (
    normalize_ashby_job,
    normalize_greenhouse_job,
    normalize_job,
    normalize_lever_job,
)


def test_unified_job_post_instantiation() -> None:
    """Verify clean instantiation and field trimming of UnifiedJobPost."""
    job = UnifiedJobPost(
        source=JobSource.GREENHOUSE,
        job_id="gh_123",
        job_url=" https://jobs.example.com/123 ",
        official_application_url="https://jobs.example.com/123/apply",
        title="  AI Platform Engineer  ",
        company="  ExampleCo  ",
        location="  Bengaluru, India  ",
        work_mode=WorkMode.HYBRID,
        description="  Building LLM agents with Python.  ",
        inferred_skills=["Python", "FastAPI"],
    )
    assert job.title == "AI Platform Engineer"
    assert job.company == "ExampleCo"
    assert job.location == "Bengaluru, India"
    assert job.work_mode == "Hybrid"
    assert job.source == "greenhouse"


def test_work_mode_normalization() -> None:
    """Verify work mode string coercion."""
    assert UnifiedJobPost.normalize_work_mode("Remote - Global") == WorkMode.REMOTE
    assert UnifiedJobPost.normalize_work_mode("Office / On-site") == WorkMode.ONSITE
    assert UnifiedJobPost.normalize_work_mode("Hybrid working") == WorkMode.HYBRID
    assert UnifiedJobPost.normalize_work_mode("Unspecified") == WorkMode.UNKNOWN


def test_normalize_greenhouse_format() -> None:
    """Verify Greenhouse schema normalization into UnifiedJobPost."""
    gh_raw: dict[str, Any] = {
        "job_id": "gh_postman_7762102003",
        "title": "Senior Engineer - Fabric Gateway",
        "company": "Postman",
        "location": "Bengaluru, Karnataka, India",
        "work_mode": "On-site",
        "experience": "Senior / 3+ years (Stretch)",
        "salary": None,
        "posted_date": "2026-08-17T18:15:55-04:00",
        "description": "Who Are We? Postman is an API platform...",
        "required_skills": ["GO", "Kubernetes"],
        "preferred_skills": ["Python"],
        "job_url": "https://job-boards.greenhouse.io/postman/jobs/7762102003",
        "official_application_url": "https://job-boards.greenhouse.io/postman/jobs/7762102003",
        "departments": ["Product Engineering"],
        "source": "greenhouse",
    }

    unified = normalize_greenhouse_job(gh_raw)
    assert unified.source == JobSource.GREENHOUSE
    assert unified.job_id == "gh_postman_7762102003"
    assert unified.title == "Senior Engineer - Fabric Gateway"
    assert unified.company == "Postman"
    assert unified.location == "Bengaluru, Karnataka, India"
    assert unified.work_mode == WorkMode.ONSITE
    assert unified.department == "Product Engineering"
    assert unified.inferred_skills == ["GO", "Kubernetes"]
    assert unified.inferred_experience_level == "Senior / 3+ years (Stretch)"
    assert unified.metadata["preferred_skills"] == ["Python"]


def test_normalize_ashby_format() -> None:
    """Verify Ashby schema normalization into UnifiedJobPost."""
    ashby_raw: dict[str, Any] = {
        "source": "ashby",
        "job_id": "ashby_openai_bf036b23-cd23-46d0-a02f-4b1483f4698a",
        "title": "Applied AI Engineer",
        "company": "Openai",
        "location": "Delhi, India",
        "secondary_locations": ["Mumbai, India"],
        "work_mode": "Hybrid",
        "is_remote": True,
        "employment_type": "FullTime",
        "department": "Go To Market",
        "raw_experience_text": None,
        "inferred_experience_level": "Senior / 3+ years (Stretch)",
        "salary": None,
        "posted_date": "2026-08-03T04:14:45.299+00:00",
        "description": "About the Team...",
        "inferred_skills": ["GO", "Python"],
        "job_url": "https://jobs.ashbyhq.com/openai/bf036b23",
        "official_application_url": "https://jobs.ashbyhq.com/openai/bf036b23/application",
    }

    unified = normalize_ashby_job(ashby_raw)
    assert unified.source == JobSource.ASHBY
    assert unified.job_id == "ashby_openai_bf036b23-cd23-46d0-a02f-4b1483f4698a"
    assert unified.title == "Applied AI Engineer"
    assert unified.company == "Openai"
    assert unified.location == "Delhi, India"
    assert unified.secondary_locations == ["Mumbai, India"]
    assert unified.work_mode == WorkMode.HYBRID
    assert unified.is_remote is True
    assert unified.employment_type == "FullTime"
    assert unified.department == "Go To Market"
    assert unified.inferred_skills == ["GO", "Python"]


def test_normalize_lever_format() -> None:
    """Verify Lever schema normalization into UnifiedJobPost."""
    lever_raw: dict[str, Any] = {
        "source": "lever",
        "job_id": "lever_cred_7e4d512e-fc89-40fd-9a30-46c5459bbea5",
        "title": "machine learning engineer",
        "company": "Cred",
        "location": "hyderabad",
        "secondary_locations": ["hyderabad"],
        "work_mode": "On-site",
        "is_remote": False,
        "employment_type": "full time",
        "department": "Prefr",
        "raw_experience_text": None,
        "inferred_experience_level": "0-3 years",
        "salary": None,
        "posted_date": "2025-12-18T06:24:33.908000+00:00",
        "description": "prefr is a tech-first fintech platform...",
        "inferred_skills": ["Machine Learning"],
        "job_url": "https://jobs.lever.co/cred/7e4d512e",
        "official_application_url": "https://jobs.lever.co/cred/7e4d512e/apply",
    }

    unified = normalize_lever_job(lever_raw)
    assert unified.source == JobSource.LEVER
    assert unified.job_id == "lever_cred_7e4d512e-fc89-40fd-9a30-46c5459bbea5"
    assert unified.title == "machine learning engineer"
    assert unified.company == "Cred"
    assert unified.location == "hyderabad"
    assert unified.work_mode == WorkMode.ONSITE
    assert unified.inferred_skills == ["Machine Learning"]


def test_generic_normalize_job_dispatch() -> None:
    """Verify normalize_job correctly dispatches by source."""
    sample: dict[str, Any] = {
        "job_id": "gh_1",
        "job_url": "https://example.com",
        "title": "Engineer",
        "company": "Test",
        "location": "Bengaluru",
        "description": "Desc",
    }
    unified = normalize_job(sample, "greenhouse")
    assert unified.source == JobSource.GREENHOUSE

    with pytest.raises(ValueError, match="Unsupported job source"):
        normalize_job(sample, "unsupported_platform")
