"""Unit tests for Greenhouse job collector."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from personal_job_hunter.collectors.greenhouse import (
    clean_html_text,
    collect_greenhouse_jobs,
    detect_work_mode,
    extract_skills,
    is_target_location,
    is_target_role,
    parse_and_normalize_job,
)


def test_clean_html_text() -> None:
    """Verify HTML cleaning and entity unescaping."""
    raw = "<p>We are hiring a <strong>Python &amp; AI Engineer</strong> in Bangalore.</p><br/>"
    cleaned = clean_html_text(raw)
    assert cleaned == "We are hiring a Python & AI Engineer in Bangalore."


def test_extract_skills() -> None:
    """Verify deterministic skill extraction using word boundaries."""
    text = "Requires Python, FastAPI, PostgreSQL, and experience with Docker, LangChain & AWS S3."
    skills = extract_skills(text)
    assert "PYTHON" in [s.upper() for s in skills]
    assert "FASTAPI" in [s.upper() for s in skills]
    assert "POSTGRESQL" in [s.upper() for s in skills]
    assert "DOCKER" in [s.upper() for s in skills]
    assert "LANGCHAIN" in [s.upper() for s in skills]
    assert "AWS" in [s.upper() for s in skills]
    assert "S3" in [s.upper() for s in skills]


def test_is_target_role_filtering() -> None:
    """Verify target roles are matched and excluded roles are filtered out."""
    assert is_target_role("AI Platform Engineer") is True
    assert is_target_role("Python Backend Developer") is True
    assert is_target_role("Software Engineer - GenAI") is True
    assert is_target_role("Machine Learning Engineer") is True

    # Exclusions
    assert is_target_role("Senior Sales Representative") is False
    assert is_target_role("HR Recruiter") is False
    assert is_target_role("BPO Executive") is False
    assert is_target_role("Account Executive - Enterprise") is False


def test_is_target_location_filtering() -> None:
    """Verify target locations are correctly matched."""
    assert is_target_location("Bangalore, India") is True
    assert is_target_location("Bengaluru, Karnataka") is True
    assert is_target_location("Remote - India") is True
    assert is_target_location("Home Based - APAC") is True
    assert is_target_location("New York, NY") is False
    assert is_target_location("London, UK") is False


def test_detect_work_mode() -> None:
    """Verify work mode detection."""
    assert detect_work_mode("Remote - India", "AI Engineer", "Work from anywhere") == "Remote"
    assert (
        detect_work_mode("Bangalore, India", "Backend Engineer", "Hybrid work policy") == "Hybrid"
    )
    assert detect_work_mode("Bangalore Office", "Software Engineer", "Office based") == "On-site"


def test_parse_and_normalize_job() -> None:
    """Verify complete normalization of a raw Greenhouse job."""
    raw_job: dict[str, Any] = {
        "id": 12345,
        "title": "Junior AI Engineer",
        "location": {"name": "Bengaluru, India"},
        "absolute_url": "https://boards.greenhouse.io/example/jobs/12345",
        "updated_at": "2026-09-01T10:00:00Z",
        "content": "<p>Looking for a Python and PyTorch developer with FastAPI experience.</p>",
        "departments": [{"name": "AI Engineering"}],
    }

    normalized = parse_and_normalize_job(raw_job, "example")
    assert normalized is not None
    assert normalized["job_id"] == "gh_example_12345"
    assert normalized["title"] == "Junior AI Engineer"
    assert normalized["company"] == "Example"
    assert normalized["location"] == "Bengaluru, India"
    assert normalized["source"] == "greenhouse"
    assert normalized["job_url"] == "https://boards.greenhouse.io/example/jobs/12345"
    assert (
        normalized["official_application_url"] == "https://boards.greenhouse.io/example/jobs/12345"
    )
    assert "PYTHON" in [s.upper() for s in normalized["required_skills"]]
    assert "FASTAPI" in [s.upper() for s in normalized["required_skills"]]


@pytest.mark.asyncio
async def test_collect_greenhouse_jobs_mocked(tmp_path: Path) -> None:
    """Verify collector orchestration, deduplication, and file writing with mocked HTTP."""
    mock_payload = {
        "jobs": [
            {
                "id": 101,
                "title": "AI Platform Engineer",
                "location": {"name": "Bangalore, India"},
                "absolute_url": "https://boards.greenhouse.io/test/jobs/101",
                "updated_at": "2026-09-01T12:00:00Z",
                "content": "<p>Python, AWS, and Docker skills needed.</p>",
                "departments": [{"name": "Platform"}],
            },
            {
                "id": 102,
                "title": "Sales Development Rep",  # Should be filtered out
                "location": {"name": "Bangalore, India"},
                "absolute_url": "https://boards.greenhouse.io/test/jobs/102",
                "content": "<p>Cold calling.</p>",
            },
        ]
    }

    import httpx

    fake_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://boards-api.greenhouse.io/v1/boards/testco/jobs"),
    )

    output_file = tmp_path / "test_jobs.json"

    with patch.object(httpx.AsyncClient, "get", return_value=fake_response):
        jobs = await collect_greenhouse_jobs(
            companies=["testco"],
            output_file=output_file,
            request_delay_seconds=0.0,
        )

    assert len(jobs) == 1
    assert jobs[0]["title"] == "AI Platform Engineer"
    assert output_file.exists()

    with open(output_file, encoding="utf-8") as f:
        saved_data = json.load(f)
    assert len(saved_data) == 1
    assert saved_data[0]["job_id"] == "gh_testco_101"
