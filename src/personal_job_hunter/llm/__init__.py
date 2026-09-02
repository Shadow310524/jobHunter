"""LLM package: structured job enrichment, prompts, and providers."""

from personal_job_hunter.llm.base import BaseLLMService
from personal_job_hunter.llm.enricher import JobEnrichmentEngine, compute_enrichment_hash
from personal_job_hunter.llm.models import JobEnrichmentResult, LLMEnrichmentRecord
from personal_job_hunter.llm.prompts import ENRICHMENT_PROMPT_VERSION, SYSTEM_PROMPT
from personal_job_hunter.llm.service import (
    GeminiLLMService,
    MockLLMService,
    OllamaLLMService,
    get_default_llm_service,
)

__all__ = [
    "ENRICHMENT_PROMPT_VERSION",
    "BaseLLMService",
    "GeminiLLMService",
    "JobEnrichmentEngine",
    "JobEnrichmentResult",
    "LLMEnrichmentRecord",
    "MockLLMService",
    "OllamaLLMService",
    "SYSTEM_PROMPT",
    "compute_enrichment_hash",
    "get_default_llm_service",
]
