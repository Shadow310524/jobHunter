"""Hybrid Ranker: Runs deterministic + semantic matching on canonical dataset."""

import json
from pathlib import Path

from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
    MatchRecommendation,
    MatchWeights,
)
from personal_job_hunter.domain.semantic_matcher import match_all_jobs_hybrid
from personal_job_hunter.embeddings.service import FastEmbedService, MockEmbeddingService


def score_and_rank_canonical_jobs_hybrid(
    canonical_file: Path | str = Path("data/canonical_jobs.json"),
    output_file: Path | str = Path("data/hybrid_ranked_jobs.json"),
    profile: CandidateProfile | None = None,
    weights: MatchWeights | None = None,
    use_mock_embeddings: bool = False,
) -> list[tuple[JobMatchResult, list[float], list[float]]]:
    """Load canonical jobs, run hybrid matching, and persist ranked results."""
    canon_path = Path(canonical_file)
    if not canon_path.exists():
        raise FileNotFoundError(f"Canonical jobs file not found: {canon_path}")

    with open(canon_path, encoding="utf-8") as f:
        data = json.load(f)

    jobs = [CanonicalJobPost.model_validate(item) for item in data]
    active_profile = profile or CandidateProfile()
    svc = MockEmbeddingService() if use_mock_embeddings else FastEmbedService()

    ranked_tuples = match_all_jobs_hybrid(
        jobs=jobs,
        profile=active_profile,
        embedding_service=svc,
        weights=weights,
    )

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [t[0].model_dump(mode="json") for t in ranked_tuples]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2, ensure_ascii=False)

    return ranked_tuples


def main() -> None:
    """CLI runner to evaluate live canonical dataset with hybrid semantic matcher."""
    print("\nRunning Hybrid Deterministic + FastEmbed Semantic Matching...")
    results = score_and_rank_canonical_jobs_hybrid()

    match_results = [r[0] for r in results]
    apply_jobs = [r for r in match_results if r.recommendation == MatchRecommendation.APPLY]
    stretch_jobs = [r for r in match_results if r.recommendation == MatchRecommendation.STRETCH]
    skip_jobs = [r for r in match_results if r.recommendation == MatchRecommendation.SKIP]

    print("\n" + "=" * 75)
    print("   PERSONAL AI JOB HUNTER — HYBRID SEMANTIC MATCHING REPORT (Phase 7)")
    print("=" * 75)
    print(f"Total Canonical Jobs Evaluated:  {len(match_results)}")
    print(f"[APPLY] High-Priority Targets:   {len(apply_jobs)}")
    print(f"[STRETCH] Moderate Opportunities:{len(stretch_jobs)}")
    print(f"[SKIP] Low-Fit / Ineligible:     {len(skip_jobs)}")
    print("-" * 75)

    print(f"\nTop {min(20, len(match_results))} Hybrid Ranked Job Postings:")
    print("-" * 75)
    for i, job in enumerate(match_results[:20], start=1):
        tag = f"[{job.recommendation}]"
        bd = job.breakdown
        det_str = f"{bd.deterministic_score:.1f}" if bd.deterministic_score is not None else "N/A"
        sem_str = f"{bd.semantic_score:.1f}" if bd.semantic_score is not None else "N/A"
        sim_str = f"{bd.semantic_similarity:.4f}" if bd.semantic_similarity is not None else "N/A"

        print(f"{i:2d}. {tag:<9} [{job.overall_score:5.1f}/100] {job.job_title} @ {job.company}")
        print(f"    Location:    {job.location}")
        print(
            f"    Scores:      Combined={job.overall_score:5.1f} | "
            f"Det={det_str} | Sem={sem_str} (Cos={sim_str})"
        )
        print(
            f"    Components:  Role={bd.role_score:4.1f} | "
            f"Tech={bd.technical_score:4.1f} | "
            f"Exp={bd.experience_score:4.1f} | "
            f"Loc={bd.location_score:4.1f}"
        )
        if bd.matched_skills:
            print(f"    Matched:     {', '.join(bd.matched_skills[:6])}")
        print(f"    Apply URL:   {job.application_urls[0] if job.application_urls else 'N/A'}")
        print()

    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
