"""Rank and evaluate canonical jobs against candidate profile."""

import json
from pathlib import Path

from personal_job_hunter.domain.matcher import match_all_jobs
from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
    MatchRecommendation,
)


def score_and_rank_canonical_jobs(
    input_file: Path | None = None,
    output_file: Path | None = None,
    profile: CandidateProfile | None = None,
) -> list[JobMatchResult]:
    """Load canonical_jobs.json, score each job against the profile, and save ranked_jobs.json."""
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    in_path = input_file or base_dir / "data" / "canonical_jobs.json"
    out_path = output_file or base_dir / "data" / "ranked_jobs.json"

    if not in_path.exists():
        raise FileNotFoundError(f"Canonical jobs file not found: {in_path}")

    with open(in_path, encoding="utf-8") as f:
        raw_canonical = json.load(f)

    canonical_posts = [CanonicalJobPost.model_validate(item) for item in raw_canonical]
    ranked_results = match_all_jobs(canonical_posts, profile=profile)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_results = [r.model_dump(mode="json") for r in ranked_results]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serialized_results, f, indent=2, ensure_ascii=False)

    return ranked_results


def main() -> None:
    """Run ranking on live canonical dataset and print top jobs."""
    results = score_and_rank_canonical_jobs()
    apply_jobs = [r for r in results if r.recommendation == MatchRecommendation.APPLY]
    stretch_jobs = [r for r in results if r.recommendation == MatchRecommendation.STRETCH]
    skip_jobs = [r for r in results if r.recommendation == MatchRecommendation.SKIP]

    print("\n" + "=" * 70)
    print("       PERSONAL AI JOB HUNTER — DETERMINISTIC MATCHING REPORT")
    print("=" * 70)
    print(f"Total Canonical Jobs Evaluated:  {len(results)}")
    print(f"[APPLY] Recommendations:         {len(apply_jobs)}")
    print(f"[STRETCH] Recommendations:       {len(stretch_jobs)}")
    print(f"[SKIP] Recommendations:          {len(skip_jobs)}")
    print("-" * 70)

    print("\nTop 10 High-Fit Job Postings (APPLY):")
    print("-" * 70)
    for i, job in enumerate(apply_jobs[:10], start=1):
        print(f"{i}. [{job.overall_score}/100] {job.job_title} @ {job.company}")
        print(f"   Location:  {job.location}")
        print(
            f"   Scores:    Tech={job.breakdown.technical_score} | "
            f"Role={job.breakdown.role_score} | "
            f"Exp={job.breakdown.experience_score} | "
            f"Loc={job.breakdown.location_score}"
        )
        print(f"   Matched:   {', '.join(job.breakdown.matched_skills[:6])}")
        print(f"   Apply URL: {job.application_urls[0] if job.application_urls else 'N/A'}")
        print()

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
