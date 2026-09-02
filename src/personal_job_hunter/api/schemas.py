"""Pydantic API request and response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from personal_job_hunter.domain.models import ApplicationStatus, MatchRecommendation


class JobMatchScoreResponse(BaseModel):
    """API schema for job match score."""

    model_config = ConfigDict(from_attributes=True)

    recommendation: MatchRecommendation
    overall_score: float
    deterministic_score: float | None = None
    semantic_score: float | None = None
    semantic_similarity: float | None = None
    role_score: float
    technical_score: float
    experience_score: float
    location_score: float
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    score_reasons: list[str] = Field(default_factory=list)


class JobListItemResponse(BaseModel):
    """API schema for job listings in dashboard cards / table."""

    model_config = ConfigDict(from_attributes=True)

    canonical_id: str
    title: str
    company: str
    location: str
    work_mode: str
    is_remote: bool
    posted_date: str | None = None
    application_urls: list[str] = Field(default_factory=list)
    match_score: JobMatchScoreResponse | None = None
    application_status: str = "PENDING_HUMAN_REVIEW"


class JobDetailResponse(BaseModel):
    """Full detail API schema for single canonical job inspection."""

    model_config = ConfigDict(from_attributes=True)

    canonical_id: str
    title: str
    company: str
    location: str
    secondary_locations: list[str] = Field(default_factory=list)
    work_mode: str
    is_remote: bool
    employment_type: str | None = None
    department: str | None = None
    posted_date: str | None = None
    description: str
    inferred_skills: list[str] = Field(default_factory=list)
    application_urls: list[str] = Field(default_factory=list)
    match_score: JobMatchScoreResponse | None = None
    enrichment: dict[str, Any] | None = None
    application_status: str = "PENDING_HUMAN_REVIEW"
    application_notes: str | None = None
    application_events: list[dict[str, Any]] = Field(default_factory=list)


class JobReviewItemResponse(BaseModel):
    """API schema for jobs awaiting human decision in review inbox."""

    canonical_id: str
    title: str
    company: str
    location: str
    work_mode: str
    is_remote: bool
    application_urls: list[str] = Field(default_factory=list)
    match_score: JobMatchScoreResponse | None = None
    enrichment: dict[str, Any] | None = None
    status: str = "PENDING_HUMAN_REVIEW"


class ApplicationActionRequest(BaseModel):
    """Payload for human-in-the-loop application status actions."""

    notes: str | None = None
    reason: str | None = None
    interview_date: datetime | None = None
    applied_at: datetime | None = None


class ApplicationResponse(BaseModel):
    """API schema for application tracking entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_id: str
    status: ApplicationStatus
    applied_at: datetime | None = None
    interview_date: datetime | None = None
    human_feedback: str | None = None
    notes: str | None = None
    events_log: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StatsResponse(BaseModel):
    """API schema for high-level dashboard metrics."""

    total_canonical_jobs: int
    recommendations_breakdown: dict[str, int]
    applications_breakdown: dict[str, int]
    top_matched_skills: list[tuple[str, int]] = Field(default_factory=list)


class PipelineTriggerResponse(BaseModel):
    """API response for unified pipeline ingestion trigger."""

    status: str
    message: str
    duration_seconds: float
    canonical_jobs_count: int
    apply_targets_count: int
    stretch_opps_count: int
    enriched_count: int
    errors: list[str] = Field(default_factory=list)
