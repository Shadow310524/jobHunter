"""Deterministic Candidate Profile Matcher & Scoring Engine (Calibrated Phase 5B).

100% deterministic evaluation of CanonicalJobPost entities against a CandidateProfile.
Provides multi-tier role relevance, granular experience parsing, strict location hierarchy,
and conservative classification (APPLY / STRETCH / SKIP).
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
    "aws": ["aws", "amazon web services"],
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
    "aws": "AWS",
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

# Role Tiers
DISQUALIFIED_ROLES = [
    "manager",
    "director",
    "vp",
    "head of",
    "recruiter",
    "talent",
    "hr",
    "human resources",
    "sales",
    "account executive",
    "marketing",
    "finance",
    "payroll",
    "legal",
    "counsel",
    "operations manager",
    "strategy",
    "accountant",
    "communications",
    "bpo",
    "telecalling",
    "area collections",
]

SUPPORT_OPS_ROLES = [
    "support",
    "sustaining",
    "field engineer",
    "desktop",
    "alliances",
    "l1",
    "l2",
    "l3",
    "technical support",
    "qa",
    "quality assurance",
    "test engineer",
    "sdet",
    "security engineer",
    "network engineer",
    "solutions architect",
    "sales engineer",
]

HARDWARE_NICHE_ROLES = [
    "mir",
    "graphics",
    "windowing",
    "embedded",
    "kernel",
    "firmware",
    "asic",
    "fpga",
    "hardware",
]

AI_CORE_ROLES = [
    "ai engineer",
    "genai",
    "generative ai",
    "ai platform",
    "ai backend",
    "applied ai",
    "llm",
    "agentic",
    "machine learning engineer",
    "ml engineer",
    "ml platform",
    "ai software engineer",
    "ai deployment engineer",
    "ai agents",
    "data + ai",
]

BACKEND_ROLES = [
    "python engineer",
    "python developer",
    "backend engineer",
    "backend developer",
    "platform engineer",
    "cloud platform engineer",
    "api engineer",
    "database engineer",
    "data engineer",
    "distributed systems",
    "forward deployed engineer",
    "fde",
]

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


def evaluate_role_relevance(
    job: CanonicalJobPost, profile: CandidateProfile
) -> tuple[float, list[str], list[str]]:
    """Evaluate role title relevance with strict tiering.

    Returns:
        (role_score, matched_role_keywords, reasons)
    """
    reasons: list[str] = []
    matched_keywords: list[str] = []
    title_lower = f" {job.title.lower()} "

    # 1. Disqualified non-technical roles
    for ex in DISQUALIFIED_ROLES:
        if re.search(rf"\b{re.escape(ex)}\b", title_lower):
            if "engineer" not in title_lower and "developer" not in title_lower:
                reasons.append(f"Disqualified Role: Title contains excluded keyword '{ex}'.")
                return 0.0, [], reasons

    # 2. Support / Sustaining / IT / QA / Security roles
    for sup in SUPPORT_OPS_ROLES:
        if re.search(rf"\b{re.escape(sup)}\b", title_lower):
            reasons.append(f"Support/Ops Role: Title contains operational/support keyword '{sup}'.")
            return 35.0, [sup], reasons

    # 3. Hardware / Kernel / Mir Graphics niche
    for hw in HARDWARE_NICHE_ROLES:
        if re.search(rf"\b{re.escape(hw)}\b", title_lower):
            reasons.append(f"Hardware/Kernel Niche Role: Title contains '{hw}'.")
            return 40.0, [hw], reasons

    # 4. Tier 1: Core AI / GenAI / LLM / AI Platform
    for ai_kw in AI_CORE_ROLES:
        if ai_kw in title_lower:
            matched_keywords.append(ai_kw)

    if matched_keywords:
        reasons.append(f"Tier 1 Target AI Role: '{job.title}'.")
        return 100.0, matched_keywords, reasons

    # 5. Tier 2: Core Backend / Python / Platform
    for bk_kw in BACKEND_ROLES:
        if re.search(rf"\b{re.escape(bk_kw)}\b", title_lower):
            matched_keywords.append(bk_kw)

    if matched_keywords:
        reasons.append(f"Tier 2 Target Backend/Python Role: '{job.title}'.")
        return 85.0, matched_keywords, reasons

    # 6. Tier 3: General Software Engineer / Full Stack
    if any(w in title_lower for w in ["software engineer", "software developer", "sde"]):
        matched_keywords.append("software engineer")
        reasons.append(f"Tier 3 General Software Engineering Role: '{job.title}'.")
        return 70.0, matched_keywords, reasons

    reasons.append(f"Peripheral Engineering Role: '{job.title}'.")
    return 50.0, matched_keywords, reasons


def evaluate_technical_skills(
    job: CanonicalJobPost, profile: CandidateProfile, role_score: float
) -> tuple[float, list[str], list[str], list[str]]:
    """Evaluate technical skills with role-aware anti-inflation weighting.

    Returns:
        (technical_score, matched_skills, missing_skills, reasons)
    """
    reasons: list[str] = []

    # 1. Normalize candidate skills
    core_cand = {normalize_skill_name(s) for s in profile.core_skills}
    sec_cand = {normalize_skill_name(s) for s in profile.secondary_skills}
    all_cand = core_cand | sec_cand

    # 2. Gather normalized job skills
    raw_job_skills = set(job.inferred_skills) | extract_skills_from_text(
        f"{job.title} {job.description}"
    )
    job_skills = {normalize_skill_name(s) for s in raw_job_skills}

    if not job_skills:
        reasons.append("Baseline technical score (no explicit skill requirements in description).")
        return 65.0, [], [], reasons

    matched_skills = sorted(job_skills & all_cand)
    missing_skills = sorted(job_skills - all_cand)

    # Core AI skill checking for AI Tier 1 roles
    ai_skills_cand = {
        "AI Agents",
        "LangChain",
        "LangGraph",
        "RAG",
        "LLM",
        "GenAI",
        "AWS Bedrock",
        "pgvector",
        "Embeddings",
        "PyTorch",
        "Machine Learning",
        "Deep Learning",
    }
    matched_ai_skills = [s for s in matched_skills if s in ai_skills_cand]

    # Weighted overlap calculation
    total_weight = sum(2.0 if s in core_cand else 1.0 for s in matched_skills)
    missing_weight = sum(1.2 for _ in missing_skills)

    raw_ratio = (
        total_weight / (total_weight + missing_weight)
        if (total_weight + missing_weight) > 0
        else 0.5
    )
    technical_score = round(min(100.0, raw_ratio * 100.0), 1)

    # Competency boosters
    if "Python" in matched_skills:
        technical_score = min(100.0, technical_score + 10.0)
    if any(s in matched_skills for s in ["FastAPI", "PostgreSQL", "Docker"]):
        technical_score = min(100.0, technical_score + 5.0)

    # Role-aware skill check: If AI role has ZERO AI skills, cap technical score
    if role_score >= 95.0 and not matched_ai_skills:
        technical_score = min(60.0, technical_score)
        reasons.append(
            "Technical score capped at 60.0 (AI role without matched core AI/LLM skills)."
        )

    matched_sample = ", ".join(matched_skills[:5])
    reasons.append(
        f"Matched {len(matched_skills)} skills "
        f"({matched_sample}{'...' if len(matched_skills) > 5 else ''})."
    )
    if missing_skills:
        missing_sample = ", ".join(missing_skills[:4])
        reasons.append(
            f"Missing {len(missing_skills)} skills "
            f"({missing_sample}{'...' if len(missing_skills) > 4 else ''})."
        )

    return technical_score, matched_skills, missing_skills, reasons


def extract_min_experience_years(text: str) -> int | None:
    """Extract minimum years of experience using deterministic regex."""
    patterns = [
        r"(\d+)\s*(?:-|to|\+)?\s*(\d+)?\s*(?:\+)?\s*years?(?:\s+of)?\s+(?:relevant\s+)?experience",
        r"experience\s*(?:of|:)?\s*(\d+)\s*(?:-|to|\+)?\s*(\d+)?\s*years?",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass
    return None


def evaluate_experience_compatibility(
    job: CanonicalJobPost, profile: CandidateProfile
) -> tuple[float, bool, list[str]]:
    """Evaluate experience level compatibility with fine-grained evidence.

    Returns:
        (experience_score, experience_eligible, reasons)
    """
    reasons: list[str] = []
    title_lower = f" {job.title.lower()} "

    # 1. Title High Seniority Checks
    if any(
        re.search(rf"\b{re.escape(w)}\b", title_lower)
        for w in ["staff", "principal", "director", "head", "vp", "lead"]
    ):
        reasons.append(f"Ineligible: High seniority title ('{job.title}').")
        return 20.0, False, reasons

    if any(
        re.search(rf"\b{re.escape(w)}\b", title_lower)
        for w in ["senior", "sr.", "sr", "sde iii", "level 3", "engineer iii"]
    ):
        reasons.append(f"Stretch: Senior title ('{job.title}', 3-5+ years expected).")
        return 35.0, False, reasons

    if any(
        re.search(rf"\b{re.escape(w)}\b", title_lower) for w in ["sde ii", "engineer ii", "level 2"]
    ):
        reasons.append(f"Stretch: Mid-level title ('{job.title}', 2-3 years expected).")
        return 65.0, False, reasons

    if any(
        re.search(rf"\b{re.escape(w)}\b", title_lower)
        for w in [
            "intern",
            "graduate",
            "associate",
            "junior",
            "entry level",
            "sde i",
            "engineer i",
            "fresher",
        ]
    ):
        reasons.append("Eligible: Explicit early career / entry-level title.")
        return 100.0, True, reasons

    # 2. Parse explicit years from description
    min_years = extract_min_experience_years(
        f"{job.raw_experience_text or ''} {job.description[:1200]}"
    )
    if min_years is not None:
        if min_years <= 1:
            reasons.append(
                f"Eligible: Requires {min_years}+ years experience (matches 2026 graduate profile)."
            )
            return 100.0, True, reasons
        if min_years == 2:
            reasons.append(
                "Eligible / Stretch: Requires 2 years experience (within candidate capability)."
            )
            return 85.0, True, reasons
        if min_years == 3:
            reasons.append("Stretch: Requires 3 years experience (moderate experience gap).")
            return 55.0, False, reasons
        if min_years in [4, 5]:
            reasons.append(f"Ineligible / Stretch: Requires {min_years}+ years experience.")
            return 30.0, False, reasons
        if min_years >= 6:
            reasons.append(f"Ineligible: Requires {min_years}+ years experience.")
            return 15.0, False, reasons

    # 3. Inferred experience from collector
    inf_exp = str(job.inferred_experience_level or "").lower()
    if "senior" in inf_exp or "3+" in inf_exp:
        reasons.append("Stretch: Inferred senior experience level.")
        return 40.0, False, reasons
    if "fresher" in inf_exp or "0-2" in inf_exp:
        reasons.append("Eligible: Inferred early career experience level.")
        return 90.0, True, reasons

    reasons.append("Eligible (Default): No explicit years specified in title or description.")
    return 75.0, True, reasons


def evaluate_location_compatibility(
    job: CanonicalJobPost, profile: CandidateProfile
) -> tuple[float, bool, list[str]]:
    """Evaluate location compatibility with strict Indian residency verification.

    Returns:
        (location_score, location_eligible, reasons)
    """
    reasons: list[str] = []
    all_locations = [job.location] + job.secondary_locations
    loc_str = " ".join(all_locations).lower()
    is_remote = job.is_remote or job.work_mode == WorkMode.REMOTE or "remote" in loc_str

    # 1. Tier 1: Bangalore / Bengaluru or Explicit Remote India
    if any(b in loc_str for b in ["bangalore", "bengaluru"]) or (
        is_remote
        and any(
            r in loc_str
            for r in ["remote - india", "remote, india", "india - remote", "india remote"]
        )
    ):
        reasons.append(f"Tier 1 Location: Top priority location match ({job.location}).")
        return 100.0, True, reasons

    # 2. Tier 2: Indian Tech Hubs (Hyderabad, Pune, Mumbai, Delhi, Gurgaon, Noida, Chennai)
    indian_hubs = ["hyderabad", "pune", "mumbai", "delhi", "gurgaon", "noida", "chennai"]
    if any(h in loc_str for h in indian_hubs):
        reasons.append(f"Tier 2 Location: Verified Indian tech hub ({job.location}).")
        return 80.0, True, reasons

    # 3. Tier 3: Broad India / APAC Remote
    if "india" in loc_str or (is_remote and "apac" in loc_str):
        reasons.append(f"Tier 3 Location: India or APAC Remote ({job.location}).")
        return 65.0, True, reasons

    # 4. Tier 4: Worldwide / Global Remote (Unverified Indian tax entity)
    if is_remote and any(g in loc_str for g in ["global", "worldwide", "anywhere", "remote"]):
        reasons.append(
            f"Tier 4 Location: Worldwide Remote without verified India entity ({job.location}). "
            "Stretch-eligible only."
        )
        return 50.0, False, reasons

    # 5. Tier 5: Foreign on-site (Disqualified)
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
        reasons.append(f"Disqualified Location: Foreign on-site ({job.location}).")
        return 0.0, False, reasons

    reasons.append(f"Location neutral ({job.location}).")
    return 60.0, True, reasons


def match_job(
    job: CanonicalJobPost,
    profile: CandidateProfile | None = None,
    weights: MatchWeights | None = None,
) -> JobMatchResult:
    """Evaluate a single CanonicalJobPost against a CandidateProfile with calibrated thresholds.

    Returns:
        JobMatchResult with granular breakdown, scores, and recommendation (APPLY/STRETCH/SKIP).
    """
    active_profile = profile or CandidateProfile()
    # Default calibrated weights
    active_weights = weights or MatchWeights(
        role_weight=0.35,
        technical_weight=0.30,
        experience_weight=0.20,
        location_weight=0.15,
        apply_threshold=80.0,
        stretch_threshold=55.0,
    )

    # 1. Compute component scores
    role_score, matched_role_kws, role_reasons = evaluate_role_relevance(job, active_profile)
    tech_score, matched_skills, missing_skills, tech_reasons = evaluate_technical_skills(
        job, active_profile, role_score
    )
    exp_score, exp_eligible, exp_reasons = evaluate_experience_compatibility(job, active_profile)
    loc_score, loc_eligible, loc_reasons = evaluate_location_compatibility(job, active_profile)

    # 2. Compute weighted overall score
    overall_score = round(
        (active_weights.role_weight * role_score)
        + (active_weights.technical_weight * tech_score)
        + (active_weights.experience_weight * exp_score)
        + (active_weights.location_weight * loc_score),
        1,
    )

    score_reasons = role_reasons + tech_reasons + exp_reasons + loc_reasons

    # 3. Calibrated Classification Logic
    # Strict APPLY requirements
    is_apply_eligible = (
        overall_score >= active_weights.apply_threshold
        and role_score >= 85.0  # Must be Tier 1 AI or Tier 2 Python/Backend
        and tech_score >= 70.0
        and exp_eligible is True  # Cannot be Senior, Staff, Lead, SDE II, or 3+ yrs
        and loc_eligible is True  # Must be Bangalore, Remote India, or Indian hub
    )

    # STRETCH requirements
    is_stretch_eligible = (
        overall_score >= active_weights.stretch_threshold
        and role_score >= 65.0  # At least general SWE
        and tech_score >= 60.0
        and exp_score >= 30.0  # Cannot be Staff/Principal/7+ yrs
        and loc_score >= 45.0  # Cannot be foreign on-site
    )

    if is_apply_eligible:
        recommendation = MatchRecommendation.APPLY
        score_reasons.append(
            "Final Recommendation: APPLY (High-priority target: matches target role, "
            "technical skills, experience eligibility, and target location)."
        )
    elif is_stretch_eligible:
        recommendation = MatchRecommendation.STRETCH
        score_reasons.append(
            "Final Recommendation: STRETCH (Viable opportunity: relevant technical stack with "
            "moderate experience gap, senior title, or global remote setup)."
        )
    else:
        recommendation = MatchRecommendation.SKIP
        score_reasons.append(
            "Final Recommendation: SKIP (Disqualified or low fit: operational/support role, "
            "ineligible location, or significant experience mismatch)."
        )

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
