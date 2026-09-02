"""API router for job discovery, queries, and detailed inspections."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from personal_job_hunter.api.dependencies import get_db
from personal_job_hunter.api.schemas import (
    JobDetailResponse,
    JobListItemResponse,
    JobMatchScoreResponse,
    JobReviewItemResponse,
)
from personal_job_hunter.db.models import (
    ApplicationModel,
    CanonicalJobModel,
    JobEnrichmentModel,
    JobMatchScoreModel,
)
from personal_job_hunter.db.repository import ApplicationRepository, JobRepository
from personal_job_hunter.domain.models import ApplicationStatus

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get("", response_model=list[JobListItemResponse])
def list_jobs(
    recommendation: str | None = Query(None, description="Filter by APPLY, STRETCH, or SKIP"),
    work_mode: str | None = Query(None, description="Filter by Remote, On-site, Hybrid"),
    search: str | None = Query(None, description="Keyword search in title or company"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[JobListItemResponse]:
    """Retrieve paginated canonical jobs with match scores and tracking status."""
    stmt = (
        select(CanonicalJobModel, JobMatchScoreModel, ApplicationModel)
        .outerjoin(
            JobMatchScoreModel, CanonicalJobModel.canonical_id == JobMatchScoreModel.canonical_id
        )
        .outerjoin(
            ApplicationModel, CanonicalJobModel.canonical_id == ApplicationModel.canonical_id
        )
    )

    if recommendation:
        stmt = stmt.where(JobMatchScoreModel.recommendation == recommendation.upper())
    if work_mode:
        stmt = stmt.where(CanonicalJobModel.work_mode.ilike(f"%{work_mode}%"))
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            CanonicalJobModel.title.ilike(search_pattern)
            | CanonicalJobModel.company.ilike(search_pattern)
            | CanonicalJobModel.location.ilike(search_pattern)
        )

    stmt = stmt.order_by(desc(JobMatchScoreModel.overall_score)).offset(offset).limit(limit)
    rows = db.execute(stmt).all()

    results: list[JobListItemResponse] = []
    for job, score, app in rows:
        score_resp = JobMatchScoreResponse.model_validate(score) if score else None
        app_status = app.status if app else ApplicationStatus.PENDING_HUMAN_REVIEW.value
        results.append(
            JobListItemResponse(
                canonical_id=job.canonical_id,
                title=job.title,
                company=job.company,
                location=job.location,
                work_mode=job.work_mode,
                is_remote=job.is_remote,
                posted_date=job.posted_date,
                application_urls=job.application_urls or [],
                match_score=score_resp,
                application_status=app_status,
            )
        )
    return results


@router.get("/recommended", response_model=list[JobListItemResponse])
def get_recommended_jobs(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[JobListItemResponse]:
    """Retrieve highest priority target jobs (APPLY and top STRETCH)."""
    stmt = (
        select(CanonicalJobModel, JobMatchScoreModel, ApplicationModel)
        .join(JobMatchScoreModel, CanonicalJobModel.canonical_id == JobMatchScoreModel.canonical_id)
        .outerjoin(
            ApplicationModel, CanonicalJobModel.canonical_id == ApplicationModel.canonical_id
        )
        .where(JobMatchScoreModel.recommendation.in_(["APPLY", "STRETCH"]))
        .order_by(desc(JobMatchScoreModel.overall_score))
        .limit(limit)
    )
    rows = db.execute(stmt).all()

    results: list[JobListItemResponse] = []
    for job, score, app in rows:
        results.append(
            JobListItemResponse(
                canonical_id=job.canonical_id,
                title=job.title,
                company=job.company,
                location=job.location,
                work_mode=job.work_mode,
                is_remote=job.is_remote,
                posted_date=job.posted_date,
                application_urls=job.application_urls or [],
                match_score=JobMatchScoreResponse.model_validate(score),
                application_status=app.status
                if app
                else ApplicationStatus.PENDING_HUMAN_REVIEW.value,
            )
        )
    return results


@router.get("/review", response_model=list[JobReviewItemResponse])
def get_review_inbox(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[JobReviewItemResponse]:
    """Retrieve jobs awaiting human decision in review inbox."""
    inbox = ApplicationRepository.get_review_inbox(db, limit=limit)
    items: list[JobReviewItemResponse] = []
    for app, job, score, enr_model in inbox:
        items.append(
            JobReviewItemResponse(
                canonical_id=job.canonical_id,
                title=job.title,
                company=job.company,
                location=job.location,
                work_mode=job.work_mode,
                is_remote=job.is_remote,
                application_urls=job.application_urls or [],
                match_score=JobMatchScoreResponse.model_validate(score) if score else None,
                enrichment=enr_model.enrichment_data if enr_model else None,
                status=app.status,
            )
        )
    return items


@router.get("/{canonical_id}", response_model=JobDetailResponse)
def get_job_detail(
    canonical_id: str,
    db: Session = Depends(get_db),
) -> JobDetailResponse:
    """Retrieve full job specification, scoring breakdown, LLM insights, and application status."""
    job = JobRepository.get_canonical_job(db, canonical_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with canonical ID '{canonical_id}' not found.",
        )

    score_model = db.scalars(
        select(JobMatchScoreModel).where(JobMatchScoreModel.canonical_id == canonical_id)
    ).first()

    enrichment_model = db.scalars(
        select(JobEnrichmentModel).where(JobEnrichmentModel.canonical_id == canonical_id)
    ).first()

    app_model = ApplicationRepository.get_application(db, canonical_id)

    return JobDetailResponse(
        canonical_id=job.canonical_id,
        title=job.title,
        company=job.company,
        location=job.location,
        secondary_locations=job.secondary_locations or [],
        work_mode=job.work_mode,
        is_remote=job.is_remote,
        employment_type=job.employment_type,
        department=job.department,
        posted_date=job.posted_date,
        description=job.description,
        inferred_skills=job.inferred_skills or [],
        application_urls=job.application_urls or [],
        match_score=JobMatchScoreResponse.model_validate(score_model) if score_model else None,
        enrichment=enrichment_model.enrichment_data if enrichment_model else None,
        application_status=app_model.status
        if app_model
        else ApplicationStatus.PENDING_HUMAN_REVIEW.value,
        application_notes=app_model.notes if app_model else None,
        application_events=app_model.events_log if app_model else [],
    )


@router.get("/{canonical_id}/enrichment", response_model=dict[str, Any])
def get_job_enrichment(
    canonical_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve LLM enrichment result for a specific job."""
    enrichment_model = db.scalars(
        select(JobEnrichmentModel).where(JobEnrichmentModel.canonical_id == canonical_id)
    ).first()

    if not enrichment_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No LLM enrichment available for job '{canonical_id}'.",
        )
    return enrichment_model.enrichment_data
