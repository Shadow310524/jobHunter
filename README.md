# Personal AI Job Hunter

[![Tests](https://img.shields.io/badge/pytest-86%20passed-brightgreen.svg)](https://github.com/Shadow310524/jobHunter)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-black.svg)](https://github.com/astral-sh/ruff)
[![Type Checked](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://github.com/python/mypy)
[![Cost](https://img.shields.io/badge/cost-$0.00%20default-green.svg)]()

An autonomous, cost-efficient, personal job-hunting and application intelligence platform. Designed specifically for targeted **AI Engineer, GenAI Engineer, LLM Engineer, Agentic AI, and Backend** roles.

Built on **Deterministic First** engineering: `Deterministic logic -> SQL/filtering -> Algorithms -> Local pgvector Embeddings -> LLM Enrichment -> Human-in-the-Loop Review`.

---

## 🏗️ End-to-End System Architecture

```mermaid
flowchart TD
    subgraph S1["1. Multi-ATS Ingestion"]
        G[Greenhouse API] --> N[Unified Normalization]
        A[Ashby API] --> N
        L[Lever API] --> N
    end

    subgraph S2["2. Canonical Deduplication"]
        N --> D[Multi-Tier Deduplication Engine]
        D --> P[(PostgreSQL 16 + pgvector)]
    end

    subgraph S3["3. Hybrid Matching & Ranking"]
        P --> M1[Phase 5B Calibrated Deterministic Matcher]
        M1 --> M2[FastEmbed BAAI/bge-small-en-v1.5 ONNX]
        M2 --> M3[pgvector Cosine Similarity Retrieval]
        M3 --> HR["Hybrid Blended Score (70% Det + 30% Sem)"]
    end

    subgraph S4["4. Gated LLM Enrichment"]
        HR --> Gating{"Gating Check: APPLY / Top STRETCH?"}
        Gating -- "SKIP / Low Stretch" --> Free["Bypass LLM ($0.00 Spent)"]
        Gating -- "Target Opportunities" --> LLM["LLM Enrichment: Ground Truth vs Inferences"]
        LLM --> Hash["SHA-256 Idempotency Cache"]
    end

    subgraph S5["5. Human-in-the-Loop Review & Actions"]
        HR --> Queue["Review Inbox: PENDING_HUMAN_REVIEW"]
        LLM --> Queue
        Queue --> Review{"Human Decision"}
        Review -- "[APPROVE]" --> Ready["READY_TO_APPLY"]
        Review -- "[REJECT]" --> Closed["REJECTED_BY_HUMAN"]
        Ready --> ManualSubmit["Candidate Manually Submits on Portal"]
        ManualSubmit --> Applied["APPLIED"]
        Applied --> Interview["INTERVIEWING"]
        Interview --> Offer["OFFER / REJECTED"]
    end

    subgraph S6["6. Productization & Dashboard"]
        Queue --> API["FastAPI REST Endpoints (/api/jobs, /api/applications)"]
        API --> UI["Glassmorphism Web Dashboard (HTML5 / Vanilla CSS / ES6)"]
        API --> Alert["Console / File Audit Notifications"]
    end
```

---

## ⚡ Key Highlights & Core Principles

1. **Deterministic Safety Gates**: Hard disqualifiers (e.g. Sales, Technical Support, 5+ yrs Senior roles, Foreign On-site) are evaluated deterministically and strictly remain `SKIP`. Semantic similarity and LLMs **never** override eligibility.
2. **$0.00 Default Cost Assumption**:
   - Embeddings run **100% locally on CPU** using FastEmbed ONNX runtime (`BAAI/bge-small-en-v1.5`, 384 dimensions).
   - LLMs run on Google Gemini free tier or 100% offline via Ollama / Mock.
   - Gated enrichment processes only high-priority targets ($\sim 15\%$ of total corpus).
3. **Strict Human-in-the-Loop (HITL) Safety**:
   - Automatic application submission is strictly prohibited.
   - The state machine blocks skipping approval directly to `APPLIED`.
   - Immutable event logs record every human decision and portal submission timestamp.
4. **Multi-Tier Identity & Deduplication**:
   - Tier 1: Canonical URL stripping tracking parameters.
   - Tier 2: Source + Source Job ID.
   - Tier 3: Conservative cross-source cluster grouping.

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
- **Python 3.11+** or **3.12+**
- **uv** (recommended for ultra-fast package management): `curl -LsSf https://astral.sh/uv/install.ps1 | iex`
- **PostgreSQL 16+** with `pgvector` extension (or local test SQLite)

### 2. Clone & Setup
```bash
git clone https://github.com/Shadow310524/jobHunter.git
cd Personal-AI-Job-Hunter

# Sync virtualenv and dependencies
uv sync --all-extras
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` as needed:
```ini
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/jobhunter
GEMINI_API_KEY=your_gemini_api_key_here  # Optional: for live LLM enrichment
LOG_LEVEL=INFO
```

### 4. Run Database Migrations
```bash
uv run alembic upgrade head
```

---

## 🛠️ Usage & Commands

### 1. Run the Complete Unified Pipeline
Executes Multi-ATS collection $\rightarrow$ Deduplication $\rightarrow$ DB persistence $\rightarrow$ Hybrid matching $\rightarrow$ Gated LLM enrichment $\rightarrow$ HITL queue sync $\rightarrow$ Notifications:
```bash
uv run python -m personal_job_hunter.unified_pipeline
```

### 2. Start the FastAPI Server & Interactive Dashboard
```bash
uv run uvicorn personal_job_hunter.api.app:app --host 0.0.0.0 --port 8000 --reload
```
- 🌐 **Interactive Web Dashboard**: [http://localhost:8000](http://localhost:8000)
- 📖 **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Review Applications via Interactive CLI
```bash
# Review pending high-priority jobs in terminal
uv run python -c "from personal_job_hunter.tracking.cli import review_inbox_cli; review_inbox_cli()"

# View application status summary dashboard
uv run python -c "from personal_job_hunter.tracking.cli import print_status_summary; print_status_summary()"
```

---

## 🧪 Testing & Code Quality

Run the complete test suite across all 86 unit tests:
```bash
uv run pytest
```

Run static type checking and linting:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

---

## 📊 Application Lifecycle States

| State | Description | Transition Trigger |
| :--- | :--- | :--- |
| `DISCOVERED` | Raw job ingested from ATS feed. | Pipeline Ingestion |
| `PENDING_HUMAN_REVIEW` | Matched, ranked, and LLM-enriched. Awaiting decision. | Pipeline Hybrid Evaluator |
| `READY_TO_APPLY` | Candidate reviewed and approved. Official link generated. | **Human Action**: `[Approve]` |
| `REJECTED_BY_HUMAN` | Candidate rejected or skipped. Requisition closed. | **Human Action**: `[Reject]` |
| `APPLIED` | Candidate manually submitted application on employer portal. | **Human Action**: `[Mark Applied]` |
| `INTERVIEWING` | Screening, technical round, or manager interview scheduled. | **Human Action**: `[Schedule Interview]` |
| `OFFER` | Job offer letter received! | **Human Action**: `[Got Offer]` |
| `REJECTED_BY_COMPANY`| Employer sent rejection or closed requisition. | **Human Action** / Follow-up |

---

## 🛡️ Privacy & Safety Statement

This application strictly complies with OWASP best practices and ethical automation rules:
- No browser session hijacking, anti-bot evasion, or CAPTCHA bypass.
- Never sends credentials, API keys, or personal cookies over external networks.
- Candidate embeddings exclude sensitive identifiers and focus strictly on engineering competencies.
- **Zero auto-submitting**: Every application requires human confirmation.
