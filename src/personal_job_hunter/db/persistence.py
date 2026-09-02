"""Pipeline database persistence coordinator."""

import logging
from typing import Any

from personal_job_hunter.db.repository import JobRepository, ProfileRepository
from personal_job_hunter.db.session import create_tables, get_db_engine, get_session
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
)

logger = logging.getLogger("db_persistence")


def persist_pipeline_to_database(
    canonical_jobs: list[CanonicalJobPost],
    match_results: list[JobMatchResult] | None = None,
    profile: CandidateProfile | None = None,
    db_url: str | None = None,
) -> dict[str, Any]:
    """Persist canonical jobs, source provenance, match scores, and candidate profile to database.

    Args:
        canonical_jobs: List of CanonicalJobPost entities.
        match_results: Optional list of JobMatchResult evaluations.
        profile: CandidateProfile entity. Defaults to default candidate profile.
        db_url: Database connection URL. Defaults to configured environment database URL.

    Returns:
        Summary dict containing counts of persisted entities.
    """
    active_profile = profile or CandidateProfile()
    engine = get_db_engine(db_url)
    logger.info("Initializing database tables...")
    create_tables(engine)

    with get_session(db_url) as session:
        # 1. Persist Candidate Profile
        profile_model = ProfileRepository.save_profile(
            session, active_profile, profile_id="default"
        )
        logger.info("Persisted candidate profile for: %s", profile_model.name)

        # 2. Persist Canonical Jobs and Source Provenance
        jobs_upserted = JobRepository.upsert_canonical_jobs_batch(session, canonical_jobs)
        logger.info("Upserted %d canonical jobs and provenance records", jobs_upserted)

        # 3. Persist Match Scores if provided
        scores_upserted = 0
        if match_results:
            scores_upserted = JobRepository.save_match_scores_batch(
                session, match_results, profile_id="default"
            )
            logger.info("Upserted %d job match score evaluations", scores_upserted)

        total_db_jobs = JobRepository.get_total_job_count(session)

    return {
        "status": "SUCCESS",
        "profile_id": "default",
        "canonical_jobs_upserted": jobs_upserted,
        "match_scores_upserted": scores_upserted,
        "total_canonical_jobs_in_db": total_db_jobs,
    }
