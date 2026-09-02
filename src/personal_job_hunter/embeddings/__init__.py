"""Embeddings package: interfaces, local fastembed service, mock service, and builders."""

from personal_job_hunter.embeddings.base import BaseEmbeddingService, EmbeddingResult
from personal_job_hunter.embeddings.representations import (
    build_candidate_embedding_text,
    build_job_embedding_text,
    compute_content_hash,
)
from personal_job_hunter.embeddings.service import (
    FastEmbedService,
    MockEmbeddingService,
    get_default_embedding_service,
)

__all__ = [
    "BaseEmbeddingService",
    "EmbeddingResult",
    "FastEmbedService",
    "MockEmbeddingService",
    "build_candidate_embedding_text",
    "build_job_embedding_text",
    "compute_content_hash",
    "get_default_embedding_service",
]
