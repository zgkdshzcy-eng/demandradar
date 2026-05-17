"""Test fixtures: in-memory SQLite for fast unit tests (no Postgres required).

Note: pgvector columns degrade to NULL on SQLite (we don't test the analyzer
in this suite). For analyzer/clustering integration tests, use the docker-compose
Postgres (Day 5+).
"""
from __future__ import annotations

import os

# Set BEFORE importing app modules so Settings picks it up.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

# Make pgvector's Vector type compilable on SQLite (degrades to BLOB).
@compiles(Vector, "sqlite")
def _compile_vector_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return "BLOB"


from app.db import session as db_session  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    """Replace the global engine/SessionLocal with a SQLite in-memory one,
    then create all tables. StaticPool keeps a single shared connection so
    in-memory tables are visible across sessions.
    """
    from sqlalchemy.pool import StaticPool

    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # Rebind the *existing* sessionmaker in-place. This is the critical bit:
    # callers that did `from app.db.session import SessionLocal` at import
    # time hold a reference to this very factory object, so reconfiguring it
    # transparently redirects all of them to the test engine.
    db_session.engine = test_engine
    db_session.SessionLocal.configure(bind=test_engine)

    # Import models so they register on Base.metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def _truncate_between_modules():
    """Wipe all rows at the start of each test module so files don't bleed
    state into each other. Tests within a single module still share state
    (which several existing tests rely on)."""
    with db_session.engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(tbl.delete())
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
