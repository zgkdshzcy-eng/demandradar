"""X (Twitter) auto-poster.

Strategy:
- After each weekly report we generate one tweet for the #1 painpoint and
  enqueue it as a `social_posts(platform='x', kind='weekly')` row.
- A separate `post_pending` worker drains the queue, calling X API v2's
  `POST /2/tweets` with the configured user access token. We **never** post
  inline during webhook processing.

The composer is intentionally LLM-free: it pulls the painpoint title, total
score and a short evidence snippet, then truncates to 280 chars including a
shortened link to the latest sample.

Both sides degrade gracefully:
- TWITTER_ENABLED=false → enqueue rows with `status='manual'` so the admin can
  copy/paste them
- HTTP errors → `status='failed'` + error captured for retry
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.pain_point import PainPoint
from app.models.social_post import SocialPost
from app.models.brief import Brief
from app.models.weekly_report import WeeklyReport

X_API_URL = "https://api.twitter.com/2/tweets"
TWEET_MAX = 280


# ---------- composer ----------

def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _compose_weekly_tweet(
    report: WeeklyReport,
    top: PainPoint | None,
    *,
    locale: str = "en",
) -> str:
    base = settings.public_base_url.rstrip("/") or "https://demandradar.example.com"
    link = f"{base}/sample"
    if locale == "zh":
        if top is None:
            body = (
                f"📡 DemandRadar 周报 #{report.issue_no} 已发布\n"
                f"9+ 公开数据源 · Top 20 高付费意愿痛点\n{link}"
            )
            return _truncate(body, TWEET_MAX)
        score = (
            f"score {top.total_score:.0f}" if top.total_score is not None else "go"
        )
        head = f"📡 DemandRadar #{report.issue_no} · 本周 #1 痛点"
        pain = top.pain or "新需求"
        target = top.target_user or ""
        target_part = f"\n目标：{target}" if target else ""
        base_block = f"{head}\n「{pain}」 · {score}{target_part}\n详情：{link}"
        if len(base_block) <= TWEET_MAX:
            return base_block
        pain_budget = TWEET_MAX - len(base_block) + len(pain)
        return f"{head}\n「{_truncate(pain, max(20, pain_budget))}」 · {score}{target_part}\n详情：{link}"

    # English (default) — broadcast on the global X account.
    if top is None:
        body = (
            f"📡 DemandRadar weekly #{report.issue_no} is out\n"
            f"9+ public sources · Top 20 high-WTP pain points for indie hackers\n{link}"
        )
        return _truncate(body, TWEET_MAX)
    score = (
        f"score {top.total_score:.0f}" if top.total_score is not None else "go"
    )
    head = f"📡 DemandRadar #{report.issue_no} · this week's #1 pain"
    pain = top.pain or "new demand"
    target = top.target_user or ""
    target_part = f"\nTarget: {target}" if target else ""
    base_block = f"{head}\n\"{pain}\" · {score}{target_part}\nMore: {link}"
    if len(base_block) <= TWEET_MAX:
        return base_block
    pain_budget = TWEET_MAX - len(base_block) + len(pain)
    return f"{head}\n\"{_truncate(pain, max(20, pain_budget))}\" · {score}{target_part}\nMore: {link}"


# ---------- queue ----------

def enqueue_weekly_post(db: Session, report: WeeklyReport) -> SocialPost:
    """Create a queued tweet for the given weekly report (idempotent per
    weekly_report_id)."""
    existing = db.scalar(
        select(SocialPost)
        .where(SocialPost.platform == "x")
        .where(SocialPost.weekly_report_id == report.id)
    )
    if existing is not None:
        return existing

    top: PainPoint | None = None
    if report.pain_point_ids:
        top_id = report.pain_point_ids[0]
        top = db.get(PainPoint, top_id)

    body = _compose_weekly_tweet(report, top)
    row = SocialPost(
        platform="x",
        status="queued" if settings.twitter_enabled else "manual",
        kind="weekly",
        weekly_report_id=report.id,
        pain_point_id=top.id if top else None,
        title=f"weekly #{report.issue_no}",
        body=body,
        url=f"{settings.public_base_url.rstrip('/')}/sample",
    )
    db.add(row)
    db.flush()
    return row


def _compose_brief_tweet(
    brief: Brief, pp: PainPoint | None, *, locale: str = "en"
) -> str:
    base = settings.public_base_url.rstrip("/") or "https://demandradar.example.com"
    link = f"{base}/briefs/{brief.id}"
    score = (
        f"score {pp.total_score:.0f}"
        if (pp and pp.total_score is not None)
        else "go"
    )
    if locale == "zh":
        title = brief.title or (pp.pain if pp else "新项目书")
        head = f"🛠 DemandRadar 新项目书 · {score}"
        body = f"{head}\n「{title}」\n13 段构建路径：{link}"
        if len(body) <= TWEET_MAX:
            return body
        budget = TWEET_MAX - len(body) + len(title)
        title = _truncate(title, max(20, budget))
        return f"{head}\n「{title}」\n13 段构建路径：{link}"
    title = brief.title or (pp.pain if pp else "new brief")
    head = f"🛠 DemandRadar new brief · {score}"
    body = f'{head}\n"{title}"\n13-section build path: {link}'
    if len(body) <= TWEET_MAX:
        return body
    budget = TWEET_MAX - len(body) + len(title)
    title = _truncate(title, max(20, budget))
    return f'{head}\n"{title}"\n13-section build path: {link}'


def enqueue_brief_post(
    db: Session, brief: Brief, *, min_score: float | None = None
) -> SocialPost | None:
    """Queue a tweet for `brief` if its painpoint scores >= `min_score`.

    Idempotent per brief_id. Returns the SocialPost row on enqueue, None when
    skipped (low score, missing painpoint, or already queued)."""
    if min_score is None:
        min_score = float(settings.auto_tweet_min_score)

    pp = db.get(PainPoint, brief.pain_point_id)
    if pp is None:
        return None
    if pp.total_score is None or pp.total_score < min_score:
        return None

    existing = db.scalar(
        select(SocialPost)
        .where(SocialPost.platform == "x")
        .where(SocialPost.brief_id == brief.id)
    )
    if existing is not None:
        return existing

    body = _compose_brief_tweet(brief, pp)
    row = SocialPost(
        platform="x",
        status="queued" if settings.twitter_enabled else "manual",
        kind="brief",
        brief_id=brief.id,
        pain_point_id=pp.id,
        title=brief.title,
        body=body,
        url=f"{settings.public_base_url.rstrip('/')}/briefs/{brief.id}",
    )
    db.add(row)
    db.flush()
    return row


# ---------- poster ----------

@dataclass
class PostStats:
    posted: int = 0
    failed: int = 0
    skipped: int = 0


def _post_one(post: SocialPost) -> tuple[bool, str | None, str | None]:
    """Send a single tweet. Returns (ok, external_id, error)."""
    if not settings.twitter_enabled:
        return False, None, "twitter disabled"
    if not settings.twitter_access_token:
        return False, None, "TWITTER_ACCESS_TOKEN missing"
    headers = {
        "Authorization": f"Bearer {settings.twitter_access_token}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                X_API_URL, headers=headers, content=json.dumps({"text": post.body})
            )
        if r.status_code >= 300:
            return False, None, f"HTTP {r.status_code}: {r.text[:200]}"
        data: dict[str, Any] = r.json()
        tweet_id = (data.get("data") or {}).get("id")
        return True, tweet_id, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def post_pending(db: Session, *, limit: int = 10) -> PostStats:
    """Drain queued posts. Skips silently when TWITTER_ENABLED=false."""
    stats = PostStats()
    if not settings.twitter_enabled:
        return stats

    rows: list[SocialPost] = list(
        db.execute(
            select(SocialPost)
            .where(SocialPost.platform == "x")
            .where(SocialPost.status == "queued")
            .order_by(desc(SocialPost.id))
            .limit(limit)
        ).scalars()
    )
    for row in rows:
        ok, ext_id, err = _post_one(row)
        if ok:
            row.status = "posted"
            row.external_id = ext_id
            row.posted_at = datetime.now(tz=timezone.utc)
            stats.posted += 1
        else:
            row.status = "failed"
            row.error = (err or "")[:500]
            stats.failed += 1
            logger.warning("twitter post failed: id={} err={}", row.id, err)
    db.commit()
    return stats


__all__ = [
    "PostStats",
    "enqueue_brief_post",
    "enqueue_weekly_post",
    "post_pending",
]
