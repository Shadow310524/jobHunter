"""Ashby public job board collector.

Collects real job postings from legitimate public Ashby ATS endpoints
(e.g., https://api.ashbyhq.com/posting-api/job-board/{company}).
No scraping, no authentication bypass, no anti-bot evasion.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

# Configure logging
logger = logging.getLogger("ashby_collector")

# Curated list of top AI & technology employers using Ashby
DEFAULT_ASHBY_COMPANIES = [
    "openai",
    "cerebras",
    "perplexity",
    "cursor",
    "replit",
    "supabase",
    "sentry",
    "linear",
    "ramp",
    "midjourney",
    "quora",
    "posthog",
    "modal",
    "langfuse",
    "e2b",
    "dust",
    "instawork",
    "retool",
    "sourcegraph",
]

# Targeted engineering roles
TARGET_ROLE_KEYWORDS = [
    "engineer",
    "developer",
    "ai",
    "genai",
    "generative ai",
    "llm",
    "agentic",
    "machine learning",
    "ml",
    "backend",
    "software",
    "python",
    "platform",
    "data engineer",
    "applied ai",
    "architect",
    "full stack",
    "frontend",
]

# Exclusions (non-technical, sales, marketing, HR, etc.)
EXCLUDED_KEYWORDS = [
    "sales",
    "marketing",
    "bpo",
    "telecalling",
    "hr",
    "human resources",
    "recruiter",
    "recruiting",
    "talent acquisition",
    "account executive",
    "customer success",
    "financial",
    "legal",
    "counsel",
    "business development",
    "payroll",
    "operations lead",
    "communications",
]

# Target locations
TARGET_LOCATIONS = [
    "bangalore",
    "bengaluru",
    "india",
    "remote - india",
    "remote, india",
    "india - remote",
    "mumbai",
    "delhi",
    "hyderabad",
    "pune",
    "gurgaon",
    "noida",
    "chennai",
    "apac",
    "home based - apac",
    "remote, global",
    "worldwide",
    "anywhere",
]

# Recognized tech skills for deterministic extraction
COMMON_TECH_SKILLS = [
    "python",
    "fastapi",
    "django",
    "flask",
    "rest api",
    "rest apis",
    "postgresql",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "pgvector",
    "vector database",
    "rag",
    "retrieval-augmented generation",
    "embeddings",
    "langchain",
    "langgraph",
    "mcp",
    "fastmcp",
    "aws",
    "s3",
    "bedrock",
    "docker",
    "kubernetes",
    "k8s",
    "git",
    "github",
    "java",
    "spring boot",
    "c++",
    "rust",
    "go",
    "golang",
    "machine learning",
    "deep learning",
    "llm",
    "genai",
    "generative ai",
    "transformers",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "sql",
    "linux",
]


def extract_skills(text: str) -> list[str]:
    """Extract recognized tech skills deterministically using word boundaries."""
    if not text:
        return []
    lower_text = f" {text.lower()} "
    found_skills: set[str] = set()

    for skill in COMMON_TECH_SKILLS:
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, lower_text):
            found_skills.add(skill.upper() if len(skill) <= 4 else skill.title())

    return sorted(found_skills)


def is_target_role(title: str) -> bool:
    """Check if title matches engineering keywords and excludes non-technical roles."""
    lower_title = f" {title.lower()} "

    # 1. Exclude non-technical roles
    for ex in EXCLUDED_KEYWORDS:
        if re.search(rf"\b{re.escape(ex)}\b", lower_title):
            # Allow "partner engineer" or "deployment engineer" even if "partner" is in exclusions
            if "engineer" in lower_title or "developer" in lower_title:
                continue
            return False

    # 2. Match target engineering keywords with word boundaries
    for kw in TARGET_ROLE_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lower_title):
            return True

    return False


def is_target_location(location_str: str, is_remote: bool | None = None) -> bool:
    """Check if location matches Bangalore/India or broad Global/APAC Remote.

    Explicitly excludes foreign country-specific remotes (e.g. US Remote, UK Remote, EMEA).
    """
    if not location_str:
        return bool(is_remote)

    lower = location_str.lower()

    # 1. Direct positive match for India / Bangalore / Bengaluru / Indian tech hubs
    indian_cities = [
        "bangalore",
        "bengaluru",
        "india",
        "remote - india",
        "remote, india",
        "india - remote",
        "mumbai",
        "delhi",
        "hyderabad",
        "pune",
        "gurgaon",
        "noida",
        "chennai",
    ]
    if any(city in lower for city in indian_cities):
        return True

    # 2. Exclude foreign country-specific locations
    foreign_regions = [
        "us -",
        "remote (us)",
        "us only",
        "usa",
        "united states",
        "canada",
        "toronto",
        "uk",
        "london",
        "emea",
        "europe",
        "poland",
        "germany",
        "france",
        "san francisco",
        "new york",
        "seattle",
        "sunnyvale",
        "california",
    ]
    if any(f in lower for f in foreign_regions):
        return False

    # 3. Match global / APAC remote
    global_remotes = [
        "global",
        "worldwide",
        "anywhere",
        "apac",
        "home based - apac",
        "remote - apac",
    ]
    if any(g in lower for g in global_remotes):
        return True

    if is_remote and lower.strip() in ["remote", "remote - global", "remote, global"]:
        return True

    return False


def infer_experience_level(title: str, description: str) -> str:
    """Infer experience level from title and description without falsifying company data."""
    combined = f"{title} {description[:400]}".lower()
    if any(
        k in combined
        for k in ["senior", "sr.", "lead", "staff", "principal", "director", "manager"]
    ):
        return "Senior / 3+ years (Stretch)"
    if any(
        k in combined
        for k in ["intern", "graduate", "fresher", "junior", "entry level", "associate"]
    ):
        return "Fresher / 0-2 years (Target)"
    return "0-3 years"


async def fetch_company_jobs(client: httpx.AsyncClient, company: str) -> list[dict[str, Any]]:
    """Fetch raw job postings for a company from Ashby Public API."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company}"
    logger.info("Fetching jobs for company: %s", company)

    try:
        response = await client.get(url, timeout=12.0)
        if response.status_code == 404:
            logger.warning("Ashby board not found for '%s' (404)", company)
            return []
        response.raise_for_status()
        data = response.json()
        jobs: list[dict[str, Any]] = data.get("jobs", [])
        logger.info("Received %d raw jobs for '%s'", len(jobs), company)
        return jobs
    except httpx.TimeoutException:
        logger.warning("Timeout fetching jobs for '%s'", company)
        return []
    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP error %s fetching '%s'", exc.response.status_code, company)
        return []
    except Exception as exc:
        logger.error("Unexpected error fetching '%s': %s", company, exc)
        return []


