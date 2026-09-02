"""Unified Ingestion & Aggregation Pipeline.

Coordinates:
  Collection (Greenhouse, Ashby, Lever)
    ↓
  Normalization (UnifiedJobPost)
    ↓
  Deduplication (CanonicalJobPost)
    ↓
  Persistence (canonical_jobs.json)
    ↓
  Execution Summary & Metrics
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from personal_job_hunter.collectors.ashby import collect_ashby_jobs
from personal_job_hunter.collectors.greenhouse import collect_greenhouse_jobs
from personal_job_hunter.collectors.lever import collect_lever_jobs
from personal_job_hunter.domain.deduplication import deduplicate_jobs
from personal_job_hunter.domain.models import (
    DeduplicationResult,
    JobSource,
    UnifiedJobPost,
)
from personal_job_hunter.domain.normalizers import normalize_job

# Configure logging
logger = logging.getLogger("pipeline")


class SourceExecutionStat(BaseModel):
    """Execution statistics for a single job source."""

    model_config = ConfigDict(use_enum_values=True)

    source: JobSource
    status: str = "SUCCESS"  # "SUCCESS" | "FAILED" | "PARTIAL"
    collected_count: int = 0
    normalized_count: int = 0
    duration_seconds: float = 0.0
    error: str | None = None


class PipelineSummary(BaseModel):
    """Complete summary of a pipeline ingestion execution."""

    model_config = ConfigDict(use_enum_values=True)

    started_at: str
    completed_at: str
    total_duration_seconds: float
    sources_summary: list[SourceExecutionStat] = Field(default_factory=list)
    total_collected_records: int = 0
    total_normalized_records: int = 0
    total_canonical_unique_jobs: int = 0
    confirmed_duplicates_merged: int = 0
    potential_duplicate_groups: int = 0
    output_file: str


async def run_collector_safe(
    source: JobSource, collector_fn: Any
) -> tuple[JobSource, list[dict[str, Any]], float, str | None]:
    """Execute a single collector safely with timing and exception isolation."""
    start_time = time.perf_counter()
    try:
        raw_jobs = await collector_fn()
        duration = time.perf_counter() - start_time
        return source, raw_jobs, duration, None
    except Exception as exc:
        duration = time.perf_counter() - start_time
        logger.error("Collector %s failed: %s", source.value, exc, exc_info=True)
        return source, [], duration, str(exc)


async def run_ingestion_pipeline(
    output_file: Path | None = None,
    greenhouse_companies: list[str] | None = None,
    ashby_companies: list[str] | None = None,
    lever_companies: list[str] | None = None,
) -> tuple[DeduplicationResult, PipelineSummary]:
    """Execute the complete collection -> normalization -> deduplication pipeline.

    Args:
        output_file: Target path for canonical_jobs.json.
        greenhouse_companies: Optional override company list for Greenhouse.
        ashby_companies: Optional override company list for Ashby.
        lever_companies: Optional override company list for Lever.

    Returns:
        Tuple of (DeduplicationResult, PipelineSummary).
    """
    start_wall_time = datetime.now(UTC).isoformat()
    pipeline_start_clock = time.perf_counter()

    default_output_file = (
        output_file
        or Path(__file__).resolve().parent.parent.parent / "data" / "canonical_jobs.json"
    )

    logger.info("Starting Unified Ingestion Pipeline...")

    # 1. Define collectors to run
    tasks = [
        run_collector_safe(
            JobSource.GREENHOUSE,
            lambda: collect_greenhouse_jobs(
                companies=greenhouse_companies, request_delay_seconds=0.2
            ),
        ),
        run_collector_safe(
            JobSource.ASHBY,
            lambda: collect_ashby_jobs(companies=ashby_companies, request_delay_seconds=0.2),
        ),
        run_collector_safe(
            JobSource.LEVER,
            lambda: collect_lever_jobs(companies=lever_companies, request_delay_seconds=0.2),
        ),
    ]

    # 2. Run collectors concurrently with isolation
    results = await asyncio.gather(*tasks)

    # 3. Normalize collected jobs
    all_normalized_jobs: list[UnifiedJobPost] = []
    source_stats: list[SourceExecutionStat] = []

    for source, raw_records, duration, err in results:
        normalized_count = 0
        status = "FAILED" if err else "SUCCESS"

        if raw_records:
            for item in raw_records:
                try:
                    norm_post = normalize_job(item, source)
                    all_normalized_jobs.append(norm_post)
                    normalized_count += 1
                except Exception as norm_err:
                    logger.warning("Failed to normalize record from %s: %s", source.value, norm_err)

        source_stats.append(
            SourceExecutionStat(
                source=source,
                status=status,
                collected_count=len(raw_records),
                normalized_count=normalized_count,
                duration_seconds=round(duration, 2),
                error=err,
            )
        )

    # 4. Deduplicate into CanonicalJobPost entities
    logger.info("Deduplicating %d normalized job records...", len(all_normalized_jobs))
    dedup_result = deduplicate_jobs(all_normalized_jobs)

    # 5. Persist canonical jobs to JSON
    default_output_file.parent.mkdir(parents=True, exist_ok=True)
    serialized_canonical = [job.model_dump(mode="json") for job in dedup_result.canonical_jobs]

    with open(default_output_file, "w", encoding="utf-8") as f:
        json.dump(serialized_canonical, f, indent=2, ensure_ascii=False)

    logger.info("Saved %d canonical jobs to %s", len(serialized_canonical), default_output_file)

    end_wall_time = datetime.now(UTC).isoformat()
    total_duration = time.perf_counter() - pipeline_start_clock

    summary = PipelineSummary(
        started_at=start_wall_time,
        completed_at=end_wall_time,
        total_duration_seconds=round(total_duration, 2),
        sources_summary=source_stats,
        total_collected_records=sum(s.collected_count for s in source_stats),
        total_normalized_records=len(all_normalized_jobs),
        total_canonical_unique_jobs=dedup_result.unique_canonical_jobs,
        confirmed_duplicates_merged=dedup_result.confirmed_duplicates_merged,
        potential_duplicate_groups=dedup_result.potential_duplicate_groups_count,
        output_file=str(default_output_file),
    )

    return dedup_result, summary


def print_pipeline_summary(summary: PipelineSummary) -> None:
    """Print a clean execution summary to the console."""
    print("\n" + "=" * 65)
    print("       PERSONAL AI JOB HUNTER — INGESTION PIPELINE SUMMARY")
    print("=" * 65)
    print(f"Started At:       {summary.started_at}")
    print(f"Completed At:     {summary.completed_at}")
    print(f"Total Duration:   {summary.total_duration_seconds}s")
    print("-" * 65)
    print(f"{'Source':<15} {'Status':<10} {'Collected':<12} {'Normalized':<12} {'Duration'}")
    print("-" * 65)
    for stat in summary.sources_summary:
        print(
            f"{stat.source:<15} {stat.status:<10} "
            f"{stat.collected_count:<12} {stat.normalized_count:<12} {stat.duration_seconds}s"
        )
        if stat.error:
            print(f"  -> Error: {stat.error}")
    print("-" * 65)
    print(f"Total Raw Records Collected:     {summary.total_collected_records}")
    print(f"Total Normalized Job Posts:      {summary.total_normalized_records}")
    print(f"Confirmed Duplicates Merged:     {summary.confirmed_duplicates_merged}")
    print(f"Canonical Unique Jobs Produced:  {summary.total_canonical_unique_jobs}")
    print(f"Potential Duplicate Clusters:    {summary.potential_duplicate_groups}")
    print(f"Canonical Output File:           {summary.output_file}")
    print("=" * 65 + "\n")


async def main() -> None:
    """Entry point for running the complete pipeline from CLI."""
    _, summary = await run_ingestion_pipeline()
    print_pipeline_summary(summary)


if __name__ == "__main__":
    asyncio.run(main())
