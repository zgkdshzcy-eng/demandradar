"""Observability primitives: Sentry, Prometheus metrics, request middleware.

All initialisation is no-op when the relevant env vars are unset, so dev
machines without any external service still work normally.
"""
from __future__ import annotations

import time
import uuid
from typing import Awaitable, Callable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import logger

# ---------------- Prometheus ----------------
# Use a dedicated registry so multiple imports under tests don't double-register.
REGISTRY = CollectorRegistry()

HTTP_REQUESTS_TOTAL = Counter(
    "demandradar_http_requests_total",
    "HTTP requests by method, path template and status code",
    ["method", "path", "status"],
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION = Histogram(
    "demandradar_http_request_duration_seconds",
    "Request latency in seconds",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)
HTTP_IN_FLIGHT = Gauge(
    "demandradar_http_in_flight",
    "In-flight HTTP requests",
    registry=REGISTRY,
)
JOB_RUNS_TOTAL = Counter(
    "demandradar_job_runs_total",
    "Background job invocations grouped by name and outcome",
    ["job", "outcome"],
    registry=REGISTRY,
)
JOB_DURATION = Histogram(
    "demandradar_job_duration_seconds",
    "Background job duration",
    ["job"],
    buckets=(0.5, 1, 5, 10, 30, 60, 300, 600, 1800),
    registry=REGISTRY,
)


def metrics_response() -> Response:
    """Render the current registry as Prometheus text exposition."""
    if not settings.metrics_enabled:
        return Response(status_code=404)
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


def record_job(job: str, outcome: str, duration_seconds: float) -> None:
    """Helper for scheduler hooks."""
    JOB_RUNS_TOTAL.labels(job=job, outcome=outcome).inc()
    JOB_DURATION.labels(job=job).observe(duration_seconds)


# ---------------- Sentry ----------------

_sentry_initialised = False


def init_sentry() -> bool:
    """Initialise Sentry. Returns True iff actually initialised."""
    global _sentry_initialised
    if _sentry_initialised or not settings.sentry_dsn:
        return _sentry_initialised
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            release=None,  # populated by CI via SENTRY_RELEASE env if needed
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
            ],
        )
        _sentry_initialised = True
        logger.info(
            "sentry initialised env={} traces={}",
            settings.app_env,
            settings.sentry_traces_sample_rate,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("sentry init failed: {}", exc)
    return _sentry_initialised


# ---------------- Middleware ----------------

REQUEST_ID_HEADER = "X-Request-ID"


def _route_template(request: Request) -> str:
    """Use the matched route's path template (e.g. /api/briefs/{brief_id})
    so high-cardinality ids don't blow up Prometheus labels.
    Falls back to the raw URL path when no route matched (404).
    """
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign each request a stable request_id, expose it in:
    - response header `X-Request-ID`
    - the contextual loguru logger (so every log line within the request carries it)
    - one structured access log line at completion
    - Prometheus counters / histograms

    Honours an inbound `X-Request-ID` header if the upstream proxy sets one
    (Caddy / Nginx / Traefik conventions).
    """

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
        method = request.method
        path = request.url.path

        bound = logger.bind(
            request_id=rid,
            method=method,
            path=path,
            ip=(request.client.host if request.client else "-"),
        )

        HTTP_IN_FLIGHT.inc()
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception:
            bound.exception("request crashed")
            raise
        finally:
            elapsed = time.perf_counter() - started
            HTTP_IN_FLIGHT.dec()
            tmpl = _route_template(request)
            HTTP_REQUEST_DURATION.labels(method=method, path=tmpl).observe(elapsed)
            HTTP_REQUESTS_TOTAL.labels(
                method=method, path=tmpl, status=str(status)
            ).inc()
            bound.bind(
                status=status, latency_ms=round(elapsed * 1000, 2), route=tmpl
            ).info("http")

            # Inject the header on the outgoing response, even on errors.
            try:
                response  # noqa: B018
                response.headers[REQUEST_ID_HEADER] = rid
            except UnboundLocalError:
                pass


__all__ = [
    "REGISTRY",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION",
    "JOB_RUNS_TOTAL",
    "JOB_DURATION",
    "RequestContextMiddleware",
    "init_sentry",
    "metrics_response",
    "record_job",
]
