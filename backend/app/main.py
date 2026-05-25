"""FastAPI entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import (
    admin,
    auth,
    billing,
    briefs,
    data_api,
    health,
    industry,
    insights,
    newsletter,
    painpoints,
    public_stats,
    trend_alerts,
    waitlist,
    weekly,
)
from app.core import scheduler as scheduler_mod
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.observability import RequestContextMiddleware, init_sentry


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    setup_logging()
    init_sentry()
    logger.info(
        "DemandRadar starting | env={} version={} log_format={}",
        settings.app_env,
        __version__,
        settings.log_format,
    )
    scheduler_mod.start()
    yield
    scheduler_mod.shutdown()
    logger.info("DemandRadar shutting down")


app = FastAPI(
    title="DemandRadar API",
    description="自动化需求挖掘与项目书生成系统",
    version=__version__,
    lifespan=lifespan,
)

_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_origins = (
    [o.strip() for o in settings.public_base_url.split(",") if o.strip()]
    + _default_origins
    if settings.public_base_url
    else _default_origins
)

# Order matters: outermost first. RequestContext wraps the entire stack so it
# also tracks CORS preflight responses.
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.include_router(health.router)
app.include_router(waitlist.router)
app.include_router(painpoints.router)
app.include_router(briefs.router)
app.include_router(weekly.router)
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(admin.router)
app.include_router(newsletter.router)
app.include_router(insights.router)
app.include_router(public_stats.router)
app.include_router(trend_alerts.router)
app.include_router(industry.router)
app.include_router(data_api.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "DemandRadar",
        "version": __version__,
        "docs": "/docs",
    }
