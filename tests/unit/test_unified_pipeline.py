"""Unit tests for the unified pipeline orchestration, notifications, and fault tolerance."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    DeduplicationResult,
    JobSource,
    WorkMode,
)
from personal_job_hunter.notifications.base import NotificationEvent
from personal_job_hunter.notifications.service import (
    ConsoleNotificationService,
    FileLogNotificationService,
)
from personal_job_hunter.unified_pipeline import FullPipelineResult, run_full_unified_pipeline


class MockNotificationService:
    """Mock notification recorder."""

    def __init__(self) -> None:
        self.events: list[NotificationEvent] = []

    def notify(self, event: NotificationEvent) -> bool:
        self.events.append(event)
        return True


@pytest.fixture
def test_db_url() -> str:
    return "sqlite:///:memory:"


@pytest.mark.asyncio
async def test_unified_pipeline_full_execution_mocked(test_db_url: str) -> None:
    """Verify unified pipeline coordinates all 10 phases end-to-end."""
    sample_job = CanonicalJobPost(
        canonical_id="canon_unif_1",
        title="AI Engineer",
        company="Databricks",
        location="Bengaluru, India",
        work_mode=WorkMode.ONSITE,
        description="Build LLM systems.",
        sources=[JobSource.GREENHOUSE],
        application_urls=["https://databricks.com/apply"],
    )
    mock_dedup_res = DeduplicationResult(
        canonical_jobs=[sample_job],
        total_input_records=1,
        unique_canonical_jobs=1,
        confirmed_duplicates_merged=0,
        potential_duplicate_groups_count=0,
        potential_duplicate_jobs_count=0,
    )

    mock_notif = MockNotificationService()

    with patch(
        "personal_job_hunter.unified_pipeline.run_ingestion_pipeline",
        new=AsyncMock(return_value=(mock_dedup_res, MagicMock())),
    ):
        result = await run_full_unified_pipeline(
            db_url=test_db_url,
            profile=CandidateProfile(),
            notification_svc=mock_notif,
        )

        assert isinstance(result, FullPipelineResult)
        assert result.status == "SUCCESS"
        assert result.canonical_unique_jobs == 1
        assert result.persisted_db_jobs == 1
        assert result.ranked_jobs_count == 1
        assert result.synced_review_count == 1
        assert len(mock_notif.events) >= 1


def test_notification_services_console_and_file(tmp_path: Path) -> None:
    """Verify console and file log notification services."""
    log_file = tmp_path / "test_notif.jsonl"
    file_svc = FileLogNotificationService(log_path=log_file)
    console_svc = ConsoleNotificationService()

    event = NotificationEvent(
        event_type="NEW_HIGH_PRIORITY_JOB",  # type: ignore[arg-type]
        title="Test Alert",
        message="Test message body",
    )

    assert console_svc.notify(event) is True
    assert file_svc.notify(event) is True
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Test Alert" in content
