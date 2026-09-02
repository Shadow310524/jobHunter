"""SQLAlchemy 2.0 ORM database models for PostgreSQL & pgvector persistence."""

from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class CandidateProfileModel(Base):
    """Persisted candidate profile."""

    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    degree: Mapped[str] = mapped_column(String(255), nullable=False)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    cgpa: Mapped[float] = mapped_column(Float, nullable=False)
    current_role: Mapped[str] = mapped_column(String(255), nullable=False)
    company_internship: Mapped[str] = mapped_column(String(255), nullable=False)
    internship_duration: Mapped[str] = mapped_column(String(255), nullable=False)

    core_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    secondary_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    primary_locations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    secondary_locations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    match_scores: Mapped[list["JobMatchScoreModel"]] = relationship(
        "JobMatchScoreModel", back_populates="profile", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list["ProfileEmbeddingModel"]] = relationship(
        "ProfileEmbeddingModel", back_populates="profile", cascade="all, delete-orphan"
    )
    enrichments: Mapped[list["JobEnrichmentModel"]] = relationship(
        "JobEnrichmentModel", back_populates="profile", cascade="all, delete-orphan"
    )


class CanonicalJobModel(Base):
    """Canonical unified job posting entity."""

    __tablename__ = "canonical_jobs"

    canonical_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    secondary_locations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    work_mode: Mapped[str] = mapped_column(String(32), default="Unknown", index=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    employment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posted_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    salary: Mapped[dict[str, Any] | str | None] = mapped_column(JSON, nullable=True)
    raw_experience_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    inferred_experience_level: Mapped[str | None] = mapped_column(String(128), nullable=True)
    inferred_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    application_urls: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    duplicate_candidate_group: Mapped[str | None] = mapped_column(
        String(512), nullable=True, index=True
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    source_records: Mapped[list["SourceProvenanceModel"]] = relationship(
        "SourceProvenanceModel", back_populates="canonical_job", cascade="all, delete-orphan"
    )
    match_scores: Mapped[list["JobMatchScoreModel"]] = relationship(
        "JobMatchScoreModel", back_populates="canonical_job", cascade="all, delete-orphan"
    )
    application: Mapped["ApplicationModel | None"] = relationship(
        "ApplicationModel",
        back_populates="canonical_job",
        uselist=False,
        cascade="all, delete-orphan",
    )
    embeddings: Mapped[list["JobEmbeddingModel"]] = relationship(
        "JobEmbeddingModel", back_populates="canonical_job", cascade="all, delete-orphan"
    )
    enrichments: Mapped[list["JobEnrichmentModel"]] = relationship(
        "JobEnrichmentModel", back_populates="canonical_job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_canonical_jobs_company_title", "company", "title"),
        Index("ix_canonical_jobs_location_work_mode", "location", "work_mode"),
    )


class SourceProvenanceModel(Base):
    """Source provenance tracking contributing job sources."""

    __tablename__ = "source_provenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("canonical_jobs.canonical_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_job_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    job_url: Mapped[str] = mapped_column(Text, nullable=False)
    official_application_url: Mapped[str] = mapped_column(Text, nullable=False)
    posted_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    canonical_job: Mapped[CanonicalJobModel] = relationship(
        "CanonicalJobModel", back_populates="source_records"
    )

    __table_args__ = (
        UniqueConstraint(
            "canonical_id", "source", "source_job_id", name="uq_canonical_source_job_id"
        ),
        Index("ix_source_provenance_lookup", "source", "source_job_id"),
    )


class JobMatchScoreModel(Base):
    """Persisted deterministic + semantic match evaluation for a canonical job."""

    __tablename__ = "job_match_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("canonical_jobs.canonical_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        default="default",
        nullable=False,
        index=True,
    )
    recommendation: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    role_score: Mapped[float] = mapped_column(Float, nullable=False)
    technical_score: Mapped[float] = mapped_column(Float, nullable=False)
    experience_score: Mapped[float] = mapped_column(Float, nullable=False)
    location_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Hybrid Semantic Additions
    deterministic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    semantic_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)

    matched_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    matched_role_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    experience_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    location_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score_reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    canonical_job: Mapped[CanonicalJobModel] = relationship(
        "CanonicalJobModel", back_populates="match_scores"
    )
    profile: Mapped[CandidateProfileModel] = relationship(
        "CandidateProfileModel", back_populates="match_scores"
    )

    __table_args__ = (
        UniqueConstraint("canonical_id", "profile_id", name="uq_canonical_job_match_profile"),
        Index("ix_job_match_scores_recommendation_score", "recommendation", "overall_score"),
    )


class JobEmbeddingModel(Base):
    """Persisted vector embeddings for canonical jobs with model versioning & content hash."""

    __tablename__ = "job_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("canonical_jobs.canonical_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    canonical_job: Mapped[CanonicalJobModel] = relationship(
        "CanonicalJobModel", back_populates="embeddings"
    )

    __table_args__ = (
        UniqueConstraint(
            "canonical_id",
            "model_name",
            "model_version",
            name="uq_job_embeddings_canonical_model_version",
        ),
        Index("ix_job_embeddings_lookup", "canonical_id", "model_name", "model_version"),
    )


class ProfileEmbeddingModel(Base):
    """Persisted vector embeddings for candidate profiles with model versioning & content hash."""

    __tablename__ = "profile_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    profile: Mapped[CandidateProfileModel] = relationship(
        "CandidateProfileModel", back_populates="embeddings"
    )

    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "model_name",
            "model_version",
            name="uq_profile_embeddings_model_version",
        ),
    )


class JobEnrichmentModel(Base):
    """Persisted LLM enrichment results with prompt & model versioning and content hash."""

    __tablename__ = "job_enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("canonical_jobs.canonical_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        default="default",
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    enrichment_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    canonical_job: Mapped[CanonicalJobModel] = relationship(
        "CanonicalJobModel", back_populates="enrichments"
    )
    profile: Mapped[CandidateProfileModel] = relationship(
        "CandidateProfileModel", back_populates="enrichments"
    )

    __table_args__ = (
        UniqueConstraint(
            "canonical_id",
            "profile_id",
            "model_name",
            "prompt_version",
            name="uq_job_enrichments_lookup",
        ),
        Index(
            "ix_job_enrichments_lookup",
            "canonical_id",
            "profile_id",
            "model_name",
            "prompt_version",
        ),
    )


class ApplicationModel(Base):
    """Application tracking record for human-in-the-loop lifecycle."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("canonical_jobs.canonical_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), default="NOT_APPLIED", index=True, nullable=False
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    canonical_job: Mapped[CanonicalJobModel] = relationship(
        "CanonicalJobModel", back_populates="application"
    )
