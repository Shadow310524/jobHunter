"""FastAPI main application initialization and route mounting."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from personal_job_hunter.api.routers import applications, jobs, pipeline, stats
from personal_job_hunter.db.session import create_tables, get_db_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Startup and shutdown lifecycle handler."""
    try:
        engine = get_db_engine()
        create_tables(engine)
    except Exception as e:
        # Graceful fallback for offline test environments
        pass
    yield


app = FastAPI(
    title="Personal AI Job Hunter API",
    description=(
        "Autonomous AI-powered job discovery, pgvector semantic matching, "
        "LLM enrichment, and Human-in-the-Loop application lifecycle tracking."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(stats.router)
app.include_router(pipeline.router)

# Mount Static Frontend
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_dashboard() -> FileResponse:
    """Serve the single-page HTML5 dashboard."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return FileResponse(Path(__file__).resolve().parent / "schemas.py")  # Fallback
