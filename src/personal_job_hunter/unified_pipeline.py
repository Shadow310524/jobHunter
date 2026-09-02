"""Unified End-to-End Autonomous Job Hunter Pipeline (Phases 1-10)."""

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

from personal_job_hunter.db.persistence import persist_pipeline_to_database
from personal_job_hunter.db.session import create_tables, get_db_engine, get_session
from personal_job_hunter.domain.models import (
    CandidateProfile,
    MatchRecommendation,
)
from personal_job_hunter.domain.semantic_matcher import match_all_jobs_hybrid
from personal_job_hunter.embeddings.service import get_default_embedding_service
from personal_job_hunter.llm.enricher import JobEnrichmentEngine
from personal_job_hunter.llm.service import get_default_llm_service
from personal_job_hunter.notifications import (
    BaseNotificationService,
    NotificationEvent,
    NotificationType,
    get_default_notification_service,
)
from personal_job_hunter.pipeline import run_ingestion_pipeline
from personal_job_hunter.tracking.manager import ApplicationTracker

logger = logging.getLogger("unified_pipeline")


class FullPipelineResult:
    """Detailed telemetry and execution metrics of a unified pipeline run."""

    def __init__(self) -> None:
        self.started_at: str = datetime.now(UTC).isoformat()
        self.completed_at: str = ""
        self.duration_seconds: float = 0.0
        self.collected_raw_jobs: int = 0
        self.canonical_unique_jobs: int = 0
        self.persisted_db_jobs: int = 0
        self.ranked_jobs_count: int = 0
        self.apply_count: int = 0
        self.stretch_count: int = 0
        self.skip_count: int = 0
        self.enriched_jobs_count: int = 0
        self.synced_review_count: int = 0
        self.notifications_sent: int = 0
        self.status: str = "SUCCESS"
        self.errors: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "collected_raw_jobs": self.collected_raw_jobs,
            "canonical_unique_jobs": self.canonical_unique_jobs,
            "persisted_db_jobs": self.persisted_db_jobs,
            "ranked_jobs_count": self.ranked_jobs_count,
            "apply_count": self.apply_count,
            "stretch_count": self.stretch_count,
            "skip_count": self.skip_count,
            "enriched_jobs_count": self.enriched_jobs_count,
            "synced_review_count": self.synced_review_count,
            "notifications_sent": self.notifications_sent,
            "status": self.status,
            "errors": self.errors,
        }


