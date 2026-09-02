# PERSONAL AI JOB HUNTER — MASTER ENGINEERING RULES

## 1. Development Principles
* **KISS & YAGNI**: Solve the problem simply. Do not build hypothetical abstractions or microservices.
* **Separation of Concerns**: Scrapers collect, normalizers clean, matchers score, repositories persist.
* **Strict Typing & Contracts**: All functions and models must use explicit type annotations and Pydantic validation where appropriate.
* **Step-by-Step Evolution**: Build one component at a time with test coverage before advancing to subsequent phases.

## 2. Technology Decision Hierarchy
```
Deterministic Logic
  ↓
SQL / Filtering
  ↓
Traditional Algorithms
  ↓
Embeddings (Vector Similarity)
  ↓
LLM (Structured Extraction & High-Value Reasoning Only)
```

## 3. Cost & Resource Optimization
* Default budget is **$0.00**.
* Leverage free tier / local embeddings and open-source models first.
* Justify any paid external API before introducing it.

## 4. Security & Safety (OWASP)
* Never commit secrets, tokens, cookies, or API keys (`.env` must be in `.gitignore`).
* Load configuration through type-safe settings (`core.config.Settings`).
* Human In The Loop (HITL): The system prepares and analyzes applications, but final submission always requires human approval.
* Ethical Automation: Respect `robots.txt`, implement rate limits, and stop gracefully if restricted.
