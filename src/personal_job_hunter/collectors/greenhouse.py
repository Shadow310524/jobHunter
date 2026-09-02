"""Greenhouse public job board collector.

Collects real job postings from legitimate public Greenhouse ATS endpoints
(e.g., https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true).
No scraping, no authentication bypass, no anti-bot evasion.
"""

import asyncio
import json
import logging
import re
from html import unescape
from pathlib import Path
from typing import Any

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("greenhouse_collector")

# Default curated list of tech companies with active public Greenhouse boards
DEFAULT_COMPANIES = [
    "postman",
    "inmobi",
    "groww",
    "cloudflare",
    "databricks",
    "elastic",
    "canonical",
    "airtable",
    "couchbase",
    "cloudera",
    "snyk",
    "dbtlabs",
    "confluent",
    "mongodb",
]

# Targeted roles and keywords for software & AI engineering
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
]

# Explicit exclusions (non-technical, sales, marketing, HR, etc.)
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
]

# Target locations
TARGET_LOCATIONS = [
    "bangalore",
    "bengaluru",
    "india",
    "remote - india",
    "remote",
    "home based - apac",
    "apac",
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


def clean_html_text(raw_html: str) -> str:
    """Convert HTML content into plain text safely (handles double/escaped HTML)."""
    if not raw_html:
        return ""
    # 1. Unescape HTML entities first so &lt;div&gt; becomes <div>
    text = unescape(raw_html)
    # 2. Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # 3. Final entity unescape and whitespace normalization
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_skills(text: str) -> list[str]:
    """Extract recognized tech skills deterministically using word boundaries."""
    if not text:
        return []
    lower_text = f" {text.lower()} "
    found_skills: set[str] = set()

    for skill in COMMON_TECH_SKILLS:
        # Match whole words/phrases
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, lower_text):
            found_skills.add(skill.upper() if len(skill) <= 4 else skill.title())

    return sorted(found_skills)


def detect_work_mode(location_name: str, title: str, description: str) -> str:
    """Detect if the role is Remote, Hybrid, or On-site."""
    combined = f"{location_name} {title} {description[:500]}".lower()
    if "remote" in combined or "home based" in combined or "work from home" in combined:
        return "Remote"
    if "hybrid" in combined:
        return "Hybrid"
    if "on-site" in combined or "onsite" in combined or "office based" in combined:
        return "On-site"
    return "On-site" if location_name else "Unknown"


def is_target_role(title: str) -> bool:
    """Check if the title matches target engineering profiles and excludes non-technical roles."""
    lower_title = title.lower()

    # 1. Exclude non-technical roles
    if any(ex in lower_title for ex in EXCLUDED_KEYWORDS):
        return False

    # 2. Match target keywords
    return any(kw in lower_title for kw in TARGET_ROLE_KEYWORDS)


def is_target_location(location_name: str) -> bool:
    """Check if location matches Bangalore/India/Remote priorities.

    Prioritizes:
    - Bangalore / Bengaluru
    - India / Remote - India / Indian tech hubs
    - Global / APAC Remote (where India candidates are eligible)
    Excludes non-India local remotes (e.g. Remote Italy, Remote US).
    """
    if not location_name:
        return True

    lower_loc = location_name.lower()

    # 1. Direct positive match for India / Bangalore / Bengaluru / Indian cities
    indian_locations = [
        "bangalore",
        "bengaluru",
        "india",
        "remote - india",
        "remote, india",
        "hyderabad",
        "pune",
        "gurgaon",
        "noida",
        "mumbai",
        "chennai",
        "delhi",
    ]
    if any(loc in lower_loc for loc in indian_locations):
        return True

    # 2. General / APAC remote (eligible for Indian candidates)
    general_remote = [
        "home based - apac",
        "remote - apac",
        "apac",
        "anywhere",
        "worldwide",
        "remote - global",
    ]
    if any(loc in lower_loc for loc in general_remote):
        return True

    return False


async def fetch_company_jobs(client: httpx.AsyncClient, company: str) -> list[dict[str, Any]]:
    """Fetch raw job postings for a company from Greenhouse Public API."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
    logger.info("Fetching jobs for company: %s", company)

    try:
        response = await client.get(url, timeout=12.0)
        if response.status_code == 404:
            logger.warning("Greenhouse board not found for '%s' (404)", company)
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
    """Normalize raw Greenhouse job object into standard dictionary schema."""
    title = str(raw_job.get("title") or "").strip()
    if not title or not is_target_role(title):
        return None

    loc_obj = raw_job.get("location") or {}
    location_name = str(loc_obj.get("name") or "").strip()
    if not is_target_location(location_name):
        return None

    raw_content = str(raw_job.get("content") or "")
    plain_description = clean_html_text(raw_content)

    departments_raw = raw_job.get("departments") or []
    department_names = [
        str(dept.get("name"))
        for dept in departments_raw
        if isinstance(dept, dict) and dept.get("name")
    ]

    job_url = str(raw_job.get("absolute_url") or "").strip()
    posted_date = raw_job.get("updated_at")

    work_mode = detect_work_mode(location_name, title, plain_description)
    extracted_skills = extract_skills(f"{title} {plain_description}")

    # Experience heuristic detection from description
    experience_hint = "0-3 years"
    if any(k in title.lower() for k in ["senior", "sr.", "lead", "staff", "principal", "manager"]):
        experience_hint = "Senior / 3+ years (Stretch)"
    elif any(
        k in title.lower() or k in plain_description.lower()
        for k in ["intern", "graduate", "fresher", "junior", "entry"]
    ):
        experience_hint = "Fresher / 0-2 years (Target)"

    return {
        "job_id": f"gh_{company}_{raw_job.get('id')}",
        "title": title,
        "company": company.title(),
        "location": location_name or "Not Specified",
        "work_mode": work_mode,
        "experience": experience_hint,
        "salary": None,  # Greenhouse public API rarely publishes structured salary
        "posted_date": posted_date,
        "description": plain_description,
        "required_skills": extracted_skills,
        "preferred_skills": [],
        "job_url": job_url,
        "official_application_url": job_url,
        "departments": department_names,
        "source": "greenhouse",
    }


async def collect_greenhouse_jobs(
    companies: list[str] | None = None,
    output_file: Path | None = None,
    request_delay_seconds: float = 0.5,
) -> list[dict[str, Any]]:
    """Collect, filter, normalize, and deduplicate jobs across Greenhouse company boards.

    Args:
        companies: List of company board tokens. Defaults to DEFAULT_COMPANIES.
        output_file: Path where JSON output should be saved.
        request_delay_seconds: Polite delay between company API requests.

    Returns:
        List of normalized job dictionary records.
    """
    target_companies = companies or DEFAULT_COMPANIES
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

            # Respectful rate limiting between requests
            if index < len(target_companies) - 1:
                await asyncio.sleep(request_delay_seconds)

    logger.info(
        "Total relevant jobs collected across %d companies: %d",
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
    """Entrypoint for running the Greenhouse collector directly."""
    output_path = (
        Path(__file__).resolve().parent.parent.parent.parent / "data" / "greenhouse_jobs.json"
    )
    print(f"Starting Greenhouse job collection across {len(DEFAULT_COMPANIES)} tech companies...")
    jobs = await collect_greenhouse_jobs(output_file=output_path)
    print(f"\nCollection complete! Found {len(jobs)} target jobs.")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
