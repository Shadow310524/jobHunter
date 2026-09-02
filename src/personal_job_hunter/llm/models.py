"""Structured schemas for LLM job enrichment (Phase 8)."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class JobEnrichmentResult(BaseModel):
    """Strict structured schema for LLM-powered job enrichment.

    Carefully distinguishes COMPANY-STATED FACTS from MODEL INFERENCE.
    """

    model_config = ConfigDict(use_enum_values=True)

    # 1. Company-Stated Ground Truth (Directly extracted without hallucination)
    job_summary: str = Field(
        ...,
        description="Concise 1-2 sentence summary strictly based on description.",
    )
    key_responsibilities: list[str] = Field(
        default_factory=list,
        description="Key responsibilities explicitly stated by employer.",
    )
    stated_qualifications: list[str] = Field(
        default_factory=list,
        description="Explicit required qualifications stated by employer.",
    )

    # 2. Model Inferences & Tailored Candidate Insights (Clearly flagged as inference)
    inferred_technical_focus: list[str] = Field(
        default_factory=list,
        description="Model interpretation of primary tech stack and engineering domains.",
    )
    candidate_strengths: list[str] = Field(
        default_factory=list,
        description="Direct overlaps between candidate profile and role needs.",
    )
    gap_analysis: list[str] = Field(
        default_factory=list,
        description="Missing skills, experience stretch points, or unverified requirements.",
    )
    transferable_skills: list[str] = Field(
        default_factory=list,
        description="Candidate competencies that bridge identified requirement gaps.",
    )
    ambiguity_flags: list[str] = Field(
        default_factory=list,
        description="Ambiguous requirements (e.g. unstated experience, vague remote policy).",
    )
    interview_talking_points: list[str] = Field(
        default_factory=list,
        description="Tailored points connecting AVASOFT internship to this role.",
    )

    # 3. Metadata & Confidence
    confidence_score: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Model confidence in the accuracy of extraction and alignment analysis.",
    )
    is_company_stated_fact_verified: bool = Field(
        default=True,
        description="Flag indicating ground truth sections contain no synthetic extrapolations.",
    )


class LLMEnrichmentRecord(BaseModel):
    """Full persisted enrichment record containing provenance, hashes, and structured result."""

    model_config = ConfigDict(use_enum_values=True)

    canonical_id: str
    profile_id: str = "default"
    model_name: str
    model_version: str
    prompt_version: str
    content_hash: str
    enrichment: JobEnrichmentResult
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