async def run_full_unified_pipeline(
    db_url: str | None = None,
    profile: CandidateProfile | None = None,
    notification_svc: BaseNotificationService | None = None,
    greenhouse_companies: list[str] | None = None,
    ashby_companies: list[str] | None = None,
    lever_companies: list[str] | None = None,
) -> FullPipelineResult:
    """Execute complete end-to-end pipeline:

    Collect -> Deduplicate -> Persist -> Hybrid Match -> LLM Enrich -> HITL Review Sync -> Notify
    """
    result = FullPipelineResult()
    start_clock = time.perf_counter()
    active_profile = profile or CandidateProfile()
    notif = notification_svc or get_default_notification_service()

    engine = get_db_engine(db_url)
    create_tables(engine)

    try:
        # Step 1: Collect & Deduplicate
        logger.info("Executing Step 1: Multi-ATS Ingestion & Deduplication...")
        dedup_res, _ingest_summary = await run_ingestion_pipeline(
            greenhouse_companies=greenhouse_companies,
            ashby_companies=ashby_companies,
            lever_companies=lever_companies,
        )
        canonical_jobs = dedup_res.canonical_jobs
        result.canonical_unique_jobs = len(canonical_jobs)

        # Step 2: Hybrid Semantic Matching + pgvector Embeddings
        logger.info("Executing Step 2: FastEmbed + pgvector Hybrid Ranking...")
        embedding_svc = get_default_embedding_service()
        ranked_triplets = match_all_jobs_hybrid(
            jobs=canonical_jobs,
            profile=active_profile,
            embedding_service=embedding_svc,
        )
        result.ranked_jobs_count = len(ranked_triplets)

        match_results = [r[0] for r in ranked_triplets]
        job_embeddings = [r[2] for r in ranked_triplets]
        cand_embedding = ranked_triplets[0][1] if ranked_triplets else None

        # Count recommendations
        for match_res in match_results:
            if match_res.recommendation == MatchRecommendation.APPLY:
                result.apply_count += 1
            elif match_res.recommendation == MatchRecommendation.STRETCH:
                result.stretch_count += 1
            else:
                result.skip_count += 1

        # Step 3: Database Batch Persistence (Canonical + Provenance + Match + Embeddings)
        logger.info("Executing Step 3: PostgreSQL Batch Persistence...")
        persist_pipeline_to_database(
            canonical_jobs=canonical_jobs,
            match_results=match_results,
            profile=active_profile,
            candidate_embedding=cand_embedding,
            job_embeddings=job_embeddings,
            db_url=db_url,
        )
        result.persisted_db_jobs = len(canonical_jobs)

        with get_session(db_url) as session:
            # Step 4: Gated LLM Enrichment
            logger.info("Executing Step 4: Gated LLM Enrichment on Target Opportunities...")
            jobs_by_id = {j.canonical_id: j for j in canonical_jobs}
            ranked_pairs = [
                (jobs_by_id[r.canonical_id], r)
                for r in match_results
                if r.canonical_id in jobs_by_id
            ]
            try:
                llm_engine = JobEnrichmentEngine(llm_service=get_default_llm_service())
                enriched_map = llm_engine.enrich_batch(
                    ranked_jobs=ranked_pairs,
                    profile=active_profile,
                    session=session,
                )
                result.enriched_jobs_count = len(enriched_map)
            except Exception as llm_err:
                logger.warning("LLM enrichment failed gracefully (non-fatal): %s", llm_err)
                result.errors.append(f"LLM Enrichment Warning: {llm_err}")

            # Step 5: Sync HITL Review Queue
            logger.info("Executing Step 5: Syncing Human Review Queue...")
            synced = ApplicationTracker.sync_pipeline_jobs(
                session=session,
                jobs=canonical_jobs,
                match_results=match_results,
            )
            result.synced_review_count = synced
            session.commit()

            # Step 6: Notifications
            logger.info("Executing Step 6: Dispatching Pipeline Notifications...")
            try:
                if result.apply_count > 0:
                    notif.notify(
                        NotificationEvent(
                            event_type=NotificationType.NEW_HIGH_PRIORITY_JOB,
                            title=f"Discovered {result.apply_count} High-Priority APPLY Jobs",
                            message=(
                                f"Pipeline identified {result.apply_count} prime targets "
                                f"and {result.stretch_count} stretch opportunities."
                            ),
                            metadata={"apply_count": result.apply_count},
                        )
                    )
                    result.notifications_sent += 1
            except Exception as notif_err:
                logger.warning("Notification dispatch failed gracefully: %s", notif_err)

    except Exception as exc:
        logger.error("Unified pipeline encountered critical failure: %s", exc, exc_info=True)
        result.status = "FAILED"
        result.errors.append(str(exc))
        raise

    finally:
        result.completed_at = datetime.now(UTC).isoformat()
        result.duration_seconds = round(time.perf_counter() - start_clock, 2)

    return result


def print_full_pipeline_summary(res: FullPipelineResult) -> None:
    """Print high-level execution telemetry to console."""
    print("\n" + "=" * 70)
    print("     PERSONAL AI JOB HUNTER -- UNIFIED PIPELINE EXECUTION")
    print("=" * 70)
    print(f"Status:               {res.status}")
    print(f"Started At:           {res.started_at}")
    print(f"Completed At:         {res.completed_at}")
    print(f"Total Duration:       {res.duration_seconds}s")
    print("-" * 70)
    print(f"Canonical Jobs:       {res.canonical_unique_jobs}")
    print(f"Persisted to DB:      {res.persisted_db_jobs}")
    print(f"Hybrid Ranked:        {res.ranked_jobs_count}")
    print(f"  [APPLY] Targets:    {res.apply_count}")
    print(f"  [STRETCH] Opps:     {res.stretch_count}")
    print(f"  [SKIP] Disqualified:{res.skip_count}")
    print(f"LLM Enriched:         {res.enriched_jobs_count}")
    print(f"HITL Review Queue:    {res.synced_review_count} pending decision")
    print(f"Notifications Sent:   {res.notifications_sent}")
    if res.errors:
        print("\nWarnings / Errors:")
        for e in res.errors:
            print(f"  - {e}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    summary = asyncio.run(run_full_unified_pipeline())
    print_full_pipeline_summary(summary)
