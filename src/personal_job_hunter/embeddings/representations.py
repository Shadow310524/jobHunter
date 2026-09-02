"""Embedding representation builders and deterministic content hashing."""

import hashlib

from personal_job_hunter.domain.models import CandidateProfile, CanonicalJobPost


def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of text content for idempotency tracking."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def build_job_embedding_text(job: CanonicalJobPost) -> str:
    """Construct dense structured text representation for a canonical job post."""
    skills_text = ", ".join(job.inferred_skills) if job.inferred_skills else "General Software"
    desc_snippet = job.description[:1200].replace("\n", " ").strip()

    parts = [
        f"Role: {job.title}",
        f"Company: {job.company}",
        f"Location: {job.location}",
        f"Work Mode: {job.work_mode.value if hasattr(job.work_mode, 'value') else job.work_mode}",
        f"Key Skills: {skills_text}",
        f"Job Description: {desc_snippet}",
    ]
    return " | ".join(parts)


def build_candidate_embedding_text(profile: CandidateProfile) -> str:
    """Construct dense structured text representation for a candidate profile."""
    core_skills = ", ".join(profile.core_skills)
    sec_skills = ", ".join(profile.secondary_skills)
    roles = ", ".join(profile.target_roles)
    locs = ", ".join(profile.primary_locations)

    parts = [
        f"Target Roles: {roles}",
        (
            f"Education: {profile.degree} "
            f"(Graduation: {profile.graduation_year}, CGPA: {profile.cgpa})"
        ),
        (
            f"Experience: {profile.current_role} at {profile.company_internship} "
            f"({profile.internship_duration})"
        ),
        f"Core Technical Skills: {core_skills}",
        f"Secondary Technical Skills: {sec_skills}",
        f"Preferred Locations: {locs}",
    ]
    return " | ".join(parts)
