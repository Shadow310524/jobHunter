"""API router for aggregated metrics and dashboard stats."""

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_job_hunter.api.dependencies import get_db
from personal_job_hunter.api.schemas import StatsResponse
from personal_job_hunter.db.models import JobMatchScoreModel
from personal_job_hunter.db.repository import ApplicationRepository, JobRepository

router = APIRouter(prefix="/api/stats", tags=["Stats"])


@router.get("", response_model=StatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db)) -> StatsResponse:
    """Retrieve aggregated counts for dashboard overview."""
    total_jobs = JobRepository.get_total_job_count(db)

    # Match score counts
    score_stmt = select(JobMatchScoreModel.recommendation, JobMatchScoreModel.matched_skills)
    score_rows = db.execute(score_stmt).all()

    rec_counts: dict[str, int] = {"APPLY": 0, "STRETCH": 0, "SKIP": 0}
    skill_counter: Counter[str] = Counter()

    for rec, skills in score_rows:
        if rec in rec_counts:
            rec_counts[rec] += 1
        if skills and isinstance(skills, list):
            for s in skills:
                skill_counter[s] += 1

    # Application tracking stats
    app_stats = ApplicationRepository.get_application_stats(db)

    return StatsResponse(
        total_canonical_jobs=total_jobs,
        recommendations_breakdown=rec_counts,
        applications_breakdown=app_stats,
        top_matched_skills=skill_counter.most_common(10),
    )
