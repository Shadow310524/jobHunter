"""Semantic & Hybrid Job Matcher (Phase 7).

Combines deterministic multi-factor evaluation (Phase 5B) with pgvector-compatible
semantic similarity embedding retrieval. Hard safety gates remain authoritative.
"""

import logging
import math
from collections.abc import Sequence

from personal_job_hunter.domain.matcher import match_job
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
    MatchRecommendation,
    MatchWeights,
)
from personal_job_hunter.embeddings.base import BaseEmbeddingService
from personal_job_hunter.embeddings.representations import (
    build_candidate_embedding_text,
    build_job_embedding_text,
)
from personal_job_hunter.embeddings.service import get_default_embedding_service

logger = logging.getLogger("semantic_matcher")


def compute_cosine_similarity(vec1: Sequence[float], vec2: Sequence[float]) -> float:
    """Compute cosine similarity between two float vectors.

    Returns:
        float in range [0.0, 1.0] (clamped to 0.0 for negative cosine).
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    similarity = dot_product / (norm_a * norm_b)
    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, float(similarity)))


def match_job_hybrid(
    job: CanonicalJobPost,
    profile: CandidateProfile | None = None,
    candidate_embedding: list[float] | None = None,
    job_embedding: list[float] | None = None,
    embedding_service: BaseEmbeddingService | None = None,
    weights: MatchWeights | None = None,
) -> tuple[JobMatchResult, list[float], list[float]]:
    """Evaluate a job using hybrid deterministic + semantic matching.

    Returns:
        (JobMatchResult, candidate_embedding, job_embedding)
    """
    active_profile = profile or CandidateProfile()
    active_weights = weights or MatchWeights()
    svc = embedding_service or get_default_embedding_service()

    # 1. Deterministic baseline match (Phase 5B)
    det_result = match_job(job, active_profile, active_weights)
    bd = det_result.breakdown
    det_score = det_result.overall_score

    # 2. Embedding generation if not supplied
    cand_vec = (
        candidate_embedding
        if candidate_embedding is not None
        else svc.embed_text(build_candidate_embedding_text(active_profile))
    )
    job_vec = (
        job_embedding
        if job_embedding is not None
        else svc.embed_text(build_job_embedding_text(job))
    )

    # 3. Semantic similarity calculation
    similarity = compute_cosine_similarity(cand_vec, job_vec)
    semantic_score = round(similarity * 100.0, 1)

    # 4. Combined scoring
    final_score = round(
        (active_weights.deterministic_weight * det_score)
        + (active_weights.semantic_weight * semantic_score),
        1,
    )

    # Update breakdown with audit trails
    bd.deterministic_score = det_score
    bd.semantic_score = semantic_score
    bd.semantic_similarity = round(similarity, 4)
    bd.final_score = final_score
    bd.overall_score = final_score

    score_reasons = list(bd.score_reasons)
    score_reasons.append(
        f"Semantic Similarity: {similarity:.4f} (Score: {semantic_score:.1f}/100, "
        f"Model: {svc.model_name}:{svc.model_version})."
    )
    score_reasons.append(
        f"Combined Score: {final_score:.1f}/100 "
        f"({active_weights.deterministic_weight * 100:.0f}% Det [{det_score:.1f}] + "
        f"{active_weights.semantic_weight * 100:.0f}% Sem [{semantic_score:.1f}])."
    )

    # 5. Authoritative Safety Gate Decisions
    # Rule A: If deterministic evaluation was SKIP, it CANNOT be promoted by semantic score
    if det_result.recommendation == MatchRecommendation.SKIP:
        recommendation = MatchRecommendation.SKIP
        score_reasons.append(
            "Final Decision: SKIP (Hard safety gate: failed deterministic eligibility)."
        )
    else:
        # Rule B: Strict APPLY Criteria
        is_apply = (
            final_score >= active_weights.apply_threshold
            and det_score >= 78.0
            and semantic_score >= 65.0
            and bd.role_score >= 85.0
            and bd.technical_score >= 70.0
            and bd.experience_eligible is True
            and bd.location_eligible is True
        )
        if is_apply:
            recommendation = MatchRecommendation.APPLY
            score_reasons.append(
                "Final Decision: APPLY (High-priority target: passed deterministic gates and "
                "strong semantic alignment)."
            )
        elif (
            final_score >= active_weights.stretch_threshold
            and bd.role_score >= 65.0
            and bd.location_score >= 45.0
            and bd.experience_score >= 30.0
        ):
            recommendation = MatchRecommendation.STRETCH
            score_reasons.append(
                "Final Decision: STRETCH (Viable opportunity: relevant technical alignment with "
                "stretch experience or location parameters)."
            )
        else:
            recommendation = MatchRecommendation.SKIP
            score_reasons.append(
                "Final Decision: SKIP (Did not achieve minimum hybrid score threshold)."
            )

    bd.score_reasons = score_reasons

    hybrid_result = JobMatchResult(
        canonical_id=job.canonical_id,
        job_title=job.title,
        company=job.company,
        location=job.location,
        recommendation=recommendation,
        overall_score=final_score,
        breakdown=bd,
        application_urls=job.application_urls,
    )
    return hybrid_result, cand_vec, job_vec


def match_all_jobs_hybrid(
    jobs: list[CanonicalJobPost],
    profile: CandidateProfile | None = None,
    embedding_service: BaseEmbeddingService | None = None,
    weights: MatchWeights | None = None,
) -> list[tuple[JobMatchResult, list[float], list[float]]]:
    """Evaluate and rank all jobs using batch embedding generation and hybrid scoring."""
    if not jobs:
        return []

    active_profile = profile or CandidateProfile()
    svc = embedding_service or get_default_embedding_service()

    # 1. Embed candidate profile once
    cand_text = build_candidate_embedding_text(active_profile)
    cand_vec = svc.embed_text(cand_text)

    # 2. Batch embed all jobs
    job_texts = [build_job_embedding_text(j) for j in jobs]
    job_vectors = svc.embed_texts(job_texts)

    results: list[tuple[JobMatchResult, list[float], list[float]]] = []
    for job, job_vec in zip(jobs, job_vectors, strict=False):
        res, c_vec, j_vec = match_job_hybrid(
            job=job,
            profile=active_profile,
            candidate_embedding=cand_vec,
            job_embedding=job_vec,
            embedding_service=svc,
            weights=weights,
        )
        results.append((res, c_vec, j_vec))

    # Sort descending by final combined overall_score
    results.sort(key=lambda x: x[0].overall_score, reverse=True)
    return results
