"""Unit tests for semantic matcher, vector embeddings, cosine math, and safety gates."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from personal_job_hunter.db.models import Base
from personal_job_hunter.db.repository import JobRepository, ProfileRepository
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobSource,
    MatchRecommendation,
    MatchWeights,
    WorkMode,
)
from personal_job_hunter.domain.semantic_matcher import (
    compute_cosine_similarity,
    match_all_jobs_hybrid,
    match_job_hybrid,
)
from personal_job_hunter.embeddings.representations import (
    build_candidate_embedding_text,
    build_job_embedding_text,
    compute_content_hash,
)
from personal_job_hunter.embeddings.service import MockEmbeddingService


def create_sample_job(
    canonical_id: str = "canon_sem_1",
    title: str = "AI Engineer",
    company: str = "Databricks",
    location: str = "Bengaluru, India",
    description: str = "Build LLM agents with Python, FastAPI, and Docker.",
    inferred_skills: list[str] | None = None,
) -> CanonicalJobPost:
    return CanonicalJobPost(
        canonical_id=canonical_id,
        title=title,
        company=company,
        location=location,
        work_mode=WorkMode.ONSITE,
        description=description,
        inferred_skills=inferred_skills or ["Python", "FastAPI"],
        sources=[JobSource.GREENHOUSE],
        application_urls=["https://example.com/apply"],
    )


def test_build_representations_and_content_hash() -> None:
    """Verify representation builders and deterministic content hash."""
    profile = CandidateProfile(name="Harish Renganathan")
    cand_text = build_candidate_embedding_text(profile)
    assert "Target Roles:" in cand_text
    assert "Harish Renganathan" not in cand_text  # Privacy: excludes personal name
    assert "AVASOFT" in cand_text

    job = create_sample_job()
    job_text = build_job_embedding_text(job)
    assert "Role: AI Engineer" in job_text
    assert "Databricks" in job_text

    hash1 = compute_content_hash(job_text)
    hash2 = compute_content_hash(job_text)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_mock_embedding_service_properties() -> None:
    """Verify mock embedding service generates normalized vectors of fixed dimension."""
    svc = MockEmbeddingService(dimension=32)
    assert svc.dimension == 32
    assert svc.model_name == "mock-model-small"

    vec = svc.embed_text("Test query text")
    assert len(vec) == 32
    norm = sum(x * x for x in vec)
    assert round(norm, 4) == 1.0


def test_cosine_similarity_math() -> None:
    """Verify cosine similarity calculation on known vectors."""
    # Identical vectors
    v1 = [1.0, 0.0, 0.0]
    assert compute_cosine_similarity(v1, v1) == 1.0

    # Orthogonal vectors
    v2 = [0.0, 1.0, 0.0]
    assert compute_cosine_similarity(v1, v2) == 0.0

    # Opposite vectors (clamped to 0.0)
    v3 = [-1.0, 0.0, 0.0]
    assert compute_cosine_similarity(v1, v3) == 0.0

    # Empty or mismatched vectors
    assert compute_cosine_similarity([], v1) == 0.0
    assert compute_cosine_similarity(v1, [1.0, 0.0]) == 0.0


def test_hard_safety_gates_authoritative_over_semantic_score() -> None:
    """Verify disqualified jobs (e.g. Sales) remain SKIP regardless of semantic score."""
    disqualified_job = create_sample_job(
        title="Sales Account Executive",
        location="Bengaluru, India",
        description="Sell AI products and services to enterprise clients.",
    )

    svc = MockEmbeddingService()
    res, _, _ = match_job_hybrid(
        job=disqualified_job,
        embedding_service=svc,
    )

    # Even if semantic similarity exists, hard safety gate must enforce SKIP
    assert res.recommendation == MatchRecommendation.SKIP
    assert res.breakdown.deterministic_score is not None
    assert res.breakdown.semantic_score is not None
    assert any("Hard safety gate" in r for r in res.breakdown.score_reasons)


def test_hybrid_scoring_combination_and_apply() -> None:
    """Verify combined score calculation (70% deterministic + 30% semantic)."""
    job = create_sample_job(
        title="AI Platform Engineer",
        company="Supabase",
        location="Bengaluru, India",
        description="Build LLM and agentic platforms with Python, FastAPI, and pgvector.",
        inferred_skills=["Python", "FastAPI", "pgvector", "AI Agents"],
    )

    svc = MockEmbeddingService()
    weights = MatchWeights(deterministic_weight=0.70, semantic_weight=0.30)
    res, c_vec, j_vec = match_job_hybrid(
        job=job,
        embedding_service=svc,
        weights=weights,
    )

    assert res.recommendation == MatchRecommendation.APPLY
    assert res.breakdown.deterministic_score is not None
    assert res.breakdown.semantic_score is not None
    assert res.breakdown.semantic_similarity is not None

    expected_combined = round(
        (0.70 * res.breakdown.deterministic_score) + (0.30 * res.breakdown.semantic_score), 1
    )
    assert res.overall_score == expected_combined


def test_match_all_jobs_hybrid_batch_sorting() -> None:
    """Verify match_all_jobs_hybrid sorts output descending by combined score."""
    job1 = create_sample_job(
        title="AI Engineer",
        description="Python, FastAPI, LangChain, AI Agents.",
    )
    job2 = create_sample_job(
        title="Support Engineer",
        description="Resolve customer tickets.",
    )

    svc = MockEmbeddingService()
    results = match_all_jobs_hybrid([job2, job1], embedding_service=svc)

    assert len(results) == 2
    assert results[0][0].overall_score >= results[1][0].overall_score
    assert results[0][0].job_title == "AI Engineer"
    assert results[1][0].recommendation == MatchRecommendation.SKIP


def test_vector_persistence_and_idempotency() -> None:
    """Verify vector embeddings are saved to DB and respect content hashes & model versions."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        # Create profile and job
        ProfileRepository.save_profile(session, CandidateProfile(), profile_id="default")
        job = create_sample_job(canonical_id="canon_vector_test")
        JobRepository.upsert_canonical_job(session, job)
        session.commit()

        # Insert job embedding
        emb1 = [0.1 * i for i in range(384)]
        saved_emb = JobRepository.upsert_job_embedding(
            session=session,
            canonical_id="canon_vector_test",
            model_name="bge-small-en-v1.5",
            model_version="1.5",
            content_hash="hash_v1",
            embedding=emb1,
        )
        session.commit()

        assert saved_emb.id is not None
        assert saved_emb.content_hash == "hash_v1"

        # Re-upserting identical hash does not overwrite or duplicate
        saved_emb2 = JobRepository.upsert_job_embedding(
            session=session,
            canonical_id="canon_vector_test",
            model_name="bge-small-en-v1.5",
            model_version="1.5",
            content_hash="hash_v1",
            embedding=emb1,
        )
        session.commit()
        assert saved_emb2.id == saved_emb.id

        # Text modification with new content hash updates vector
        emb2 = [0.2 * i for i in range(384)]
        updated_emb = JobRepository.upsert_job_embedding(
            session=session,
            canonical_id="canon_vector_test",
            model_name="bge-small-en-v1.5",
            model_version="1.5",
            content_hash="hash_v2",
            embedding=emb2,
        )
        session.commit()
        assert updated_emb.id == saved_emb.id
        assert updated_emb.content_hash == "hash_v2"

        # Different model version is tracked separately
        diff_ver_emb = JobRepository.upsert_job_embedding(
            session=session,
            canonical_id="canon_vector_test",
            model_name="bge-small-en-v1.5",
            model_version="2.0",
            content_hash="hash_v1",
            embedding=emb1,
        )
        session.commit()
        assert diff_ver_emb.id != saved_emb.id
        assert diff_ver_emb.model_version == "2.0"
