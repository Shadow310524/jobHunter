"""Unit tests for Unified Ingestion Pipeline."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from personal_job_hunter.pipeline import run_ingestion_pipeline


@pytest.mark.asyncio
async def test_pipeline_complete_run_mocked(tmp_path: Path) -> None:
    """Verify end-to-end pipeline with mocked collectors producing canonical_jobs.json."""
    mock_gh_jobs = [
        {
            "job_id": "gh_101",
            "title": "Senior AI Engineer",
            "company": "Databricks",
            "location": "Bengaluru, India",
            "work_mode": "Hybrid",
            "job_url": "https://databricks.com/jobs/101",
            "official_application_url": "https://databricks.com/jobs/101/apply",
            "description": "Python, PyTorch and ML models.",
            "required_skills": ["Python", "PyTorch"],
            "source": "greenhouse",
        }
    ]

    mock_ashby_jobs = [
        {
            "job_id": "ashby_202",
            "title": "Applied AI Engineer",
            "company": "OpenAI",
            "location": "Delhi, India",
            "work_mode": "Hybrid",
            "is_remote": True,
            "job_url": "https://jobs.ashbyhq.com/openai/202",
            "official_application_url": "https://jobs.ashbyhq.com/openai/202/apply",
            "description": "Python and agent workflows.",
            "inferred_skills": ["Python", "LangGraph"],
            "source": "ashby",
        }
    ]

    mock_lever_jobs = [
        {
            "job_id": "lever_303",
            "title": "Backend Engineer",
            "company": "Cred",
            "location": "Bengaluru",
            "work_mode": "On-site",
            "job_url": "https://jobs.lever.co/cred/303",
            "official_application_url": "https://jobs.lever.co/cred/303/apply",
            "description": "FastAPI and PostgreSQL systems.",
            "inferred_skills": ["FastAPI", "PostgreSQL"],
            "source": "lever",
        }
    ]

    output_file = tmp_path / "canonical_jobs.json"

    with (
        patch("personal_job_hunter.pipeline.collect_greenhouse_jobs", return_value=mock_gh_jobs),
        patch("personal_job_hunter.pipeline.collect_ashby_jobs", return_value=mock_ashby_jobs),
        patch("personal_job_hunter.pipeline.collect_lever_jobs", return_value=mock_lever_jobs),
    ):
        dedup_res, summary = await run_ingestion_pipeline(output_file=output_file)

    assert summary.total_collected_records == 3
    assert summary.total_normalized_records == 3
    assert summary.total_canonical_unique_jobs == 3
    assert summary.confirmed_duplicates_merged == 0
    assert len(summary.sources_summary) == 3
    assert all(s.status == "SUCCESS" for s in summary.sources_summary)

    assert output_file.exists()
    with open(output_file, encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved) == 3
    companies = [j["company"] for j in saved]
    assert "Databricks" in companies
    assert "OpenAI" in companies
    assert "Cred" in companies


@pytest.mark.asyncio
async def test_pipeline_partial_source_failure_graceful(tmp_path: Path) -> None:
    """Verify that a failure in one source does not crash the entire pipeline."""
    mock_gh_jobs = [
        {
            "job_id": "gh_101",
            "title": "AI Platform Engineer",
            "company": "Inmobi",
            "location": "Bengaluru",
            "job_url": "https://inmobi.com/jobs/101",
            "official_application_url": "https://inmobi.com/jobs/101",
            "description": "AI systems.",
            "source": "greenhouse",
        }
    ]

    output_file = tmp_path / "canonical_jobs.json"

    with (
        patch("personal_job_hunter.pipeline.collect_greenhouse_jobs", return_value=mock_gh_jobs),
        # Ashby collector simulates unexpected API connection failure
        patch(
            "personal_job_hunter.pipeline.collect_ashby_jobs",
            side_effect=RuntimeError("Ashby API timeout / network failure"),
        ),
        patch("personal_job_hunter.pipeline.collect_lever_jobs", return_value=[]),
    ):
        dedup_res, summary = await run_ingestion_pipeline(output_file=output_file)

    # Pipeline still produced the Greenhouse job successfully
    assert summary.total_collected_records == 1
    assert summary.total_canonical_unique_jobs == 1
    assert output_file.exists()

    # Ashby stat recorded as FAILED with error message
    ashby_stat = next(s for s in summary.sources_summary if s.source == "ashby")
    assert ashby_stat.status == "FAILED"
    assert "Ashby API timeout" in str(ashby_stat.error)

    # Greenhouse stat recorded as SUCCESS
    gh_stat = next(s for s in summary.sources_summary if s.source == "greenhouse")
    assert gh_stat.status == "SUCCESS"
    assert gh_stat.collected_count == 1
