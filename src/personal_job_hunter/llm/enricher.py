"""LLM Job Enrichment Engine with Gating, Caching, and Idempotency."""

import hashlib
import logging

from sqlalchemy.orm import Session

from personal_job_hunter.db.repository import EnrichmentRepository
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
    MatchRecommendation,
)
from personal_job_hunter.embeddings.representations import (
    build_candidate_embedding_text,
    build_job_embedding_text,
)
from personal_job_hunter.llm.base import BaseLLMService
from personal_job_hunter.llm.models import JobEnrichmentResult
from personal_job_hunter.llm.prompts import ENRICHMENT_PROMPT_VERSION
from personal_job_hunter.llm.service import get_default_llm_service

logger = logging.getLogger("llm_enricher")


def compute_enrichment_hash(
    job: CanonicalJobPost,
    profile: CandidateProfile,
    model_name: str,
    model_version: str,
    prompt_version: str = ENRICHMENT_PROMPT_VERSION,
) -> str:
    """Compute deterministic SHA-256 hash across all input parameters to guarantee idempotency."""
    job_str = build_job_embedding_text(job)
    cand_str = build_candidate_embedding_text(profile)
    composite = f"{job_str}||{cand_str}||{model_name}||{model_version}||{prompt_version}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


class JobEnrichmentEngine:
    """Orchestrates structured LLM enrichment with strict gating and caching."""

    def __init__(
        self,
        llm_service: BaseLLMService | None = None,
        prompt_version: str = ENRICHMENT_PROMPT_VERSION,
    ) -> None:
        self.llm_service = llm_service or get_default_llm_service()
        self.prompt_version = prompt_version

    def should_enrich(self, match_result: JobMatchResult) -> bool:
        """Gating policy: only enrich high-value APPLY targets or top STRETCH opportunities.

        Deterministically SKIP roles are NEVER enriched (0 compute/tokens spent).
        """
        if match_result.recommendation == MatchRecommendation.SKIP:
            return False
        if match_result.recommendation == MatchRecommendation.APPLY:
            return True
        # For STRETCH: only enrich if overall score is reasonably strong (>= 75.0)
        return match_result.overall_score >= 75.0

    def enrich_job(
        self,
        job: CanonicalJobPost,
        profile: CandidateProfile,
        match_result: JobMatchResult,
        session: Session | None = None,
    ) -> JobEnrichmentResult | None:
        """Enrich a single job if it passes gating, checking DB cache first for idempotency."""
        if not self.should_enrich(match_result):
            logger.debug(
                "Skipping LLM enrichment for job '%s' (Gating: recommendation=%s, score=%.1f)",
                job.title,
                match_result.recommendation,
                match_result.overall_score,
            )
            return None

        content_hash = compute_enrichment_hash(
            job=job,
            profile=profile,
            model_name=self.llm_service.model_name,
            model_version=self.llm_service.model_version,
            prompt_version=self.prompt_version,
        )

        # Check DB cache if session provided
        if session is not None:
            cached = EnrichmentRepository.get_enrichment(
                session=session,
                canonical_id=job.canonical_id,
                model_name=self.llm_service.model_name,
                prompt_version=self.prompt_version,
            )
            if cached and cached.content_hash == content_hash:
                logger.info(
                    "Loaded cached LLM enrichment for '%s' from DB (Hash: %s...)",
                    job.title,
                    content_hash[:8],
                )
                return JobEnrichmentResult.model_validate(cached.enrichment_data)

        # Call LLM
        logger.info("Executing LLM enrichment for '%s' @ '%s'...", job.title, job.company)
        enrichment = self.llm_service.enrich_job(job, profile)

        # Persist to DB if session provided
        if session is not None:
            EnrichmentRepository.upsert_enrichment(
                session=session,
                canonical_id=job.canonical_id,
                model_name=self.llm_service.model_name,
                model_version=self.llm_service.model_version,
                prompt_version=self.prompt_version,
                content_hash=content_hash,
                enrichment_data=enrichment.model_dump(mode="json"),
            )
            session.flush()

        return enrichment

    def enrich_batch(
        self,
        ranked_jobs: list[tuple[CanonicalJobPost, JobMatchResult]],
        profile: CandidateProfile,
        session: Session | None = None,
    ) -> dict[str, JobEnrichmentResult]:
        """Enrich a batch of ranked jobs subject to gating and caching."""
        enriched_map: dict[str, JobEnrichmentResult] = {}
        for job, match_res in ranked_jobs:
            if self.should_enrich(match_res):
                res = self.enrich_job(
                    job=job,
                    profile=profile,
                    match_result=match_res,
                    session=session,
                )
                if res is not None:
                    enriched_map[job.canonical_id] = res
        return enriched_map
