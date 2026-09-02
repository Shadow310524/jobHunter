"""Source normalizers for transforming collector outputs into UnifiedJobPost entities.

Explicitly maps each source's schema into the unified domain model without data loss.
"""

from typing import Any

from personal_job_hunter.domain.models import JobSource, UnifiedJobPost, WorkMode


def normalize_greenhouse_job(data: dict[str, Any]) -> UnifiedJobPost:
    """Normalize a Greenhouse collector output dictionary into a UnifiedJobPost."""
    # Department handling (Greenhouse outputs list of department names)
    departments_list = data.get("departments") or []
    department_str = ", ".join(departments_list) if departments_list else None

    # Inferred skills mapping
    inferred_skills = data.get("required_skills") or data.get("inferred_skills") or []

    # Preserve all raw metadata without losing source specifics
    metadata = {
        "departments": departments_list,
        "preferred_skills": data.get("preferred_skills", []),
    }

    return UnifiedJobPost(
        source=JobSource.GREENHOUSE,
        job_id=str(data["job_id"]),
        job_url=str(data["job_url"]),
        official_application_url=str(data.get("official_application_url") or data["job_url"]),
        title=str(data["title"]),
        company=str(data["company"]),
        location=str(data.get("location") or "Bengaluru, India"),
        secondary_locations=[],
        work_mode=data.get("work_mode") or WorkMode.UNKNOWN,
        is_remote="remote" in str(data.get("work_mode", "")).lower(),
        employment_type=data.get("employment_type"),
        department=department_str,
        posted_date=data.get("posted_date"),
        description=str(data.get("description") or ""),
        salary=data.get("salary"),
        raw_experience_text=data.get("raw_experience_text"),
        inferred_experience_level=data.get("experience") or data.get("inferred_experience_level"),
        inferred_skills=inferred_skills,
        metadata=metadata,
    )


def normalize_ashby_job(data: dict[str, Any]) -> UnifiedJobPost:
    """Normalize an Ashby collector output dictionary into a UnifiedJobPost."""
    metadata = {
        "secondary_locations": data.get("secondary_locations", []),
    }

    return UnifiedJobPost(
        source=JobSource.ASHBY,
        job_id=str(data["job_id"]),
        job_url=str(data["job_url"]),
        official_application_url=str(data.get("official_application_url") or data["job_url"]),
        title=str(data["title"]),
        company=str(data["company"]),
        location=str(data.get("location") or "Bengaluru"),
        secondary_locations=data.get("secondary_locations") or [],
        work_mode=data.get("work_mode") or WorkMode.UNKNOWN,
        is_remote=bool(data.get("is_remote")),
        employment_type=data.get("employment_type"),
        department=data.get("department"),
        posted_date=data.get("posted_date"),
        description=str(data.get("description") or ""),
        salary=data.get("salary"),
        raw_experience_text=data.get("raw_experience_text"),
        inferred_experience_level=data.get("inferred_experience_level"),
        inferred_skills=data.get("inferred_skills") or [],
        metadata=metadata,
    )


def normalize_lever_job(data: dict[str, Any]) -> UnifiedJobPost:
    """Normalize a Lever collector output dictionary into a UnifiedJobPost."""
    metadata = {
        "secondary_locations": data.get("secondary_locations", []),
    }

    return UnifiedJobPost(
        source=JobSource.LEVER,
        job_id=str(data["job_id"]),
        job_url=str(data["job_url"]),
        official_application_url=str(data.get("official_application_url") or data["job_url"]),
        title=str(data["title"]),
        company=str(data["company"]),
        location=str(data.get("location") or "Bengaluru"),
        secondary_locations=data.get("secondary_locations") or [],
        work_mode=data.get("work_mode") or WorkMode.UNKNOWN,
        is_remote=bool(data.get("is_remote")),
        employment_type=data.get("employment_type"),
        department=data.get("department"),
        posted_date=data.get("posted_date"),
        description=str(data.get("description") or ""),
        salary=data.get("salary"),
        raw_experience_text=data.get("raw_experience_text"),
        inferred_experience_level=data.get("inferred_experience_level"),
        inferred_skills=data.get("inferred_skills") or [],
        metadata=metadata,
    )


def normalize_job(data: dict[str, Any], source: str | JobSource) -> UnifiedJobPost:
    """Dispatch dictionary data to the appropriate source normalizer."""
    src_str = source.value if isinstance(source, JobSource) else str(source).lower()

    if src_str == JobSource.GREENHOUSE.value:
        return normalize_greenhouse_job(data)
    if src_str == JobSource.ASHBY.value:
        return normalize_ashby_job(data)
    if src_str == JobSource.LEVER.value:
        return normalize_lever_job(data)

    raise ValueError(f"Unsupported job source for normalization: {source}")
