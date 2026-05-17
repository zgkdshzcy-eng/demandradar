# syntax=docker/dockerfile:1.7

# ---------- builder: compile any wheels we may need ----------
FROM python:3.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Build deps for psycopg, scikit-learn, numpy etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Resolve every dep + our own package into /wheels.
RUN pip install --upgrade pip wheel \
    && pip wheel --wheel-dir /wheels .


# ---------- runtime ----------
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    LOG_FORMAT=json

# libpq for psycopg, curl for the HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home app

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels demandradar-backend \
    && rm -rf /wheels

# alembic.ini & migrations live next to the app; ship them so `alembic upgrade head`
# can run on container start. The egg-info inside the wheel already contains app/.
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${APP_PORT}/healthz || exit 1

# Default command runs the API; the worker container overrides this with
# `python -m app.worker`.
CMD ["sh", "-c", "uvicorn app.main:app --host ${APP_HOST} --port ${APP_PORT} --proxy-headers --forwarded-allow-ips=*"]
