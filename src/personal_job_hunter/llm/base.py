"""Base LLM service protocol and interfaces."""

from typing import Protocol

from personal_job_hunter.domain.models import CandidateProfile, CanonicalJobPost
from personal_job_hunter.llm.models import JobEnrichmentResult


class BaseLLMService(Protocol):
    """Protocol for structured LLM enrichment providers."""

    @property
    def model_name(self) -> str:
        """Identifier of the LLM model."""
        ...

    @property
    def model_version(self) -> str:
        """Version identifier of the LLM model."""
        ...

    @property
    def provider_name(self) -> str:
        """Name of the provider (e.g. gemini, ollama, mock)."""
        ...

    def enrich_job(self, job: CanonicalJobPost, profile: CandidateProfile) -> JobEnrichmentResult:
        """Generate structured enrichment result for a job post."""
        ...
