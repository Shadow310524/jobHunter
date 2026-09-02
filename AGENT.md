# PERSONAL AI JOB HUNTER — AGENT INSTRUCTIONS

Repository: `jobHunter`
Remote: `https://github.com/Shadow310524/jobHunter`

## Target Profile
* **Target Candidate**: 2026 B.Tech graduate in AI & ML (8.2 CGPA).
* **Internship**: AI Platform Engineer at AVASOFT (Dec 2025 – Apr 2026).
* **Core Target Roles**: AI Engineer, GenAI Engineer, LLM Engineer, Agentic AI Engineer, Python Backend Developer, Software Engineer.
* **Target Locations**: Bangalore / Bengaluru, Remote (India).
* **Experience Range**: Fresher / 2026 graduate / 0–2 years (1–2 year roles classified as STRETCH).

## Core Flow
```
Job Sources -> API / HTTP / Playwright -> Job Collector -> Normalization & Deduplication 
-> Database (PostgreSQL) -> Resume/JD Semantic Matcher -> AI Ranking (APPLY / STRETCH / SKIP) 
-> Human Approval -> Application Tracker -> Dashboard / Notifications
```

## Engineering Rules
1. **Deterministic First**: Follow `Deterministic logic -> SQL/filtering -> Algorithms -> Embeddings -> LLM`.
2. **Cost Optimization**: Default $0.00 cost assumption. Local processing, free tiers, and open-source models.
3. **No Unethical Scraping**: Never bypass CAPTCHA, authentication, anti-bot systems, or access controls. Safe stop and report `Human intervention required`.
4. **Safety**: Human in the loop (HITL) — Never auto-submit applications.
5. **Quality**: Modular architecture, typed code, OWASP compliance, and comprehensive unit tests.
