"""Concrete LLM enrichment service implementations."""

import json
import logging
import os
import re
from typing import Any

import httpx

from personal_job_hunter.domain.models import CandidateProfile, CanonicalJobPost
from personal_job_hunter.llm.models import JobEnrichmentResult
from personal_job_hunter.llm.prompts import SYSTEM_PROMPT, build_enrichment_user_prompt

logger = logging.getLogger("llm_service")


class MockLLMService:
    """Deterministic mock LLM service for fast offline unit testing without API calls."""

    def __init__(
        self,
        model_name: str = "mock-llm-flash",
        model_version: str = "1.0",
    ) -> None:
        self._model_name = model_name
        self._model_version = model_version

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def provider_name(self) -> str:
        return "mock"

    def enrich_job(self, job: CanonicalJobPost, profile: CandidateProfile) -> JobEnrichmentResult:
        """Generate structured enrichment derived deterministically from job and profile."""
        skills_stated = list(job.inferred_skills) or ["Python", "Engineering"]
        cand_core = set(profile.core_skills)
        matched = [s for s in skills_stated if s in cand_core]
        missing = [s for s in skills_stated if s not in cand_core]

        summary = (
            f"{job.company} is hiring a {job.title} in {job.location} "
            "focusing on technical systems."
        )
        responsibilities = [
            f"Build and maintain {job.title} systems and core platform workflows.",
            f"Collaborate with engineering teams at {job.company} to deliver production features.",
        ]
        qualifications = [
            f"Hands-on technical experience with {', '.join(skills_stated[:3])}.",
            "Demonstrated problem-solving and software engineering capabilities.",
        ]

        strengths = [
            (
                f"Direct proficiency in {', '.join(matched)}"
                if matched
                else "Strong Python and backend fundamentals"
            ),
            "Practical AI Platform Engineering experience at AVASOFT",
        ]
        gaps = [
            f"Potential ramp-up needed on {', '.join(missing)}" if missing else "None identified",
        ]
        transferable = [
            "Building multi-agent AI systems and REST APIs applies directly to this tech stack.",
        ]
        talking_points = [
            f"Discuss building agentic RAG at AVASOFT relevant to {job.company}'s platform.",
            "Highlight experience with PostgreSQL, FastAPI, and Docker in production.",
        ]

        return JobEnrichmentResult(
            job_summary=summary,
            key_responsibilities=responsibilities,
            stated_qualifications=qualifications,
            inferred_technical_focus=skills_stated[:4],
            candidate_strengths=strengths,
            gap_analysis=gaps,
            transferable_skills=transferable,
            ambiguity_flags=[],
            interview_talking_points=talking_points,
            confidence_score=0.92,
            is_company_stated_fact_verified=True,
        )


class GeminiLLMService:
    """Google Gemini API service with native structured JSON output."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-1.5-flash",
        model_version: str = "1.5",
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model_name = model_name
        self._model_version = model_version
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def provider_name(self) -> str:
        return "gemini"

    def enrich_job(self, job: CanonicalJobPost, profile: CandidateProfile) -> JobEnrichmentResult:
        """Call Gemini API requesting structured JSON conforming to JobEnrichmentResult."""
        if not self._api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        user_prompt = build_enrichment_user_prompt(job, profile)
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_name}:generateContent"
            f"?key={self._api_key}"
        )

        schema = JobEnrichmentResult.model_json_schema()
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_prompt}"}],
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": schema,
                "temperature": 0.1,
            },
        }

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)
            return JobEnrichmentResult.model_validate(parsed)
        except Exception as e:
            logger.error("Failed to parse Gemini structured response: %s", e)
            raise ValueError(f"Failed to parse Gemini structured response: {e}") from e


class OllamaLLMService:
    """Local Ollama LLM service for 100% offline structured inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "llama3:latest",
        model_version: str = "3.0",
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._model_version = model_version
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def provider_name(self) -> str:
        return "ollama"

    def enrich_job(self, job: CanonicalJobPost, profile: CandidateProfile) -> JobEnrichmentResult:
        """Call Ollama API with JSON format enforcement."""
        user_prompt = build_enrichment_user_prompt(job, profile)
        schema_json = json.dumps(JobEnrichmentResult.model_json_schema())
        full_prompt = f"{SYSTEM_PROMPT}\n\nSchema Requirements:\n{schema_json}\n\n{user_prompt}"

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model_name,
                    "prompt": full_prompt,
                    "format": "json",
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        try:
            raw_text = data.get("response", "{}")
            # Extract JSON substring if wrapped
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            clean_json = json_match.group(0) if json_match else raw_text
            parsed = json.loads(clean_json)
            return JobEnrichmentResult.model_validate(parsed)
        except Exception as e:
            logger.error("Failed to parse Ollama structured response: %s", e)
            raise ValueError(f"Failed to parse Ollama response: {e}") from e


def get_default_llm_service(use_mock: bool = False) -> Any:
    """Factory to retrieve appropriate LLM service."""
    if use_mock:
        return MockLLMService()
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        return GeminiLLMService(api_key=gemini_key)
    return MockLLMService()
