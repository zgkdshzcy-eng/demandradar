"""Health & meta endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app import __version__
from app.core.config import settings
from app.core.llm import usage as llm_usage
from app.core.observability import metrics_response
from app.db.session import ping as db_ping

router = APIRouter(tags=["meta"])


def _redis_ping() -> bool:
    """Best-effort Redis health check. Returns False on any failure."""
    if not settings.redis_url:
        return False
    try:
        import redis  # local import to avoid hard dep at module load time

        client = redis.Redis.from_url(settings.redis_url, socket_timeout=1.5)
        return bool(client.ping())
    except Exception:  # noqa: BLE001
        return False


@router.get("/healthz")
async def healthz() -> Response:
    """Liveness probe.

    - 200 when the API process is up AND the DB is reachable.
    - 503 when the DB is unreachable (so orchestrators can restart us).
    - Redis check is best-effort and never fails the response.
    """
    db_ok = db_ping()
    body: dict[str, object] = {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "env": settings.app_env,
        "db": "ok" if db_ok else "down",
        "redis": "ok" if _redis_ping() else "down",
    }
    return JSONResponse(body, status_code=200 if db_ok else 503)


@router.get("/readyz")
async def readyz() -> Response:
    """Readiness probe — only ready once DB is reachable."""
    return JSONResponse(
        {"ready": db_ping()},
        status_code=200 if db_ping() else 503,
    )


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus exposition. Disabled when METRICS_ENABLED=false."""
    return metrics_response()


@router.get("/llm/usage")
async def llm_usage_endpoint() -> dict[str, object]:
    """Today's LLM token consumption & cost. Useful for dashboarding."""
    return {
        "total_tokens": llm_usage.total_tokens,
        "total_cost_cny": round(llm_usage.total_cost_cny, 4),
        "by_model": llm_usage.by_model,
        "daily_budget_cny": settings.llm_daily_budget_cny,
    }
