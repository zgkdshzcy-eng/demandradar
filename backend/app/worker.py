"""Standalone worker entrypoint.

Runs the APScheduler loop in its own process so that:
- the API container can run multiple uvicorn replicas without each replica
  triggering duplicate background jobs.
- the worker can be scaled / restarted independently.

Usage:
    python -m app.worker

The API container should set `APP_SCHEDULER_DISABLED=1` so its lifespan
hook is a no-op.
"""
from __future__ import annotations

import asyncio
import os
import signal

from app import __version__
from app.core import scheduler as scheduler_mod
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.observability import init_sentry


async def _main() -> None:
    setup_logging()
    init_sentry()
    # Workers always run the scheduler regardless of the legacy disable flag.
    os.environ.pop("APP_SCHEDULER_DISABLED", None)
    logger.info(
        "DemandRadar worker starting | env={} version={}",
        settings.app_env,
        __version__,
    )
    scheduler_mod.start()

    stop = asyncio.Event()

    def _signal(*_: object) -> None:
        logger.info("worker: signal received, shutting down")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler in selector loops.
            signal.signal(sig, lambda *_: _signal())

    try:
        await stop.wait()
    finally:
        scheduler_mod.shutdown()
        logger.info("worker stopped")


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
