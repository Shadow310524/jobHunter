"""Unified Domain Models for Job Postings.

Preserves clear separation between:
1. Provenance / Identifiers (source, job_id, urls)
2. Company-Provided Data (title, company, locations, raw dates, description)
3. Inferred Data (inferred skills, inferred experience level)
4. Source-Specific Metadata (unstructured payload dictionary)
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkMode(StrEnum):
    """Normalized work mode."""

    REMOTE = "Remote"
    HYBRID = "Hybrid"
    ONSITE = "On-site"
    UNKNOWN = "Unknown"


class JobSource(StrEnum):
    """Supported job listing sources."""

    GREENHOUSE = "greenhouse"
    ASHBY = "ashby"
    LEVER = "lever"


class UnifiedJobPost(BaseModel):
    """Unified internal representation of a job posting across all collectors."""

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        extra="ignore",
    )

    # --- 1. Provenance & Identification ---
    source: JobSource
    job_id: str = Field(..., description="Unique source-scoped job ID (e.g., gh_company_123)")
    job_url: str = Field(..., description="Public job listing URL")
    official_application_url: str = Field(..., description="Direct official application URL")

    # --- 2. Company-Provided Fields (Ground Truth) ---
    title: str = Field(..., description="Official job title provided by employer")
    company: str = Field(..., description="Employer company name")
    location: str = Field(..., description="Primary location string")
    secondary_locations: list[str] = Field(
        default_factory=list, description="Additional locations if specified by company"
    )
    work_mode: WorkMode = Field(
        default=WorkMode.UNKNOWN, description="Company-specified or normalized work mode"
    )
    is_remote: bool = Field(default=False, description="Flag indicating if the position is remote")
    employment_type: str | None = Field(
        default=None, description="Company-provided employment type (e.g., FullTime, Contract)"
    )
    department: str | None = Field(
        default=None, description="Company-provided department or team name"
    )
    posted_date: str | None = Field(
        default=None, description="ISO 8601 formatted publication / update timestamp"
    )
    description: str = Field(..., description="Clean plaintext or markdown job description")
    salary: dict[str, Any] | str | None = Field(
        default=None, description="Company-provided compensation data if published"
    )
    raw_experience_text: str | None = Field(
        default=None,
        description="Explicit experience snippet directly stated by company, if available",
    )

    # --- 3. Inferred Fields (Derived by Local Heuristics / Matcher) ---
    inferred_experience_level: str | None = Field(
        default=None,
        description="Heuristically inferred seniority level (e.g., Fresher / 0-2 years)",
    )
    inferred_skills: list[str] = Field(
        default_factory=list,
        description="Deterministically extracted technical skills from title/description",
    )

    # --- 4. Extensibility & Source-Specific Metadata ---
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw or source-specific attributes preserved without polluting main fields",
    )

    @field_validator("title", "company", "location", "description")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Ensure core string fields are stripped of extraneous whitespace."""
        return v.strip() if isinstance(v, str) else v

    @field_validator("work_mode", mode="before")
    @classmethod
    def normalize_work_mode(cls, v: Any) -> WorkMode:
        """Normalize various work mode string representations."""
        if isinstance(v, WorkMode):
            return v
        if not v or not isinstance(v, str):
            return WorkMode.UNKNOWN

        lower = v.lower()
        if "remote" in lower or "home based" in lower:
            return WorkMode.REMOTE
        if "hybrid" in lower:
            return WorkMode.HYBRID
        if "onsite" in lower or "on-site" in lower or "office" in lower or "inoffice" in lower:
            return WorkMode.ONSITE
        return WorkMode.UNKNOWN
