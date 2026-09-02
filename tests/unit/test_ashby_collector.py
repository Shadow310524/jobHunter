"""Unit tests for Ashby job collector."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from personal_job_hunter.collectors.ashby import (
    collect_ashby_jobs,
    extract_skills,
    infer_experience_level,
    is_target_location,
    is_target_role,
    parse_and_normalize_job,
)


def test_is_target_role_ashby() -> None:
    """Verify role filtering matches engineering targets and drops non-technical."""
    assert is_target_role("Applied AI Engineer") is True
    assert is_target_role("ML Systems Performance Engineer") is True
    assert is_target_role("Partner AI Deployment Engineer - AWS") is True
    assert is_target_role("Backend Engineer - Ingestion") is True

    # Exclusions
    assert is_target_role("Product Marketing Manager") is False
    assert is_target_role("Talent Acquisition Lead") is False
    assert is_target_role("Account Executive - Strategic") is False


def test_is_target_location_ashby() -> None:
    """Verify location matching for Bangalore, India, and Global Remote."""
    assert is_target_location("Bengaluru, IND") is True
    assert is_target_location("India - Remote") is True
    assert is_target_location("Delhi, India Mumbai, India") is True
    assert is_target_location("Remote, Global", is_remote=True) is True
    assert is_target_location("San Francisco, CA", is_remote=False) is False
    assert is_target_location("US - Remote San Francisco", is_remote=True) is False


def test_extract_skills_ashby() -> None:
    """Verify deterministic skill extraction."""
    text = "Experience with Python, PyTorch, LangGraph, FastAPI, Docker, and AWS Bedrock."
    skills = extract_skills(text)
    assert "PYTHON" in [s.upper() for s in skills]
    assert "PYTORCH" in [s.upper() for s in skills]
    assert "LANGGRAPH" in [s.upper() for s in skills]
    assert "FASTAPI" in [s.upper() for s in skills]
    assert "DOCKER" in [s.upper() for s in skills]
    assert "BEDROCK" in [s.upper() for s in skills]


def test_infer_experience_level() -> None:
    """Verify experience level inference."""
    assert infer_experience_level("Senior ML Engineer", "5+ years") == "Senior / 3+ years (Stretch)"
    assert (
        infer_experience_level("Associate AI Engineer", "Fresher welcome")
        == "Fresher / 0-2 years (Target)"
    )
    assert infer_experience_level("Software Engineer", "General requirements") == "0-3 years"


def test_parse_and_normalize_job_ashby() -> None:
    """Verify complete normalization of a raw Ashby job preserving company vs inferred data."""
    raw_job: dict[str, Any] = {
        "id": "bf036b23-cd23-46d0-a02f-4b1483f4698a",
        "title": "Applied AI Engineer",
        "location": "Bengaluru, IND",
        "secondaryLocations": [{"location": "Remote - India"}],
        "isRemote": True,
        "workplaceType": "Remote",
        "department": "Applied AI",
        "employmentType": "FullTime",
        "jobUrl": "https://jobs.ashbyhq.com/openai/bf036b23",
        "applyUrl": "https://jobs.ashbyhq.com/openai/bf036b23/application",
        "publishedAt": "2026-08-20T10:00:00Z",
        "descriptionPlain": (
            "We are seeking a Python and PyTorch engineer to build agentic workflows."
        ),
        "compensation": {"min": 120000, "max": 180000, "currency": "USD"},
    }

    normalized = parse_and_normalize_job(raw_job, "openai")
    assert normalized is not None
    assert normalized["source"] == "ashby"
    assert normalized["job_id"] == "ashby_openai_bf036b23-cd23-46d0-a02f-4b1483f4698a"
    assert normalized["title"] == "Applied AI Engineer"
    assert normalized["company"] == "Openai"
    assert normalized["location"] == "Bengaluru, IND"
    assert normalized["work_mode"] == "Remote"
    assert normalized["employment_type"] == "FullTime"
    assert normalized["department"] == "Applied AI"
    assert normalized["salary"] == {"min": 120000, "max": 180000, "currency": "USD"}
    assert (
        normalized["official_application_url"]
        == "https://jobs.ashbyhq.com/openai/bf036b23/application"
    )
    assert "PYTHON" in [s.upper() for s in normalized["inferred_skills"]]
    assert "PYTORCH" in [s.upper() for s in normalized["inferred_skills"]]


@pytest.mark.asyncio
async def test_collect_ashby_jobs_mocked(tmp_path: Path) -> None:
    """Verify Ashby collector orchestration, filtering, and file writing with mocked HTTP."""
    mock_payload = {
        "jobs": [
            {
                "id": "job-1",
                "title": "Partner AI Deployment Engineer - AWS",
                "location": "India - Remote",
                "secondaryLocations": [],
                "isRemote": True,
                "workplaceType": "Remote",
                "department": "Engineering",
                "jobUrl": "https://jobs.ashbyhq.com/test/job-1",
                "applyUrl": "https://jobs.ashbyhq.com/test/job-1/apply",
                "publishedAt": "2026-08-25T12:00:00Z",
                "descriptionPlain": "Deploying LLMs and AWS infrastructure with Python.",
            },
            {
                "id": "job-2",
                "title": "Senior Sales Executive",  # Should be filtered out
                "location": "Bengaluru, IND",
                "isRemote": False,
                "jobUrl": "https://jobs.ashbyhq.com/test/job-2",
                "descriptionPlain": "Sales quota management.",
            },
        ]
    }

    fake_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://api.ashbyhq.com/posting-api/job-board/testai"),
    )

    output_file = tmp_path / "ashby_test_jobs.json"

    with patch.object(httpx.AsyncClient, "get", return_value=fake_response):
        jobs = await collect_ashby_jobs(
            companies=["testai"],
            output_file=output_file,
            request_delay_seconds=0.0,
        )

    assert len(jobs) == 1
    assert jobs[0]["title"] == "Partner AI Deployment Engineer - AWS"
    assert output_file.exists()

    with open(output_file, encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved) == 1
    assert saved[0]["job_id"] == "ashby_testai_job-1"
