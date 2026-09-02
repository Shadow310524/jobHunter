"""Interactive CLI Review Inbox and Application Lifecycle Dashboard."""

from typing import Any

from personal_job_hunter.db.repository import ApplicationRepository
from personal_job_hunter.db.session import create_tables, get_db_engine, get_session
from personal_job_hunter.domain.models import ApplicationStatus
from personal_job_hunter.tracking.manager import ApplicationTracker


def print_status_summary(db_url: str | None = None) -> None:
    """Print high-level dashboard of application states."""
    engine = get_db_engine(db_url)
    create_tables(engine)

    with get_session(db_url) as session:
        stats = ApplicationRepository.get_application_stats(session)

    p_rev = stats.get(ApplicationStatus.PENDING_HUMAN_REVIEW.value, 0)
    p_ready = stats.get(ApplicationStatus.READY_TO_APPLY.value, 0)
    p_app = stats.get(ApplicationStatus.APPLIED.value, 0)
    p_int = stats.get(ApplicationStatus.INTERVIEWING.value, 0)
    p_off = stats.get(ApplicationStatus.OFFER.value, 0)
    p_rej_h = stats.get(ApplicationStatus.REJECTED_BY_HUMAN.value, 0)
    p_rej_c = stats.get(ApplicationStatus.REJECTED_BY_COMPANY.value, 0)

    print("\n" + "=" * 65)
    print("      PERSONAL AI JOB HUNTER -- HITL APPLICATION DASHBOARD")
    print("=" * 65)
    print(f"  [PENDING REVIEW]   {p_rev:3d}  (Needs your decision)")
    print(f"  [READY TO APPLY]   {p_ready:3d}  (Approved by you)")
    print(f"  [APPLIED]          {p_app:3d}  (Submitted)")
    print(f"  [INTERVIEWING]     {p_int:3d}  (Active rounds)")
    print(f"  [OFFER]            {p_off:3d}  (Offers received)")
    print(f"  [REJECTED - HUMAN] {p_rej_h:3d}  (Skipped by you)")
    print(f"  [REJECTED - CO]    {p_rej_c:3d}  (Closed)")
    print("=" * 65 + "\n")


def review_inbox_cli(db_url: str | None = None, auto_approve_all: bool = False) -> None:
    """Interactive review inbox for human-in-the-loop application approval."""
    engine = get_db_engine(db_url)
    create_tables(engine)

    with get_session(db_url) as session:
        inbox = ApplicationRepository.get_review_inbox(session, limit=20)

        if not inbox:
            print("\n[OK] Review inbox is clear! No jobs pending decision.\n")
            return

        print(f"\nFound {len(inbox)} jobs awaiting your review.\n")

        for idx, (_app, job, score, enrichment_model) in enumerate(inbox, start=1):
            enr: dict[str, Any] = enrichment_model.enrichment_data if enrichment_model else {}
            score_val = f"{score.overall_score:.1f}" if score else "N/A"
            rec_val = score.recommendation if score else "UNKNOWN"
            det_val = (
                f"{score.deterministic_score:.1f}"
                if score and score.deterministic_score is not None
                else "N/A"
            )
            sem_val = (
                f"{score.semantic_score:.1f}"
                if score and score.semantic_score is not None
                else "N/A"
            )

            print("-" * 75)
            header = f"[{rec_val}] [{score_val}/100] {job.title} @ {job.company}"
            print(f"JOB {idx}/{len(inbox)}: {header[:65]}")
            loc_mode = f"{job.location} (Remote: {job.is_remote}, Mode: {job.work_mode})"
            print(f"Location:       {loc_mode[:60]}")
            print(f"Score Details:  Combined={score_val} | Det={det_val} | Sem={sem_val}")
            print(f"Official URL:   {job.application_urls[0] if job.application_urls else 'N/A'}")
            print("-" * 75)

            if enr:
                print(f"Summary:        {enr.get('job_summary', 'N/A')}")
                print(f"Tech Focus:     {', '.join(enr.get('inferred_technical_focus', [])[:4])}")
                print(f"Strengths:      {', '.join(enr.get('candidate_strengths', [])[:2])}")
                if enr.get("gap_analysis"):
                    print(f"Gaps/Stretch:   {', '.join(enr.get('gap_analysis', [])[:2])}")
                if enr.get("interview_talking_points"):
                    print(f"AVASOFT Point:  {enr.get('interview_talking_points', [])[0]}")
            print("-" * 75)

            if auto_approve_all:
                print("[Auto-Approve Mode] Marking as READY_TO_APPLY.")
                ApplicationTracker.approve_for_apply(session, job.canonical_id)
                session.commit()
                continue

            # Interactive Prompt
            prompt = (
                "Action: [A]pprove (Ready to Apply) | [R]eject (Close) | [S]kip / Next | [Q]uit > "
            )
            choice = input(prompt).strip().lower()

            if choice in ["a", "approve", "y", "yes"]:
                ApplicationTracker.approve_for_apply(session, job.canonical_id)
                session.commit()
                print(" -> [APPROVED] Moved to READY_TO_APPLY.\n")
            elif choice in ["r", "reject", "n", "no"]:
                reason = input("Optional rejection reason > ").strip()
                ApplicationTracker.reject_by_human(session, job.canonical_id, reason=reason)
                session.commit()
                print(" -> [REJECTED] Moved to REJECTED_BY_HUMAN.\n")
            elif choice in ["q", "quit", "exit"]:
                print("\nExiting review inbox.\n")
                break
            else:
                print(" -> [SKIPPED] Skipped for now.\n")


def list_applications_by_status_cli(status_str: str, db_url: str | None = None) -> None:
    """List jobs currently in a specified status."""
    engine = get_db_engine(db_url)
    create_tables(engine)

    with get_session(db_url) as session:
        records = ApplicationRepository.get_applications_by_status(
            session=session, status=status_str.upper(), limit=50
        )

        print(f"\nApplications with status: [{status_str.upper()}] ({len(records)} found)")
        print("=" * 75)
        for i, (app, job, score) in enumerate(records, start=1):
            score_str = f"[{score.overall_score:.1f}/100]" if score else "[N/A]"
            print(f"{i:2d}. {score_str} {job.title} @ {job.company} ({job.location})")
            print(f"    Canonical ID: {job.canonical_id}")
            print(f"    Apply URL:    {job.application_urls[0] if job.application_urls else 'N/A'}")
            if app.notes:
                print(f"    Notes:        {app.notes}")
            print()
        print("=" * 75 + "\n")
