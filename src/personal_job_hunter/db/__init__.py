"""Database package: SQLAlchemy 2.0 ORM models, session management, and repositories."""

from personal_job_hunter.db.models import (
    ApplicationModel,
    Base,
    CandidateProfileModel,
    CanonicalJobModel,
    JobEmbeddingModel,
    JobEnrichmentModel,
    JobMatchScoreModel,
    ProfileEmbeddingModel,
    SourceProvenanceModel,
)
from personal_job_hunter.db.repository import (
    EnrichmentRepository,
    JobRepository,
    ProfileRepository,
)
from personal_job_hunter.db.session import create_tables, get_db_engine, get_session

__all__ = [
    "ApplicationModel",
    "Base",
    "CandidateProfileModel",
    "CanonicalJobModel",
    "EnrichmentRepository",
    "JobEmbeddingModel",
    "JobEnrichmentModel",
    "JobMatchScoreModel",
    "JobRepository",
    "ProfileEmbeddingModel",
    "ProfileRepository",
    "SourceProvenanceModel",
    "create_tables",
    "get_db_engine",
    "get_session",
]
