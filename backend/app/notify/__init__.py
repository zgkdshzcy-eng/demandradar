"""D15 outbound automation: newsletter, X, ProductHunt queue.

Each submodule is a thin orchestrator on top of `core.notify.send_email`
(SMTP) or a vendor REST API (X). All side-effects are guarded by feature
flags + credentials so the system runs locally with everything turned off.
"""
from app.notify import newsletter, producthunt, twitter  # noqa: F401

__all__ = ["newsletter", "producthunt", "twitter"]
