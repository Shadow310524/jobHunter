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


class SourceProvenance(BaseModel):
    """Provenance record tracking which source provided what data."""

    model_config = ConfigDict(use_enum_values=True)

    source: JobSource
    source_job_id: str
    job_url: str
    official_application_url: str
    posted_date: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalJobPost(BaseModel):
    """Canonical unified job posting with full source provenance and duplicate tracking."""

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        extra="ignore",
    )

    canonical_id: str = Field(..., description="Deterministic canonical identifier")
    title: str = Field(..., description="Primary canonical job title")
    company: str = Field(..., description="Normalized company name")
    location: str = Field(..., description="Primary location")
    secondary_locations: list[str] = Field(default_factory=list)
    work_mode: WorkMode = Field(default=WorkMode.UNKNOWN)
    is_remote: bool = Field(default=False)
    employment_type: str | None = None
    department: str | None = None
    posted_date: str | None = None
    description: str = Field(..., description="Primary comprehensive job description")
    salary: dict[str, Any] | str | None = None
    raw_experience_text: str | None = None
    inferred_experience_level: str | None = None
    inferred_skills: list[str] = Field(default_factory=list)

    # --- Provenance Information ---
    sources: list[JobSource] = Field(
        default_factory=list, description="All sources contributing to this canonical job"
    )
    source_records: list[SourceProvenance] = Field(
        default_factory=list, description="Detailed records from each contributing source"
    )
    application_urls: list[str] = Field(
        default_factory=list, description="All unique application URLs found for this job"
    )

    # --- Candidate Match Flag ---
    duplicate_candidate_group: str | None = Field(
        default=None,
        description="Candidate group key if matching company/title/location with other jobs",
    )


class DeduplicationResult(BaseModel):
    """Summary and payload of a deterministic deduplication execution."""

    total_input_records: int
    unique_canonical_jobs: int
    confirmed_duplicates_merged: int
    potential_duplicate_groups_count: int
    potential_duplicate_jobs_count: int
    canonical_jobs: list[CanonicalJobPost]
    potential_duplicate_groups: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map of candidate group key to list of canonical_ids",
    )


class MatchRecommendation(StrEnum):
    """Classification recommendation for an application."""

    APPLY = "APPLY"  # 🟢 High fit, eligible
    STRETCH = "STRETCH"  # 🟡 Good technical fit, requires 1-2 yrs experience or slight stretch
    SKIP = "SKIP"  # 🔴 Mismatched skills, disqualified location/role, or 5+ yrs requirement


class CandidateProfile(BaseModel):
    """Candidate profile model representing real background and goals."""

    model_config = ConfigDict(use_enum_values=True)

    name: str = "Harish Renganathan"
    degree: str = "B.Tech in Artificial Intelligence & Machine Learning"
    graduation_year: int = 2026
    cgpa: float = 8.2
    current_role: str = "AI Platform Engineer Intern"
    company_internship: str = "AVASOFT"
    internship_duration: str = "Dec 2025 – Apr 2026"

    # Skills categorized by proficiency/priority
    core_skills: list[str] = Field(
        default_factory=lambda: [
            "Python",
            "FastAPI",
            "REST APIs",
            "PostgreSQL",
            "pgvector",
            "RAG",
            "Embeddings",
            "LangChain",
            "LangGraph",
            "FastMCP",
            "MCP",
            "AI Agents",
            "Multi-Agent Workflows",
            "HITL",
            "AWS",
            "AWS Bedrock",
            "AWS S3",
            "Docker",
            "Git",
            "GenAI",
            "LLM",
            "Machine Learning",
        ]
    )
    secondary_skills: list[str] = Field(
        default_factory=lambda: [
            "Kubernetes",
            "Java",
            "Spring Boot",
            "MySQL",
            "Redis",
            "Linux",
            "SQL",
            "PyTorch",
            "Deep Learning",
        ]
    )

    # Preferred target roles
    target_roles: list[str] = Field(
        default_factory=lambda: [
            "AI Engineer",
            "GenAI Engineer",
            "Generative AI Engineer",
            "AI/ML Engineer",
            "LLM Engineer",
            "Agentic AI Engineer",
            "AI Platform Engineer",
            "Applied AI Engineer",
            "AI Backend Engineer",
            "Python AI Engineer",
            "Python Backend Developer",
            "Backend Engineer",
            "Software Engineer",
            "Python Developer",
            "AI Software Engineer",
            "ML Platform Engineer",
            "Machine Learning Platform Engineer",
        ]
    )

    # Preferred locations in priority order
    primary_locations: list[str] = Field(
        default_factory=lambda: [
            "Bangalore",
            "Bengaluru",
            "Remote - India",
            "Remote, India",
            "India - Remote",
        ]
    )
    secondary_locations: list[str] = Field(
        default_factory=lambda: [
            "Hyderabad",
            "Pune",
            "Mumbai",
            "Delhi",
            "Gurgaon",
            "Noida",
            "Chennai",
            "Home based - APAC",
            "Remote, Global",
            "Worldwide",
        ]
    )

    experience_years_max: float = 2.0


class MatchWeights(BaseModel):
    """Configurable scoring weights for deterministic matching."""

    role_weight: float = 0.35
    technical_weight: float = 0.30
    experience_weight: float = 0.20
    location_weight: float = 0.15

    # Hybrid weights for combining deterministic and semantic scores
    deterministic_weight: float = 0.70
    semantic_weight: float = 0.30

    apply_threshold: float = 80.0
    stretch_threshold: float = 55.0


class MatchBreakdown(BaseModel):
    """Component scores and explanation for a match."""

    technical_score: float = 0.0
    role_score: float = 0.0
    experience_score: float = 0.0
    location_score: float = 0.0
    overall_score: float = 0.0

    # Semantic additions (Phase 7)
    deterministic_score: float | None = None
    semantic_score: float | None = None
    semantic_similarity: float | None = None
    final_score: float | None = None

    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    matched_role_keywords: list[str] = Field(default_factory=list)

    experience_eligible: bool = True
    location_eligible: bool = True

    score_reasons: list[str] = Field(default_factory=list)


class JobMatchResult(BaseModel):
    """Complete evaluation of a CanonicalJobPost against a CandidateProfile."""

    model_config = ConfigDict(use_enum_values=True)

    canonical_id: str
    job_title: str
    company: str
    location: str
    recommendation: MatchRecommendation
    overall_score: float
    breakdown: MatchBreakdown
    application_urls: list[str] = Field(default_factory=list)
