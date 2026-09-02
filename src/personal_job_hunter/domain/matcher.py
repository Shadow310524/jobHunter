"""Deterministic Candidate Profile Matcher & Scoring Engine.

100% deterministic evaluation of CanonicalJobPost entities against a CandidateProfile.
Provides modular scoring factors, granular reasoning, and classification (APPLY / STRETCH / SKIP).
"""

import re

from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
    MatchBreakdown,
    MatchRecommendation,
    MatchWeights,
    WorkMode,
)

# Canonical synonym dictionary for tech skills
SKILL_SYNONYMS: dict[str, list[str]] = {
    "python": ["python", "python3", "py"],
    "fastapi": ["fastapi", "fast api"],
    "rest apis": ["rest api", "rest apis", "restful", "restful api", "rest", "api development"],
    "postgresql": ["postgresql", "postgres", "psql", "pg"],
    "pgvector": ["pgvector", "pg-vector"],
    "rag": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    "embeddings": ["embeddings", "embedding models", "vector embeddings"],
    "langchain": ["langchain", "lang-chain"],
    "langgraph": ["langgraph", "lang-graph"],
    "fastmcp": ["fastmcp"],
    "mcp": ["mcp", "model context protocol"],
    "ai agents": [
        "ai agent",
        "ai agents",
        "agentic",
        "agentic ai",
        "agent workflows",
        "multi-agent",
        "multi agent",
    ],
    "hitl": ["hitl", "human in the loop", "human-in-the-loop"],
    "aws bedrock": ["aws bedrock", "bedrock", "amazon bedrock"],
    "aws s3": ["aws s3", "s3", "amazon s3"],
    "docker": ["docker", "containerization", "containers"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git", "github", "gitlab"],
    "java": ["java", "core java"],
    "spring boot": ["spring boot", "springboot", "spring-boot", "spring framework"],
    "mysql": ["mysql"],
    "redis": ["redis"],
    "linux": ["linux", "unix", "ubuntu"],
    "sql": ["sql"],
    "machine learning": ["machine learning", "ml", "ml models"],
    "deep learning": ["deep learning", "dl", "neural networks"],
    "llm": ["llm", "llms", "large language models", "large language model"],
    "genai": ["genai", "generative ai", "generative-ai"],
    "pytorch": ["pytorch", "torch"],
    "tensorflow": ["tensorflow", "tf"],
}

CANONICAL_SKILL_CASING: dict[str, str] = {
    "python": "Python",
    "fastapi": "FastAPI",
    "rest apis": "REST APIs",
    "postgresql": "PostgreSQL",
    "pgvector": "pgvector",
    "rag": "RAG",
    "embeddings": "Embeddings",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "fastmcp": "FastMCP",
    "mcp": "MCP",
    "ai agents": "AI Agents",
    "hitl": "HITL",
    "aws bedrock": "AWS Bedrock",
    "aws s3": "AWS S3",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "git": "Git",
    "java": "Java",
    "spring boot": "Spring Boot",
    "mysql": "MySQL",
    "redis": "Redis",
    "linux": "Linux",
    "sql": "SQL",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "llm": "LLM",
    "genai": "GenAI",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
}

# Negative / Disqualifying role keywords
EXCLUDED_ROLES = [
    "sales",
    "marketing",
    "bpo",
    "telecalling",
    "hr",
    "human resources",
    "recruiter",
    "talent acquisition",
    "account executive",
    "business development",
    "collections manager",
    "payroll",
]

# Non-matching tech skill indicators to detect skill gap
OTHER_TECH_SKILLS = [
    "c++",
    "c#",
    ".net",
    "ruby",
    "rails",
    "php",
    "scala",
    "rust",
    "golang",
    "go",
    "swift",
    "kotlin",
    "ios",
    "android",
    "react",
    "angular",
    "vue",
]


def normalize_skill_name(raw_name: str) -> str:
    """Map raw skill string to canonical skill name."""
    clean = raw_name.strip().lower()
    if clean in CANONICAL_SKILL_CASING:
        return CANONICAL_SKILL_CASING[clean]
    for canonical, syns in SKILL_SYNONYMS.items():
        if clean == canonical or clean in syns:
            return CANONICAL_SKILL_CASING.get(canonical, canonical.title())
    return raw_name.strip().title()


def extract_skills_from_text(text: str) -> set[str]:
    """Deterministically find all recognized skills in a text string."""
    found: set[str] = set()
    lower_text = f" {text.lower()} "

    for canonical, syns in SKILL_SYNONYMS.items():
        for syn in syns:
            pattern = rf"\b{re.escape(syn)}\b"
            if re.search(pattern, lower_text):
                found.add(normalize_skill_name(canonical))
                break

    for other_skill in OTHER_TECH_SKILLS:
        pattern = rf"\b{re.escape(other_skill)}\b"
        if re.search(pattern, lower_text):
            found.add(normalize_skill_name(other_skill))

    return found


def evaluate_technical_skills(
    job: CanonicalJobPost, profile: CandidateProfile
) -> tuple[float, list[str], list[str], list[str]]:
    """Evaluate technical skill match between candidate profile and job posting.

    Returns:
        (technical_score, matched_skills, missing_skills, reasons)
    """
    reasons: list[str] = []

    # 1. Gather all candidate skills normalized
    core_cand = {normalize_skill_name(s) for s in profile.core_skills}
    sec_cand = {normalize_skill_name(s) for s in profile.secondary_skills}
    all_cand = core_cand | sec_cand

    # 2. Gather job skills from inferred_skills and description text normalized
    raw_job_skills = set(job.inferred_skills) | extract_skills_from_text(
        f"{job.title} {job.description}"
    )
    job_skills = {normalize_skill_name(s) for s in raw_job_skills}

    if not job_skills:
        reasons.append(
            "Job description has no specific technical skill requirements; "
            "default baseline score applied."
        )
        return 65.0, [], [], reasons

    matched_skills = sorted(job_skills & all_cand)
    missing_skills = sorted(job_skills - all_cand)

    total_weight = sum(1.5 if s in core_cand else 1.0 for s in (job_skills & all_cand))
    missing_weight = sum(1.0 for _ in missing_skills)

    raw_ratio = (
        total_weight / (total_weight + missing_weight)
        if (total_weight + missing_weight) > 0
        else 0.5
    )
    technical_score = round(min(100.0, raw_ratio * 100.0), 1)

    # Core competency boosters
    if "Python" in matched_skills or "PYTHON" in matched_skills:
        technical_score = min(100.0, technical_score + 10.0)
    if any(
        s in matched_skills
        for s in [
            "FastAPI",
            "FASTAPI",
            "PostgreSQL",
            "POSTGRESQL",
            "RAG",
            "LLM",
            "AI Agents",
            "Docker",
        ]
    ):
        technical_score = min(100.0, technical_score + 5.0)

    matched_sample = ", ".join(matched_skills[:5])
    reasons.append(
        f"Matched {len(matched_skills)} candidate skills "
        f"({matched_sample}{'...' if len(matched_skills) > 5 else ''})."
    )
    if missing_skills:
        missing_sample = ", ".join(missing_skills[:4])
        reasons.append(
            f"Missing {len(missing_skills)} job skills "
            f"({missing_sample}{'...' if len(missing_skills) > 4 else ''})."
        )

    return technical_score, matched_skills, missing_skills, reasons


def evaluate_role_relevance(
    job: CanonicalJobPost, profile: CandidateProfile
) -> tuple[float, list[str], list[str]]:
    """Evaluate role title relevance against target engineering roles.

    Returns:
        (role_score, matched_role_keywords, reasons)
    """
    reasons: list[str] = []
    matched_keywords: list[str] = []
    title_lower = f" {job.title.lower()} "

    # 1. Check for disqualified non-technical roles
    for ex in EXCLUDED_ROLES:
        if re.search(rf"\b{re.escape(ex)}\b", title_lower):
            if "engineer" not in title_lower and "developer" not in title_lower:
                reasons.append(f"Disqualified: Title contains excluded role keyword '{ex}'.")
                return 0.0, [], reasons

    # 2. Check for exact or high-priority AI / GenAI / LLM / Platform roles
    ai_keywords = [
        "ai engineer",
        "genai",
        "generative ai",
        "llm",
        "agentic",
        "ai platform",
        "applied ai",
        "ai backend",
        "ml platform",
        "machine learning engineer",
        "ai software engineer",
    ]
    for kw in ai_keywords:
        if kw in title_lower:
            matched_keywords.append(kw)

    backend_keywords = [
        "python",
        "backend engineer",
        "backend developer",
        "platform engineer",
        "software engineer",
        "sde",
        "software developer",
    ]
    for kw in backend_keywords:
        if re.search(rf"\b{re.escape(kw)}\b", title_lower):
            matched_keywords.append(kw)

    if any(
        k in matched_keywords
        for k in ["ai platform", "agentic", "genai", "llm", "ai engineer", "applied ai"]
    ):
        role_score = 100.0
        reasons.append(f"Top tier target AI role match: '{job.title}'.")
    elif any(k in matched_keywords for k in ["python", "backend engineer", "backend developer"]):
        role_score = 90.0
        reasons.append(f"Strong target backend/Python role match: '{job.title}'.")
    elif any(k in matched_keywords for k in ["software engineer", "sde", "software developer"]):
        role_score = 80.0
        reasons.append(f"General target software engineering role match: '{job.title}'.")
    else:
        role_score = 45.0
        reasons.append(f"Peripheral technical role: '{job.title}'.")

    # Seniority level impact on role score
    if any(
        s in title_lower
        for s in [
            "intern",
            "graduate",
            "fresher",
            "associate",
            "junior",
            "sde 1",
            "sde i",
            "engineer i",
        ]
    ):
        role_score = min(100.0, role_score + 5.0)
        reasons.append("Title explicitly indicates entry-level / early career friendly.")
    elif any(
        s in title_lower for s in ["lead", "staff", "principal", "director", "vp", "architect"]
    ):
        role_score = max(20.0, role_score - 20.0)
        reasons.append("Title indicates leadership / high seniority (Lead/Staff/Principal).")

    return role_score, matched_keywords, reasons


def evaluate_experience_compatibility(
    job: CanonicalJobPost, profile: CandidateProfile
) -> tuple[float, bool, list[str]]:
    """Evaluate experience level compatibility for 2026 graduate / 0-2 years range.

    Returns:
        (experience_score, experience_eligible, reasons)
    """
    reasons: list[str] = []
    exp_str = job.raw_experience_text or ""
    inf_exp_str = job.inferred_experience_level or ""
    desc_snippet = job.description[:600]
    text_to_check = f"{job.title} {exp_str} {inf_exp_str} {desc_snippet}".lower()

    # 1. Stated or inferred fresher / 0-2 years
    if any(
        w in text_to_check
        for w in [
            "fresher",
            "graduate",
            "intern",
            "0-1",
            "0-2",
            "0 to 2",
            "0–2",
            "1-2",
            "entry level",
            "associate",
        ]
    ):
        reasons.append(
            "Experience requirement matches 0-2 years / 2026 graduate profile (100% eligible)."
        )
        return 100.0, True, reasons

    # 2. 0-3 years / moderate
    if any(
        w in text_to_check for w in ["0-3", "0 to 3", "0–3", "1-3", "2-3", "2+ years", "1+ years"]
    ):
        reasons.append("Experience requirement (0-3 years) is within target / stretch range.")
        return 80.0, True, reasons

    # 3. Senior / 3+ years
    if any(
        w in text_to_check
        for w in ["senior", "sr.", "3-5", "3+", "4+", "5+ years", "lead", "staff"]
    ):
        reasons.append("Experience requirement (3+ years / Senior) is a stretch for early career.")
        return 40.0, False, reasons

    # 4. Unspecified experience
    reasons.append("No explicit experience years required; assumed open to early career engineers.")
    return 75.0, True, reasons


def evaluate_location_compatibility(
    job: CanonicalJobPost, profile: CandidateProfile
) -> tuple[float, bool, list[str]]:
    """Evaluate location compatibility prioritizing Bangalore and Remote India.

    Returns:
        (location_score, location_eligible, reasons)
    """
    reasons: list[str] = []
    all_locations = [job.location] + job.secondary_locations
    loc_str = " ".join(all_locations).lower()

    is_remote = job.is_remote or job.work_mode == WorkMode.REMOTE or "remote" in loc_str

    # 1. Bangalore / Bengaluru or Remote India
    if any(b in loc_str for b in ["bangalore", "bengaluru"]) or (is_remote and "india" in loc_str):
        reasons.append(f"Top priority location match: {job.location} (Bangalore / Remote India).")
        return 100.0, True, reasons

    # 2. Indian Tech Hubs (Hyderabad, Pune, Mumbai, Delhi, Gurgaon, Noida, Chennai)
    indian_hubs = [
        "hyderabad",
        "pune",
        "mumbai",
        "delhi",
        "gurgaon",
        "noida",
        "chennai",
        "india",
    ]
    if any(h in loc_str for h in indian_hubs):
        reasons.append(f"Secondary Indian tech hub match: {job.location}.")
        return 80.0, True, reasons

    # 3. Global Remote / APAC
    if is_remote and any(
        r in loc_str for r in ["global", "worldwide", "apac", "anywhere", "remote"]
    ):
        reasons.append(f"Acceptable global remote location: {job.location}.")
        return 70.0, True, reasons

    # 4. Non-India on-site
    foreign_regions = [
        "us",
        "usa",
        "canada",
        "uk",
        "london",
        "emea",
        "poland",
        "germany",
        "san francisco",
        "new york",
    ]
    if any(f in loc_str for f in foreign_regions) and not is_remote:
        reasons.append(f"Disqualified: Non-India on-site location ({job.location}).")
        return 0.0, False, reasons

    reasons.append(f"Location compatibility neutral ({job.location}).")
    return 60.0, True, reasons


def match_job(
    job: CanonicalJobPost,
    profile: CandidateProfile | None = None,
    weights: MatchWeights | None = None,
) -> JobMatchResult:
    """Evaluate a single CanonicalJobPost against a CandidateProfile.

    Returns:
        JobMatchResult with granular breakdown, scores, and recommendation (APPLY/STRETCH/SKIP).
    """
    active_profile = profile or CandidateProfile()
    active_weights = weights or MatchWeights()

    # 1. Compute component scores
    tech_score, matched_skills, missing_skills, tech_reasons = evaluate_technical_skills(
        job, active_profile
    )
    role_score, matched_role_kws, role_reasons = evaluate_role_relevance(job, active_profile)
    exp_score, exp_eligible, exp_reasons = evaluate_experience_compatibility(job, active_profile)
    loc_score, loc_eligible, loc_reasons = evaluate_location_compatibility(job, active_profile)

    # 2. Compute weighted overall score
    overall_score = round(
        (active_weights.technical_weight * tech_score)
        + (active_weights.role_weight * role_score)
        + (active_weights.experience_weight * exp_score)
        + (active_weights.location_weight * loc_score),
        1,
    )

    # 3. Determine recommendation
    score_reasons = tech_reasons + role_reasons + exp_reasons + loc_reasons

    if role_score <= 10.0 or loc_score == 0.0:
        recommendation = MatchRecommendation.SKIP
        score_reasons.append(
            "Classified as SKIP due to role disqualification or ineligible location."
        )
    elif overall_score >= active_weights.apply_threshold and exp_eligible and loc_eligible:
        recommendation = MatchRecommendation.APPLY
        score_reasons.append(
            "Classified as APPLY: High technical fit, compatible role, "
            "and eligible experience/location."
        )
    elif overall_score >= active_weights.stretch_threshold or (tech_score >= 70.0 and loc_eligible):
        recommendation = MatchRecommendation.STRETCH
        score_reasons.append(
            "Classified as STRETCH: Viable technical match; "
            "requires 1-2 yrs experience or stretch effort."
        )
    else:
        recommendation = MatchRecommendation.SKIP
        score_reasons.append("Classified as SKIP: Overall match score below threshold.")

    breakdown = MatchBreakdown(
        technical_score=tech_score,
        role_score=role_score,
        experience_score=exp_score,
        location_score=loc_score,
        overall_score=overall_score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        matched_role_keywords=matched_role_kws,
        experience_eligible=exp_eligible,
        location_eligible=loc_eligible,
        score_reasons=score_reasons,
    )

    return JobMatchResult(
        canonical_id=job.canonical_id,
        job_title=job.title,
        company=job.company,
        location=job.location,
        recommendation=recommendation,
        overall_score=overall_score,
        breakdown=breakdown,
        application_urls=job.application_urls,
    )


def match_all_jobs(
    jobs: list[CanonicalJobPost],
    profile: CandidateProfile | None = None,
    weights: MatchWeights | None = None,
) -> list[JobMatchResult]:
    """Evaluate and rank all canonical jobs in descending order of overall score."""
    results = [match_job(job, profile, weights) for job in jobs]
    results.sort(key=lambda x: x.overall_score, reverse=True)
    return results
