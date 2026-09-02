"""Database engine, connection, and session management."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from personal_job_hunter.core.config import settings
from personal_job_hunter.db.models import Base

# Module-level engine cache
_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_db_engine(db_url: str | None = None, echo: bool | None = None) -> Engine:
    """Create or return cached SQLAlchemy engine."""
    global _engine, _SessionFactory
    url = db_url or settings.sqlalchemy_database_url
    is_debug = echo if echo is not None else settings.debug

    if _engine is None or (db_url is not None and str(_engine.url) != url):
        # Configure connection pool for production robustness
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            url,
            echo=is_debug,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)

    return _engine


def get_session_factory(db_url: str | None = None) -> sessionmaker[Session]:
    """Return configured session factory."""
    global _SessionFactory
    if _SessionFactory is None or db_url is not None:
        get_db_engine(db_url)
    assert _SessionFactory is not None
    return _SessionFactory


@contextmanager
def get_session(db_url: str | None = None) -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic commit and rollback."""
    factory = get_session_factory(db_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables(engine: Engine | None = None) -> None:
    """Create all database tables defined in Base metadata."""
    active_engine = engine or get_db_engine()
    Base.metadata.create_all(bind=active_engine)


def drop_tables(engine: Engine | None = None) -> None:
    """Drop all database tables defined in Base metadata."""
    active_engine = engine or get_db_engine()
    Base.metadata.drop_all(bind=active_engine)
