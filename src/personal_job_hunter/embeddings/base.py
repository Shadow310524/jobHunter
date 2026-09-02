"""Base embedding service interfaces and data types."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingResult:
    """Result of embedding generation."""

    text: str
    content_hash: str
    embedding: list[float]
    model_name: str
    model_version: str


class BaseEmbeddingService(Protocol):
    """Protocol for embedding generation providers."""

    @property
    def model_name(self) -> str:
        """Name of the underlying embedding model."""
        ...

    @property
    def model_version(self) -> str:
        """Version identifier of the embedding model."""
        ...

    @property
    def dimension(self) -> int:
        """Dimension size of the embedding vector."""
        ...

    def embed_text(self, text: str) -> list[float]:
        """Generate vector embedding for a single text."""
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of texts in batch."""
        ...
