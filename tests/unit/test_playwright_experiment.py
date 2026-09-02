"""Unit test for the minimal Playwright experiment."""

from pathlib import Path

import pytest

from personal_job_hunter.playwright_experiment import extract_sample_job_title


@pytest.mark.asyncio
async def test_extract_sample_job_title() -> None:
    """Verify Playwright loads local fixture and extracts job title."""
    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "sample_job.html"
    assert fixture_path.exists(), f"Fixture not found at {fixture_path}"

    title = await extract_sample_job_title(fixture_path, headless=True)
    assert title == "AI Engineer"
