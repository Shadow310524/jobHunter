"""Unit tests for Lever job collector."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from personal_job_hunter.collectors.lever import (
    collect_lever_jobs,
    extract_skills,
    infer_experience_level,
    is_target_location,
    is_target_role,
    parse_and_normalize_job,
    parse_timestamp_ms,
)


def test_parse_timestamp_ms() -> None:
    """Verify conversion of Unix epoch ms to ISO 8601 string."""
    ts_ms = 1700000000000
    iso_str = parse_timestamp_ms(ts_ms)
    assert iso_str is not None
    assert "2023-11-14" in iso_str
    assert parse_timestamp_ms(None) is None


def test_is_target_role_lever() -> None:
    """Verify role filtering for Lever jobs."""
    assert is_target_role("Backend Engineer - Payments") is True
    assert is_target_role("AI Platform Developer") is True
    assert is_target_role("Software Engineer - Core") is True

    # Exclusions
    assert is_target_role("Area Collections Manager Bangalore") is False
    assert is_target_role("Human Resources Specialist") is False
    assert is_target_role("Business Development Lead") is False


def test_is_target_location_lever() -> None:
    """Verify location filtering for Lever postings."""
    assert is_target_location("bengaluru") is True
    assert is_target_location("Bangalore, India") is True
    assert is_target_location("Remote - India", is_remote=True) is True
    assert is_target_location("Remote, Global", is_remote=True) is True
    assert is_target_location("San Francisco, CA", is_remote=False) is False
    assert is_target_location("US - Remote", is_remote=True) is False


def test_extract_skills_lever() -> None:
    """Verify deterministic skill extraction."""
    text = "Core stack includes Python, PostgreSQL, Redis, Docker, and AWS."
    skills = extract_skills(text)
    assert "PYTHON" in [s.upper() for s in skills]
    assert "POSTGRESQL" in [s.upper() for s in skills]
    assert "REDIS" in [s.upper() for s in skills]
    assert "DOCKER" in [s.upper() for s in skills]
    assert "AWS" in [s.upper() for s in skills]


def test_infer_experience_level_lever() -> None:
    """Verify experience level inference."""
    assert infer_experience_level("Staff Backend Engineer", "") == "Senior / 3+ years (Stretch)"
    assert (
        infer_experience_level("Graduate Software Engineer", "") == "Fresher / 0-2 years (Target)"
    )
    assert infer_experience_level("Software Engineer", "") == "0-3 years"


def test_parse_and_normalize_job_lever() -> None:
    """Verify complete normalization of raw Lever job."""
    raw_job: dict[str, Any] = {
        "id": "abc-123-xyz",
        "text": "Software Engineer - Backend",
        "categories": {
            "location": "bengaluru",
            "allLocations": ["bengaluru"],
            "commitment": "full time",
            "department": "Engineering",
            "team": "Payments Platform",
        },
        "workplaceType": "hybrid",
        "createdAt": 1700000000000,
        "descriptionPlain": "Build robust Python and FastAPI microservices with PostgreSQL.",
        "additionalPlain": "Requires strong SQL and Docker experience.",
        "hostedUrl": "https://jobs.lever.co/cred/abc-123-xyz",
        "applyUrl": "https://jobs.lever.co/cred/abc-123-xyz/apply",
    }

    normalized = parse_and_normalize_job(raw_job, "cred")
    assert normalized is not None
    assert normalized["source"] == "lever"
    assert normalized["job_id"] == "lever_cred_abc-123-xyz"
    assert normalized["title"] == "Software Engineer - Backend"
    assert normalized["company"] == "Cred"
    assert normalized["location"] == "bengaluru"
    assert normalized["work_mode"] == "Hybrid"
    assert normalized["employment_type"] == "full time"
    assert normalized["department"] == "Engineering"
    assert normalized["official_application_url"] == "https://jobs.lever.co/cred/abc-123-xyz/apply"
    assert "PYTHON" in [s.upper() for s in normalized["inferred_skills"]]
    assert "FASTAPI" in [s.upper() for s in normalized["inferred_skills"]]
    assert "POSTGRESQL" in [s.upper() for s in normalized["inferred_skills"]]


@pytest.mark.asyncio
async def test_collect_lever_jobs_mocked(tmp_path: Path) -> None:
    """Verify Lever collector orchestration with mocked HTTP."""
    mock_payload = [
        {
            "id": "lever-1",
            "text": "AI Engineer",
            "categories": {
                "location": "bengaluru",
                "commitment": "full time",
            },
            "workplaceType": "onsite",
            "createdAt": 1700000000000,
            "descriptionPlain": "Building LLM agents using Python and LangChain.",
            "hostedUrl": "https://jobs.lever.co/testco/lever-1",
            "applyUrl": "https://jobs.lever.co/testco/lever-1/apply",
        },
        {
            "id": "lever-2",
            "text": "HR Recruiter",
            "categories": {"location": "bengaluru"},
            "descriptionPlain": "Hiring talents.",
        },
    ]

    fake_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://api.lever.co/v0/postings/testco?mode=json"),
    )

    output_file = tmp_path / "lever_test_jobs.json"

    with patch.object(httpx.AsyncClient, "get", return_value=fake_response):
        jobs = await collect_lever_jobs(
            companies=["testco"],
            output_file=output_file,
            request_delay_seconds=0.0,
        )

    assert len(jobs) == 1
    assert jobs[0]["title"] == "AI Engineer"
    assert output_file.exists()

    with open(output_file, encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved) == 1
    assert saved[0]["job_id"] == "lever_testco_lever-1"
