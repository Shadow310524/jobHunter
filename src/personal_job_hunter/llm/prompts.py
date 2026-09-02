"""Versioned prompt templates for LLM job enrichment."""

from personal_job_hunter.domain.models import CandidateProfile, CanonicalJobPost

ENRICHMENT_PROMPT_VERSION = "v1.0"

SYSTEM_PROMPT = """You are an expert technical recruiter and AI engineering analyst.
Your task is to analyze a job posting against a candidate profile and return structured insights.

CRITICAL INSTRUCTIONS:
1. Ground Truth Fidelity: Strictly distinguish COMPANY-STATED FACTS from MODEL INFERENCE.
   - In `job_summary`, `key_responsibilities`, and `stated_qualifications`, ONLY include facts
     explicitly mentioned in the job description.
   - Do NOT invent requirements, company details, salary, or eligibility.
2. Inferences: In `candidate_strengths`, `gap_analysis`, and `transferable_skills`, evaluate the
   candidate's actual qualifications against the role.
3. No Decision Override: Do NOT make final hiring/application decisions.
4. Output Format: Return a valid JSON object strictly matching the requested schema.
"""


def build_enrichment_user_prompt(job: CanonicalJobPost, profile: CandidateProfile) -> str:
    """Build concise user prompt with job and candidate context."""
    core_skills_str = ", ".join(profile.core_skills)
    sec_skills_str = ", ".join(profile.secondary_skills)

    return f"""### CANDIDATE PROFILE
- Name: {profile.name} (2026 B.Tech in {profile.degree}, CGPA: {profile.cgpa})
- Experience: {profile.current_role} at {profile.company_internship} ({profile.internship_duration})
- Core Skills: {core_skills_str}
- Secondary Skills: {sec_skills_str}
- Target Roles: {", ".join(profile.target_roles[:8])}
- Preferred Locations: {", ".join(profile.primary_locations)}

### JOB POSTING
- Job Title: {job.title}
- Company: {job.company}
- Location: {job.location} (Remote: {job.is_remote}, Work Mode: {job.work_mode})
- Stated Skills: {", ".join(job.inferred_skills) if job.inferred_skills else "Not specified"}
- Full Description:
{job.description[:2500]}

Analyze the job posting and return JSON strictly matching the schema.
"""