def parse_and_normalize_job(raw_job: dict[str, Any], company: str) -> dict[str, Any] | None:
    """Normalize raw Ashby job object into standard dictionary schema."""
    title = str(raw_job.get("title") or "").strip()
    if not title or not is_target_role(title):
        return None

    primary_location = str(raw_job.get("location") or "").strip()
    secondary_locations_raw = raw_job.get("secondaryLocations") or []
    secondary_locations = [
        str(loc.get("location")) if isinstance(loc, dict) else str(loc)
        for loc in secondary_locations_raw
    ]

    all_locations_str = " ".join([primary_location] + secondary_locations).strip()
    is_remote = bool(raw_job.get("isRemote"))

    if not is_target_location(all_locations_str, is_remote=is_remote):
        return None

    # Ashby provides clean plaintext description natively
    plain_description = str(raw_job.get("descriptionPlain") or "").strip()
    department = str(raw_job.get("department") or "")
    employment_type = str(raw_job.get("employmentType") or "")
    workplace_type = str(raw_job.get("workplaceType") or ("Remote" if is_remote else "On-site"))

    job_url = str(raw_job.get("jobUrl") or "").strip()
    apply_url = str(raw_job.get("applyUrl") or job_url).strip()
    published_date = raw_job.get("publishedAt")

    # Inferred attributes (clearly labeled to preserve integrity)
    inferred_skills = extract_skills(f"{title} {plain_description}")
    inferred_exp = infer_experience_level(title, plain_description)

    return {
        "source": "ashby",
        "job_id": f"ashby_{company}_{raw_job.get('id')}",
        "title": title,
        "company": company.title(),
        "location": primary_location or "Remote",
        "secondary_locations": secondary_locations,
        "work_mode": workplace_type,
        "is_remote": is_remote,
        "employment_type": employment_type,
        "department": department,
        "raw_experience_text": None,  # Ashby API does not provide a separate raw experience field
        "inferred_experience_level": inferred_exp,
        "salary": raw_job.get("compensation"),  # Structured compensation if provided
        "posted_date": published_date,
        "description": plain_description,
        "inferred_skills": inferred_skills,
        "job_url": job_url,
        "official_application_url": apply_url,
    }


async def collect_ashby_jobs(
    companies: list[str] | None = None,
    output_file: Path | None = None,
    request_delay_seconds: float = 0.5,
) -> list[dict[str, Any]]:
    """Collect, filter, normalize, and deduplicate jobs across Ashby company boards.

    Args:
        companies: List of company board slugs. Defaults to DEFAULT_ASHBY_COMPANIES.
        output_file: Path where JSON output should be saved.
        request_delay_seconds: Polite delay between company API requests.

    Returns:
        List of normalized job dictionary records.
    """
    target_companies = companies or DEFAULT_ASHBY_COMPANIES
    collected_jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    headers = {
        "User-Agent": "PersonalJobHunter/0.1.0 (Ethical Career Assistant; +https://github.com/Shadow310524/jobHunter)",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for index, company in enumerate(target_companies):
            raw_jobs = await fetch_company_jobs(client, company)

            for raw_job in raw_jobs:
                normalized = parse_and_normalize_job(raw_job, company)
                if normalized:
                    job_url = normalized["job_url"]
                    if job_url not in seen_urls:
                        seen_urls.add(job_url)
                        collected_jobs.append(normalized)

            if index < len(target_companies) - 1:
                await asyncio.sleep(request_delay_seconds)

    logger.info(
        "Total relevant jobs collected across %d Ashby companies: %d",
        len(target_companies),
        len(collected_jobs),
    )

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(collected_jobs, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d jobs to %s", len(collected_jobs), output_file)

    return collected_jobs


async def main() -> None:
    """Entrypoint for running the Ashby collector directly."""
    output_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "ashby_jobs.json"
    print(f"Starting Ashby job collection across {len(DEFAULT_ASHBY_COMPANIES)} tech companies...")
    jobs = await collect_ashby_jobs(output_file=output_path)
    print(f"\nCollection complete! Found {len(jobs)} target jobs.")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
