"""API router for triggering unified pipeline runs."""

import logging

from fastapi import APIRouter

from personal_job_hunter.api.schemas import PipelineTriggerResponse
from personal_job_hunter.unified_pipeline import run_full_unified_pipeline

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])
logger = logging.getLogger("api.pipeline")


@router.post("/run", response_model=PipelineTriggerResponse)
async def trigger_pipeline_run() -> PipelineTriggerResponse:
    """Execute complete unified pipeline run (ingestion -> match -> enrich -> sync)."""
    try:
        res = await run_full_unified_pipeline()
        return PipelineTriggerResponse(
            status=res.status,
            message="Unified pipeline run completed successfully.",
            duration_seconds=res.duration_seconds,
            canonical_jobs_count=res.canonical_unique_jobs,
            apply_targets_count=res.apply_count,
            stretch_opps_count=res.stretch_count,
            enriched_count=res.enriched_jobs_count,
            errors=res.errors,
        )
    except Exception as exc:
        logger.error("Pipeline run failed: %s", exc, exc_info=True)
        return PipelineTriggerResponse(
            status="FAILED",
            message=f"Pipeline failed: {exc}",
            duration_seconds=0.0,
            canonical_jobs_count=0,
            apply_targets_count=0,
            stretch_opps_count=0,
            enriched_count=0,
            errors=[str(exc)],
        )
