"""SQLAlchemy engine, session factory, declarative Base.

Sync engine is sufficient for our scheduler/CRUD workload; async can be added
later for high-concurrency endpoints.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _make_engine(url: str):  # type: ignore[no-untyped-def]
    """Build an engine with sane defaults; pool args only for non-SQLite."""
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if not url.startswith("sqlite"):
        kwargs.update(pool_size=5, max_overflow=10)
    return create_engine(url, **kwargs)


# echo=False; switch on temporarily for debugging.
engine = _make_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping() -> bool:
    """Lightweight DB liveness check."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
