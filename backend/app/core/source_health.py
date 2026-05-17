"""In-memory adaptive throttling for collectors.

When a source fails repeatedly (rate limit, IP block, stale credentials),
running it on the original interval just burns API quota and floods the
logs. This module exposes a tiny state machine the scheduler consults
before each collector run to compute a *current* run interval.

Resets to the baseline on the first successful run.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

# Backoff config:
# - First FAIL_THRESHOLD failures keep the baseline interval (transient
#   blips are common).
# - Each subsequent consecutive failure doubles the interval, capped at
#   MAX_INTERVAL_MULT × baseline.
FAIL_THRESHOLD = 3
MAX_INTERVAL_MULT = 8


@dataclass
class SourceState:
    consecutive_failures: int = 0
    interval_mult: int = 1
    run_count: int = 0
    last_error: str | None = None


_STATE: dict[str, SourceState] = {}
_LOCK = Lock()


def should_run(name: str) -> bool:
    """Return True if this scheduler tick should actually execute the collector.

    When `interval_mult > 1` we only run on every `interval_mult`-th tick to
    achieve the adaptive backoff without rescheduling APScheduler triggers.
    Always increments the internal run counter; idempotent on the state.
    """
    with _LOCK:
        st = _STATE.setdefault(name, SourceState())
        st.run_count += 1
        if st.interval_mult <= 1:
            return True
        return st.run_count % st.interval_mult == 0


def record_outcome(name: str, ok: bool, *, error: str | None = None) -> SourceState:
    """Update state after a collector run. Returns the new state for logging."""
    with _LOCK:
        st = _STATE.setdefault(name, SourceState())
        if ok:
            st.consecutive_failures = 0
            st.interval_mult = 1
            st.last_error = None
            return SourceState(**st.__dict__)
        st.consecutive_failures += 1
        st.last_error = (error or "")[:200] or None
        if st.consecutive_failures > FAIL_THRESHOLD:
            st.interval_mult = min(st.interval_mult * 2 or 2, MAX_INTERVAL_MULT)
        return SourceState(**st.__dict__)


def current_interval(name: str, baseline_minutes: int) -> int:
    """Current run interval for `name`, in minutes."""
    with _LOCK:
        st = _STATE.get(name)
    mult = st.interval_mult if st is not None else 1
    return baseline_minutes * mult


def snapshot() -> dict[str, dict[str, object]]:
    """Read-only state for /admin or tests."""
    with _LOCK:
        return {
            name: {
                "consecutive_failures": st.consecutive_failures,
                "interval_mult": st.interval_mult,
                "last_error": st.last_error,
            }
            for name, st in _STATE.items()
        }


def reset(name: str | None = None) -> None:
    with _LOCK:
        if name is None:
            _STATE.clear()
            return
        _STATE.pop(name, None)


__all__ = [
    "FAIL_THRESHOLD",
    "MAX_INTERVAL_MULT",
    "SourceState",
    "current_interval",
    "record_outcome",
    "reset",
    "should_run",
    "snapshot",
]
