"""Repository layer for database operations, queries, and idempotent upserts."""

from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from personal_job_hunter.db.models import (
    CandidateProfileModel,
    CanonicalJobModel,
    JobMatchScoreModel,
    SourceProvenanceModel,
)
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
    SourceProvenance,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ProfileRepository:
    """Data access operations for candidate profiles."""

    @staticmethod
    def save_profile(
        session: Session, profile: CandidateProfile, profile_id: str = "default"
    ) -> CandidateProfileModel:
        """Idempotently insert or update candidate profile."""
        existing = session.get(CandidateProfileModel, profile_id)
        if existing:
            existing.name = profile.name
            existing.degree = profile.degree
            existing.graduation_year = profile.graduation_year
            existing.cgpa = profile.cgpa
            existing.current_role = profile.current_role
            existing.company_internship = profile.company_internship
            existing.internship_duration = profile.internship_duration
            existing.core_skills = list(profile.core_skills)
            existing.secondary_skills = list(profile.secondary_skills)
            existing.target_roles = list(profile.target_roles)
            existing.primary_locations = list(profile.primary_locations)
            existing.secondary_locations = list(profile.secondary_locations)
            existing.updated_at = _utc_now()
            return existing

        new_model = CandidateProfileModel(
            id=profile_id,
            name=profile.name,
            degree=profile.degree,
            graduation_year=profile.graduation_year,
            cgpa=profile.cgpa,
            current_role=profile.current_role,
            company_internship=profile.company_internship,
            internship_duration=profile.internship_duration,
            core_skills=list(profile.core_skills),
            secondary_skills=list(profile.secondary_skills),
            target_roles=list(profile.target_roles),
            primary_locations=list(profile.primary_locations),
            secondary_locations=list(profile.secondary_locations),
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(new_model)
        return new_model

    @staticmethod
    def get_profile(session: Session, profile_id: str = "default") -> CandidateProfileModel | None:
        """Fetch candidate profile by ID."""
        return session.get(CandidateProfileModel, profile_id)


class JobRepository:
    """Data access operations for canonical jobs, source provenance, and match scores."""

    @staticmethod
    def upsert_canonical_job(session: Session, job: CanonicalJobPost) -> CanonicalJobModel:
        """Idempotently insert or update a CanonicalJobPost and its SourceProvenance records."""
        existing = session.get(CanonicalJobModel, job.canonical_id)

        if existing:
            # Update mutable fields
            existing.title = job.title
            existing.company = job.company
            existing.location = job.location
            existing.secondary_locations = list(job.secondary_locations)
            existing.work_mode = (
                job.work_mode.value if hasattr(job.work_mode, "value") else str(job.work_mode)
            )
            existing.is_remote = job.is_remote
            existing.employment_type = job.employment_type
            existing.department = job.department
            existing.posted_date = job.posted_date
            if len(job.description) > len(existing.description):
                existing.description = job.description
            existing.salary = job.salary
            existing.raw_experience_text = job.raw_experience_text
            existing.inferred_experience_level = job.inferred_experience_level
            existing.inferred_skills = list(job.inferred_skills)
            existing.application_urls = list(job.application_urls)
            existing.duplicate_candidate_group = job.duplicate_candidate_group
            existing.last_seen_at = _utc_now()
            canonical_model = existing
        else:
            canonical_model = CanonicalJobModel(
                canonical_id=job.canonical_id,
                title=job.title,
                company=job.company,
                location=job.location,
                secondary_locations=list(job.secondary_locations),
                work_mode=(
                    job.work_mode.value if hasattr(job.work_mode, "value") else str(job.work_mode)
                ),
                is_remote=job.is_remote,
                employment_type=job.employment_type,
                department=job.department,
                posted_date=job.posted_date,
                description=job.description,
                salary=job.salary,
                raw_experience_text=job.raw_experience_text,
                inferred_experience_level=job.inferred_experience_level,
                inferred_skills=list(job.inferred_skills),
                application_urls=list(job.application_urls),
                duplicate_candidate_group=job.duplicate_candidate_group,
                first_seen_at=_utc_now(),
                last_seen_at=_utc_now(),
            )
            session.add(canonical_model)
            session.flush()

        # Idempotently sync provenance records
        JobRepository._sync_provenance(session, canonical_model.canonical_id, job.source_records)
        return canonical_model

    @staticmethod
    def _sync_provenance(
        session: Session, canonical_id: str, records: list[SourceProvenance]
    ) -> None:
        """Sync provenance records ensuring uniqueness per (canonical_id, source, source_job_id)."""
        stmt = select(SourceProvenanceModel).where(
            SourceProvenanceModel.canonical_id == canonical_id
        )
        existing_prov = {(p.source, p.source_job_id): p for p in session.scalars(stmt).all()}

        for rec in records:
            src_val = rec.source.value if hasattr(rec.source, "value") else str(rec.source)
            key = (src_val, rec.source_job_id)
            if key in existing_prov:
                # Update existing provenance entry
                existing = existing_prov[key]
                existing.job_url = rec.job_url
                existing.official_application_url = rec.official_application_url
                existing.posted_date = rec.posted_date
                existing.raw_metadata = rec.raw_metadata
            else:
                new_prov = SourceProvenanceModel(
                    canonical_id=canonical_id,
                    source=src_val,
                    source_job_id=rec.source_job_id,
                    job_url=rec.job_url,
                    official_application_url=rec.official_application_url,
                    posted_date=rec.posted_date,
                    raw_metadata=rec.raw_metadata,
                    collected_at=_utc_now(),
                )
                session.add(new_prov)

    @staticmethod
    def upsert_canonical_jobs_batch(session: Session, jobs: list[CanonicalJobPost]) -> int:
        """Batch upsert multiple canonical jobs."""
        for job in jobs:
            JobRepository.upsert_canonical_job(session, job)
        session.flush()
        return len(jobs)

    @staticmethod
    def save_match_score(
        session: Session, match_result: JobMatchResult, profile_id: str = "default"
    ) -> JobMatchScoreModel:
        """Idempotently save or update a job match score evaluation."""
        stmt = select(JobMatchScoreModel).where(
            JobMatchScoreModel.canonical_id == match_result.canonical_id,
            JobMatchScoreModel.profile_id == profile_id,
        )
        existing = session.scalars(stmt).first()
        rec_val = (
            match_result.recommendation.value
            if hasattr(match_result.recommendation, "value")
            else str(match_result.recommendation)
        )
        bd = match_result.breakdown

        if existing:
            existing.recommendation = rec_val
            existing.overall_score = match_result.overall_score
            existing.role_score = bd.role_score
            existing.technical_score = bd.technical_score
            existing.experience_score = bd.experience_score
            existing.location_score = bd.location_score
            existing.matched_skills = list(bd.matched_skills)
            existing.missing_skills = list(bd.missing_skills)
            existing.matched_role_keywords = list(bd.matched_role_keywords)
            existing.experience_eligible = bd.experience_eligible
            existing.location_eligible = bd.location_eligible
            existing.score_reasons = list(bd.score_reasons)
            existing.scored_at = _utc_now()
            return existing

        new_score = JobMatchScoreModel(
            canonical_id=match_result.canonical_id,
            profile_id=profile_id,
            recommendation=rec_val,
            overall_score=match_result.overall_score,
            role_score=bd.role_score,
            technical_score=bd.technical_score,
            experience_score=bd.experience_score,
            location_score=bd.location_score,
            matched_skills=list(bd.matched_skills),
            missing_skills=list(bd.missing_skills),
            matched_role_keywords=list(bd.matched_role_keywords),
            experience_eligible=bd.experience_eligible,
            location_eligible=bd.location_eligible,
            score_reasons=list(bd.score_reasons),
            scored_at=_utc_now(),
        )
        session.add(new_score)
        return new_score

    @staticmethod
    def save_match_scores_batch(
        session: Session, match_results: list[JobMatchResult], profile_id: str = "default"
    ) -> int:
        """Batch save multiple match scores."""
        for res in match_results:
            JobRepository.save_match_score(session, res, profile_id)
        session.flush()
        return len(match_results)

    @staticmethod
    def get_canonical_job(session: Session, canonical_id: str) -> CanonicalJobModel | None:
        """Fetch canonical job with eager loaded provenance."""
        stmt = (
            select(CanonicalJobModel)
            .options(
                joinedload(CanonicalJobModel.source_records),
                joinedload(CanonicalJobModel.match_scores),
            )
            .where(CanonicalJobModel.canonical_id == canonical_id)
        )
        return session.scalars(stmt).unique().first()

    @staticmethod
    def get_ranked_jobs(
        session: Session,
        recommendation: str | None = None,
        profile_id: str = "default",
        limit: int = 50,
    ) -> list[tuple[CanonicalJobModel, JobMatchScoreModel]]:
        """Query top-ranked canonical jobs joined with their match scores."""
        stmt = (
            select(CanonicalJobModel, JobMatchScoreModel)
            .join(
                JobMatchScoreModel,
                CanonicalJobModel.canonical_id == JobMatchScoreModel.canonical_id,
            )
            .where(JobMatchScoreModel.profile_id == profile_id)
        )
        if recommendation:
            stmt = stmt.where(JobMatchScoreModel.recommendation == recommendation.upper())

        stmt = stmt.order_by(desc(JobMatchScoreModel.overall_score)).limit(limit)
        results = session.execute(stmt).all()
        return [(row[0], row[1]) for row in results]

    @staticmethod
    def get_total_job_count(session: Session) -> int:
        """Return total canonical job count in database."""
        stmt = select(CanonicalJobModel.canonical_id)
        return len(session.scalars(stmt).all())
