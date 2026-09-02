"""FastAPI dependency injection utilities."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from personal_job_hunter.db.session import get_session


def get_db() -> Generator[Session, None, None]:
    """Dependency yielding managed SQLAlchemy Session with automatic cleanup."""
    with get_session() as session:
        yield session
