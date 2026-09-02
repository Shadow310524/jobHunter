"""Enrichment Runner: Executes gated LLM enrichment on high-priority target jobs."""

import json
from pathlib import Path
from typing import Any

from personal_job_hunter.domain.models import (
    CandidateProfile,
    CanonicalJobPost,
    JobMatchResult,
)
from personal_job_hunter.llm.base import BaseLLMService
from personal_job_hunter.llm.enricher import JobEnrichmentEngine
from personal_job_hunter.llm.service import get_default_llm_service


def enrich_high_priority_jobs(
    canonical_file: Path | str = Path("data/canonical_jobs.json"),
    ranked_file: Path | str = Path("data/hybrid_ranked_jobs.json"),
    output_file: Path | str = Path("data/enriched_jobs.json"),
    profile: CandidateProfile | None = None,
    llm_service: BaseLLMService | None = None,
) -> dict[str, Any]:
    """Run gated LLM enrichment on high-priority target jobs."""
    canon_path = Path(canonical_file)
    rank_path = Path(ranked_file)

    if not canon_path.exists():
        raise FileNotFoundError(f"Canonical file not found: {canon_path}")
    if not rank_path.exists():
        raise FileNotFoundError(f"Ranked file not found: {rank_path}")

    with open(canon_path, encoding="utf-8") as f:
        canon_data = json.load(f)
    with open(rank_path, encoding="utf-8") as f:
        rank_data = json.load(f)

    jobs_by_id = {j["canonical_id"]: CanonicalJobPost.model_validate(j) for j in canon_data}
    ranked_results = [JobMatchResult.model_validate(r) for r in rank_data]

    active_profile = profile or CandidateProfile()
    engine = JobEnrichmentEngine(llm_service=llm_service or get_default_llm_service())

    enriched_output: list[dict[str, Any]] = []
    gated_count = 0
    skipped_by_gate = 0

    for match_res in ranked_results:
        job = jobs_by_id.get(match_res.canonical_id)
        if not job:
            continue

        if engine.should_enrich(match_res):
            gated_count += 1
            enrichment = engine.enrich_job(
                job=job,
                profile=active_profile,
                match_result=match_res,
            )
            if enrichment:
                enriched_output.append(
                    {
                        "canonical_id": job.canonical_id,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "recommendation": match_res.recommendation,
                        "overall_score": match_res.overall_score,
                        "enrichment": enrichment.model_dump(mode="json"),
                    }
                )
        else:
            skipped_by_gate += 1

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enriched_output, f, indent=2, ensure_ascii=False)

    return {
        "total_jobs": len(ranked_results),
        "gated_for_enrichment": gated_count,
        "skipped_by_gate": skipped_by_gate,
        "successfully_enriched": len(enriched_output),
        "output_file": str(out_path),
        "results": enriched_output,
    }


def main() -> None:
    """CLI runner to execute and print gated LLM job enrichment."""
    print("\nRunning Gated LLM Job Enrichment Pipeline...")
    summary = enrich_high_priority_jobs()

    print("\n" + "=" * 75)
    print("       PERSONAL AI JOB HUNTER — LLM ENRICHMENT REPORT (Phase 8)")
    print("=" * 75)
    print(f"Total Ranked Jobs Evaluated:      {summary['total_jobs']}")
    print(f"Gated For LLM Enrichment:        {summary['gated_for_enrichment']}")
    print(f"Bypassed by Safety/Cost Gate:    {summary['skipped_by_gate']} (0 compute spent)")
    print(f"Successfully Enriched:           {summary['successfully_enriched']}")
    print("-" * 75)

    print("\nSample Enriched Target Jobs:")
    print("-" * 75)
    for i, item in enumerate(summary["results"][:5], start=1):
        enr = item["enrichment"]
        tag = f"[{item['recommendation']}]"
        print(f"{i}. {tag} [{item['overall_score']:.1f}/100] {item['title']} @ {item['company']}")
        print(f"   Summary:       {enr['job_summary']}")
        print(f"   Tech Focus:    {', '.join(enr['inferred_technical_focus'][:4])}")
        print(f"   Strengths:     {', '.join(enr['candidate_strengths'][:2])}")
        if enr["gap_analysis"]:
            print(f"   Gaps/Stretch:  {', '.join(enr['gap_analysis'][:2])}")
        if enr["interview_talking_points"]:
            print(f"   Talking Point: {enr['interview_talking_points'][0]}")
        print()

    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
