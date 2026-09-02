"""Concrete embedding services: FastEmbed local CPU service and Mock testing service."""

import math
from typing import Any

from personal_job_hunter.embeddings.base import BaseEmbeddingService


class FastEmbedService:
    """Local, lightweight, CPU-optimized embedding service powered by FastEmbed & ONNX."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        model_version: str = "1.5",
        dimension: int = 384,
    ) -> None:
        self._model_name = model_name
        self._model_version = model_version
        self._dimension = dimension
        self._model: Any = None

    def _get_model(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for single text."""
        model = self._get_model()
        vectors = list(model.embed([text]))
        return [float(x) for x in vectors[0]]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for batch of texts."""
        if not texts:
            return []
        model = self._get_model()
        vectors = list(model.embed(texts))
        return [[float(x) for x in vec] for vec in vectors]


class MockEmbeddingService:
    """Deterministic mock embedding service for unit testing without ONNX/network overhead."""

    def __init__(
        self,
        model_name: str = "mock-model-small",
        model_version: str = "1.0",
        dimension: int = 16,
    ) -> None:
        self._model_name = model_name
        self._model_version = model_version
        self._dimension = dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def dimension(self) -> int:
        return self._dimension

    def _hash_text_to_vector(self, text: str) -> list[float]:
        """Create a deterministic normalized float vector derived from text content."""
        clean = text.lower().strip()
        vec: list[float] = []
        for i in range(self._dimension):
            # Seed value combining text length, character values, and index
            val = sum((ord(c) * (i + 1) * (idx + 1)) % 100 for idx, c in enumerate(clean[:30]))
            vec.append(float(val % 50 + 1))

        # L2 Normalize vector
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_text(self, text: str) -> list[float]:
        return self._hash_text_to_vector(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_text_to_vector(t) for t in texts]


def get_default_embedding_service(use_mock: bool = False) -> BaseEmbeddingService:
    """Factory to retrieve default embedding service."""
    if use_mock:
        return MockEmbeddingService()
    return FastEmbedService()
