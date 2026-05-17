"""GitHub auto-sync of high-score briefs to a public repo.

Why: open-source the *evidence* (not the prompts). Each high-score brief is
mirrored to a public repo as `briefs/{id}-{slug}.md` so that
- Search engines and GitHub trending pick up the title/keywords,
- People who link from r/SaaS or HN can read without a login,
- Contributors can open issues / PRs against the brief format itself.

We **do not** push the proprietary scoring prompts. Only the rendered brief
markdown plus a footer linking back to the live `/briefs/{id}` page.

Configuration:
- `GITHUB_SYNC_ENABLED=true` to turn on.
- `GITHUB_SYNC_TOKEN`: a fine-grained PAT with contents:write scope on the
  target repo only.
- `GITHUB_SYNC_REPO`: `owner/repo`, e.g. `demandradar/briefs`.
- `GITHUB_SYNC_BRANCH`: defaults to `main`.
- `GITHUB_SYNC_MIN_SCORE`: only briefs whose painpoint scored >= this go
  public. Defaults to 80.

The endpoint we hit is `PUT /repos/{owner}/{repo}/contents/{path}` which is
idempotent: passing the existing `sha` updates instead of recreates.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.brief import Brief
from app.models.pain_point import PainPoint

GH_API = "https://api.github.com"


@dataclass
class SyncStats:
    pushed: int = 0
    skipped: int = 0
    failed: int = 0


def _slug(text: str, max_len: int = 60) -> str:
    """Filesystem-safe slug. Falls back to 'brief' if input is empty."""
    s = re.sub(r"[^\w\u4e00-\u9fff\- ]", "", text or "", flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s.strip()).lower()
    s = s[:max_len].strip("-")
    return s or "brief"


def _render_markdown(brief: Brief, pp: PainPoint | None) -> str:
    base = (settings.public_base_url or "https://demandradar.example.com").rstrip("/")
    parts: list[str] = []
    parts.append(f"# {brief.title}\n")
    if pp:
        if pp.pain:
            parts.append(f"> **Pain**: {pp.pain}")
        if pp.target_user:
            parts.append(f"> **Target user**: {pp.target_user}")
        if pp.total_score is not None:
            parts.append(f"> **Score**: {pp.total_score:.0f} / 100")
        parts.append("")
    parts.append(brief.markdown or brief.preview or "")
    parts.append("")
    parts.append("---")
    parts.append(
        f"This brief is auto-published from [DemandRadar]({base}). "
        f"Read the live, lockable version with evidence chain at "
        f"[{base}/briefs/{brief.id}]({base}/briefs/{brief.id})."
    )
    return "\n".join(parts) + "\n"


def _gh_get_sha(
    client: httpx.Client, repo: str, path: str, branch: str
) -> str | None:
    r = client.get(
        f"{GH_API}/repos/{repo}/contents/{path}",
        params={"ref": branch},
    )
    if r.status_code == 404:
        return None
    if r.status_code >= 300:
        raise RuntimeError(f"GitHub GET failed: HTTP {r.status_code} {r.text[:200]}")
    return r.json().get("sha")


def _gh_put(
    client: httpx.Client,
    repo: str,
    path: str,
    branch: str,
    content_b64: str,
    message: str,
    sha: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message": message,
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    r = client.put(f"{GH_API}/repos/{repo}/contents/{path}", json=payload)
    if r.status_code >= 300:
        raise RuntimeError(f"GitHub PUT failed: HTTP {r.status_code} {r.text[:200]}")
    return r.json()


def push_brief(db: Session, brief: Brief) -> bool:
    """Push (or update) a single brief to the configured public repo.

    Returns True on success, False on skip/disabled. Raises on hard failures
    so the caller can attribute the error in metrics.
    """
    if not settings.github_sync_enabled:
        return False
    if not settings.github_sync_token or not settings.github_sync_repo:
        logger.warning("github_sync: enabled but token/repo missing")
        return False

    pp = db.get(PainPoint, brief.pain_point_id) if brief.pain_point_id else None
    min_score = float(settings.github_sync_min_score)
    if pp is None or pp.total_score is None or pp.total_score < min_score:
        return False

    body = _render_markdown(brief, pp)
    path = f"briefs/{brief.id:04d}-{_slug(brief.title or pp.pain or 'brief')}.md"
    branch = settings.github_sync_branch or "main"
    headers = {
        "Authorization": f"Bearer {settings.github_sync_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "demandradar-sync/0.1",
    }

    with httpx.Client(timeout=20.0, headers=headers) as client:
        sha = _gh_get_sha(client, settings.github_sync_repo, path, branch)
        message = (
            f"chore(brief): {'update' if sha else 'add'} #{brief.id} "
            f"{(brief.title or '')[:60]}"
        )
        _gh_put(
            client,
            settings.github_sync_repo,
            path,
            branch,
            base64.b64encode(body.encode("utf-8")).decode("ascii"),
            message,
            sha,
        )
    return True


def sync_recent(db: Session, *, limit: int = 5) -> SyncStats:
    """Walk the most-recent briefs and push any whose painpoint clears the
    threshold. Idempotent — GitHub will be a no-op when content is unchanged."""
    stats = SyncStats()
    if not settings.github_sync_enabled:
        return stats

    rows: list[Brief] = list(
        db.execute(
            select(Brief).order_by(desc(Brief.created_at)).limit(limit)
        ).scalars()
    )
    for brief in rows:
        try:
            ok = push_brief(db, brief)
            if ok:
                stats.pushed += 1
            else:
                stats.skipped += 1
        except Exception as exc:  # noqa: BLE001
            stats.failed += 1
            logger.warning("github_sync: brief #{} failed: {}", brief.id, exc)
    return stats


__all__ = ["SyncStats", "push_brief", "sync_recent"]
