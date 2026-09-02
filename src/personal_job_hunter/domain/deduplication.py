"""Deterministic deduplication and canonical identity engine.

Multi-Tier Deduplication Hierarchy:
Tier 1: Canonical URL Match (Exact -> Merged)
Tier 2: Source + Source Job ID Match (Exact -> Merged)
Tier 3: Cross-Source Candidate Match (Company + Title + Location -> Flagged ONLY, NOT merged)
"""

import hashlib
import re
import urllib.parse

from personal_job_hunter.domain.models import (
    CanonicalJobPost,
    DeduplicationResult,
    JobSource,
    SourceProvenance,
    UnifiedJobPost,
    WorkMode,
)

# Known analytics, tracking, and attribution parameters to remove during URL normalization
KNOWN_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "lever-source",
    "lever-origin",
    "gh_src",
    "fbclid",
    "gclid",
    "msclkid",
    "dclid",
    "twclid",
    "mc_cid",
    "mc_eid",
}


def normalize_url(raw_url: str) -> str:
    """Normalize a URL for exact matching while preserving structural query parameters.

    - Lowercases scheme and hostname.
    - Strips URL fragments (#hash).
    - Removes trailing slashes from path.
    - Strips only known tracking query parameters (preserving job IDs like ?gh_jid=...).
    - Deterministically sorts remaining query parameters.
    """
    if not raw_url or not isinstance(raw_url, str):
        return ""

    raw_url = raw_url.strip()
    if not raw_url.startswith(("http://", "https://")):
        return raw_url

    parsed = urllib.parse.urlsplit(raw_url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove standard default ports
    if (scheme == "http" and netloc.endswith(":80")) or (
        scheme == "https" and netloc.endswith(":443")
    ):
        netloc = netloc.rsplit(":", 1)[0]

    path = parsed.path.rstrip("/")
    if not path:
        path = "/"

    query_tuples = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_query = [(k, v) for k, v in query_tuples if k.lower() not in KNOWN_TRACKING_PARAMS]
    filtered_query.sort(key=lambda x: (x[0], x[1]))
    new_query = urllib.parse.urlencode(filtered_query)

    return urllib.parse.urlunsplit((scheme, netloc, path, new_query, ""))


def normalize_key_text(text: str) -> str:
    """Normalize text for candidate grouping (lowercase, alphanumeric tokens only)."""
    if not text:
        return ""
    # Replace non-alphanumeric with space
    clean = re.sub(r"[^a-zA-Z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", "_", clean)


def generate_candidate_group_key(company: str, title: str, location: str) -> str:
    """Generate a candidate group key for Tier 3 similarity flagging."""
    norm_comp = normalize_key_text(company)
    norm_title = normalize_key_text(title)
    norm_loc = normalize_key_text(location)
    return f"cand::{norm_comp}::{norm_title}::{norm_loc}"


def create_source_provenance(post: UnifiedJobPost) -> SourceProvenance:
    """Create a SourceProvenance record from a UnifiedJobPost."""
    return SourceProvenance(
        source=post.source,
        source_job_id=post.job_id,
        job_url=post.job_url,
        official_application_url=post.official_application_url,
        posted_date=post.posted_date,
        raw_metadata=post.metadata,
    )


def create_canonical_job_post(post: UnifiedJobPost) -> CanonicalJobPost:
    """Convert a single UnifiedJobPost into a new CanonicalJobPost."""
    provenance = create_source_provenance(post)
    canonical_hash = hashlib.sha256(
        f"{post.source}::{post.job_id}::{normalize_url(post.job_url)}".encode()
    ).hexdigest()[:16]

    app_urls = [post.official_application_url] if post.official_application_url else []
    if post.job_url and post.job_url not in app_urls:
        app_urls.append(post.job_url)

    return CanonicalJobPost(
        canonical_id=f"canon_{canonical_hash}",
        title=post.title,
        company=post.company,
        location=post.location,
        secondary_locations=list(post.secondary_locations),
        work_mode=post.work_mode,
        is_remote=post.is_remote,
        employment_type=post.employment_type,
        department=post.department,
        posted_date=post.posted_date,
        description=post.description,
        salary=post.salary,
        raw_experience_text=post.raw_experience_text,
        inferred_experience_level=post.inferred_experience_level,
        inferred_skills=list(post.inferred_skills),
        sources=[post.source],
        source_records=[provenance],
        application_urls=app_urls,
    )


def merge_into_canonical_job(existing: CanonicalJobPost, new_post: UnifiedJobPost) -> None:
    """Deterministically merge a confirmed duplicate into an existing CanonicalJobPost."""
    # 1. Add provenance record
    new_provenance = create_source_provenance(new_post)
    existing.source_records.append(new_provenance)

    # 2. Add source if not already tracked
    if new_post.source not in existing.sources:
        existing.sources.append(new_post.source)

    # 3. Add application URLs
    for url in [new_post.official_application_url, new_post.job_url]:
        if url and url not in existing.application_urls:
            existing.application_urls.append(url)

    # 4. Secondary locations union
    for loc in new_post.secondary_locations:
        if loc not in existing.secondary_locations:
            existing.secondary_locations.append(loc)

    # 5. Preserve richest description
    if len(new_post.description) > len(existing.description):
        existing.description = new_post.description

    # 6. Merge inferred skills (union)
    for skill in new_post.inferred_skills:
        if skill not in existing.inferred_skills:
            existing.inferred_skills.append(skill)
    existing.inferred_skills.sort()

    # 7. Work mode refinement (prefer explicit over Unknown)
    if existing.work_mode == WorkMode.UNKNOWN and new_post.work_mode != WorkMode.UNKNOWN:
        existing.work_mode = new_post.work_mode

    # 8. Flags & dates
    existing.is_remote = existing.is_remote or new_post.is_remote
    if not existing.department and new_post.department:
        existing.department = new_post.department
    if not existing.salary and new_post.salary:
        existing.salary = new_post.salary
    if not existing.raw_experience_text and new_post.raw_experience_text:
        existing.raw_experience_text = new_post.raw_experience_text


def deduplicate_jobs(jobs: list[UnifiedJobPost]) -> DeduplicationResult:
    """Execute conservative deterministic deduplication across a list of UnifiedJobPost items.

    Returns:
        DeduplicationResult containing canonical jobs, merged count, and candidate groups.
    """
    total_input = len(jobs)
    canonical_jobs: list[CanonicalJobPost] = []

    # Fast lookup indexes for Tier 1 and Tier 2 exact matching
    url_to_canonical: dict[str, CanonicalJobPost] = {}
    source_id_to_canonical: dict[tuple[JobSource, str], CanonicalJobPost] = {}

    confirmed_merges = 0

    for post in jobs:
        norm_job_url = normalize_url(post.job_url)
        norm_app_url = normalize_url(post.official_application_url)

        matched_canonical: CanonicalJobPost | None = None

        # --- Tier 1 Check: Exact Canonical URL Match ---
        if norm_job_url and norm_job_url in url_to_canonical:
            matched_canonical = url_to_canonical[norm_job_url]
        elif norm_app_url and norm_app_url in url_to_canonical:
            matched_canonical = url_to_canonical[norm_app_url]

        # --- Tier 2 Check: Source + Source Job ID Match ---
        if not matched_canonical:
            src_key = (post.source, post.job_id)
            if src_key in source_id_to_canonical:
                matched_canonical = source_id_to_canonical[src_key]

        # Merge or Create
        if matched_canonical:
            merge_into_canonical_job(matched_canonical, post)
            confirmed_merges += 1
        else:
            new_canon = create_canonical_job_post(post)
            canonical_jobs.append(new_canon)

            # Register in indexes
            if norm_job_url:
                url_to_canonical[norm_job_url] = new_canon
            if norm_app_url:
                url_to_canonical[norm_app_url] = new_canon
            source_id_to_canonical[(post.source, post.job_id)] = new_canon

    # --- Tier 3 Candidate Matching (Flagging ONLY, NO Auto-Merge) ---
    candidate_groups: dict[str, list[str]] = {}
    for canon in canonical_jobs:
        group_key = generate_candidate_group_key(canon.company, canon.title, canon.location)
        if group_key not in candidate_groups:
            candidate_groups[group_key] = []
        candidate_groups[group_key].append(canon.canonical_id)

    # Filter candidate groups that have > 1 job and tag them
    potential_duplicate_groups: dict[str, list[str]] = {}
    flagged_jobs_count = 0

    canon_by_id = {c.canonical_id: c for c in canonical_jobs}

    for group_key, job_id_list in candidate_groups.items():
        if len(job_id_list) > 1:
            potential_duplicate_groups[group_key] = job_id_list
            for j_id in job_id_list:
                canon_by_id[j_id].duplicate_candidate_group = group_key
                flagged_jobs_count += 1

    return DeduplicationResult(
        total_input_records=total_input,
        unique_canonical_jobs=len(canonical_jobs),
        confirmed_duplicates_merged=confirmed_merges,
        potential_duplicate_groups_count=len(potential_duplicate_groups),
        potential_duplicate_jobs_count=flagged_jobs_count,
        canonical_jobs=canonical_jobs,
        potential_duplicate_groups=potential_duplicate_groups,
    )
