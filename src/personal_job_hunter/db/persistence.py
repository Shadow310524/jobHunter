"""Pipeline database persistence coordinator with pgvector embeddings support."""

import logging
from typing import Any

from personal_job_hunter.db.repository import JobRepository, ProfileRepository
from personal_job_hunter.db.session import create_tables, get_db_engine, get_session
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
)
from personal_job_hunter.embeddings.representations import (
    build_candidate_embedding_text,
    build_job_embedding_text,
    compute_content_hash,
)

logger = logging.getLogger("db_persistence")


def persist_pipeline_to_database(
    canonical_jobs: list[CanonicalJobPost],
    match_results: list[JobMatchResult] | None = None,
    profile: CandidateProfile | None = None,
    candidate_embedding: list[float] | None = None,
    job_embeddings: list[list[float]] | None = None,
    model_name: str = "BAAI/bge-small-en-v1.5",
    model_version: str = "1.5",
    db_url: str | None = None,
) -> dict[str, Any]:
    """Persist canonical jobs, source provenance, match scores, embeddings, and candidate profile.

    Args:
        canonical_jobs: List of CanonicalJobPost entities.
        match_results: Optional list of JobMatchResult evaluations.
        profile: CandidateProfile entity. Defaults to default candidate profile.
        candidate_embedding: Optional vector embedding for candidate profile.
        job_embeddings: Optional list of vector embeddings corresponding to canonical_jobs.
        model_name: Model identifier for embeddings.
        model_version: Model version identifier.
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

        # 2. Persist Candidate Profile Embedding if provided
        if candidate_embedding:
            cand_text = build_candidate_embedding_text(active_profile)
            cand_hash = compute_content_hash(cand_text)
            ProfileRepository.upsert_profile_embedding(
                session=session,
                profile_id="default",
                model_name=model_name,
                model_version=model_version,
                content_hash=cand_hash,
                embedding=candidate_embedding,
            )

        # 3. Persist Canonical Jobs and Source Provenance
        jobs_upserted = JobRepository.upsert_canonical_jobs_batch(session, canonical_jobs)
        logger.info("Upserted %d canonical jobs and provenance records", jobs_upserted)

        # 4. Persist Job Embeddings if provided
        embeddings_saved = 0
        if job_embeddings and len(job_embeddings) == len(canonical_jobs):
            for job, vec in zip(canonical_jobs, job_embeddings, strict=False):
                job_text = build_job_embedding_text(job)
                job_hash = compute_content_hash(job_text)
                JobRepository.upsert_job_embedding(
                    session=session,
                    canonical_id=job.canonical_id,
                    model_name=model_name,
                    model_version=model_version,
                    content_hash=job_hash,
                    embedding=vec,
                )
                embeddings_saved += 1
            logger.info("Upserted %d job vector embeddings", embeddings_saved)

        # 5. Persist Match Scores if provided
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
        "job_embeddings_upserted": embeddings_saved,
        "match_scores_upserted": scores_upserted,
        "total_canonical_jobs_in_db": total_db_jobs,
    }
