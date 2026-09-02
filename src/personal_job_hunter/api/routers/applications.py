"""API router for human-in-the-loop application lifecycle tracking."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from personal_job_hunter.api.dependencies import get_db
from personal_job_hunter.api.schemas import ApplicationActionRequest, ApplicationResponse
from personal_job_hunter.db.repository import ApplicationRepository
from personal_job_hunter.tracking.manager import ApplicationTracker
from personal_job_hunter.tracking.state_machine import InvalidStateTransitionError

router = APIRouter(prefix="/api/applications", tags=["Applications"])


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    status_filter: str | None = Query(None, alias="status", description="Filter by status enum"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ApplicationResponse]:
    """List tracked applications with optional lifecycle status filter."""
    if status_filter:
        records = ApplicationRepository.get_applications_by_status(
            db, status_filter.upper(), limit=limit
        )
        return [ApplicationResponse.model_validate(app) for app, _, _ in records]

    # Return all recent applications
    inbox = ApplicationRepository.get_review_inbox(db, limit=limit)
    return [ApplicationResponse.model_validate(app) for app, _, _, _ in inbox]


@router.get("/{canonical_id}", response_model=ApplicationResponse)
def get_application(
    canonical_id: str,
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    """Retrieve single application tracking record and event audit trail."""
    app = ApplicationRepository.get_application(db, canonical_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application for canonical ID '{canonical_id}' not found.",
        )
    return ApplicationResponse.model_validate(app)


@router.post("/{canonical_id}/approve", response_model=ApplicationResponse)
def approve_job(
    canonical_id: str,
    payload: ApplicationActionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    """Human decision: Approve job for application (READY_TO_APPLY)."""
    try:
        notes = payload.notes if payload else None
        app = ApplicationTracker.approve_for_apply(db, canonical_id, notes=notes)
        db.commit()
        return ApplicationResponse.model_validate(app)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{canonical_id}/reject", response_model=ApplicationResponse)
def reject_job(
    canonical_id: str,
    payload: ApplicationActionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    """Human decision: Reject job (REJECTED_BY_HUMAN / Closed)."""
    try:
        reason = payload.reason or payload.notes if payload else None
        app = ApplicationTracker.reject_by_human(db, canonical_id, reason=reason)
        db.commit()
        return ApplicationResponse.model_validate(app)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{canonical_id}/mark-applied", response_model=ApplicationResponse)
def mark_applied(
    canonical_id: str,
    payload: ApplicationActionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    """Human action: Confirm that candidate manually submitted the application."""
    try:
        notes = payload.notes if payload else None
        applied_at = payload.applied_at if payload else None
        app = ApplicationTracker.mark_as_applied(
            db, canonical_id, notes=notes, applied_at=applied_at
        )
        db.commit()
        return ApplicationResponse.model_validate(app)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{canonical_id}/interview", response_model=ApplicationResponse)
def schedule_interview(
    canonical_id: str,
    payload: ApplicationActionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    """Record scheduled interview round (INTERVIEWING)."""
    try:
        notes = payload.notes if payload else None
        interview_date = payload.interview_date if payload else None
        app = ApplicationTracker.schedule_interview(
            db, canonical_id, interview_date=interview_date, notes=notes
        )
        db.commit()
        return ApplicationResponse.model_validate(app)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{canonical_id}/offer", response_model=ApplicationResponse)
def record_offer(
    canonical_id: str,
    payload: ApplicationActionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    """Record job offer received (OFFER)."""
    try:
        notes = payload.notes if payload else None
        app = ApplicationTracker.record_offer(db, canonical_id, notes=notes)
        db.commit()
        return ApplicationResponse.model_validate(app)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
