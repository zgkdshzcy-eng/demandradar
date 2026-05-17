"""Dev server bootstrap: SQLite-friendly (patches pgvector for SQLite) and runs uvicorn."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./dr.db")

# Patch pgvector to compile to BLOB on SQLite (dev only).
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.compiler import compiles


@compiles(Vector, "sqlite")
def _compile_vector_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return "BLOB"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["dr.db", "*.db-journal"],
    )
