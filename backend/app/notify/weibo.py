"""Weibo (微博) auto-poster — Chinese-market mirror of `app.notify.twitter`.

Strategy mirrors the X module:
- After each weekly report we enqueue one Weibo post (zh-CN) for the #1
  painpoint as a `social_posts(platform='weibo', kind='weekly')` row.
- High-score briefs (score >= AUTO_TWEET_MIN_SCORE) get a `kind='brief'` row.
- A separate `post_pending` worker drains queued rows by calling Weibo
  Open API v2 `POST /2/statuses/share.json` with the configured
  WEIBO_ACCESS_TOKEN.

When `WEIBO_ENABLED=false` posts are still composed and stored with
`status='manual'` so the admin can copy/paste them. This means the China
side of the launch never hard-blocks on getting a Weibo dev account.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.brief import Brief
from app.models.pain_point import PainPoint
from app.models.social_post import SocialPost
from app.models.weekly_report import WeeklyReport

WEIBO_API_URL = "https://api.weibo.com/2/statuses/share.json"
WEIBO_MAX = 140  # Weibo counts 1 char per CJK glyph + 1 for ASCII; 140 is safe.


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _compose_weekly(report: WeeklyReport, top: PainPoint | None) -> str:
    base = settings.public_base_url.rstrip("/") or "https://demandradar.example.com"
    link = f"{base}/sample"
    if top is None:
        body = (
            f"📡 DemandRadar 周报 #{report.issue_no} 已发布\n"
            f"9+ 公开数据源 · Top 20 高付费意愿痛点\n{link}"
        )
        return _truncate(body, WEIBO_MAX)
    score = (
        f"score {top.total_score:.0f}" if top.total_score is not None else "go"
    )
    head = f"📡 DemandRadar #{report.issue_no} · 本周 #1 痛点"
    pain = top.pain or "新需求"
    target_part = f"\n目标：{top.target_user}" if top.target_user else ""
    body = f"{head}\n「{pain}」 · {score}{target_part}\n详情：{link}"
    if len(body) <= WEIBO_MAX:
        return body
    pain_budget = WEIBO_MAX - len(body) + len(pain)
    return (
        f"{head}\n「{_truncate(pain, max(20, pain_budget))}」 · {score}"
        f"{target_part}\n详情：{link}"
    )


def _compose_brief(brief: Brief, pp: PainPoint | None) -> str:
    base = settings.public_base_url.rstrip("/") or "https://demandradar.example.com"
    link = f"{base}/briefs/{brief.id}"
    score = (
        f"score {pp.total_score:.0f}"
        if (pp and pp.total_score is not None)
        else "go"
    )
    title = brief.title or (pp.pain if pp else "新项目书")
    head = f"🛠 DemandRadar 新项目书 · {score}"
    body = f"{head}\n「{title}」\n13 段开工路径：{link}"
    if len(body) <= WEIBO_MAX:
        return body
    budget = WEIBO_MAX - len(body) + len(title)
    return (
        f"{head}\n「{_truncate(title, max(20, budget))}」\n13 段开工路径：{link}"
    )


# ---------- queue ----------


def enqueue_weekly_post(db: Session, report: WeeklyReport) -> SocialPost:
    """Idempotent per (platform='weibo', weekly_report_id)."""
    existing = db.scalar(
        select(SocialPost)
        .where(SocialPost.platform == "weibo")
        .where(SocialPost.weekly_report_id == report.id)
    )
    if existing is not None:
        return existing

    top: PainPoint | None = None
    if report.pain_point_ids:
        top = db.get(PainPoint, report.pain_point_ids[0])

    body = _compose_weekly(report, top)
    row = SocialPost(
        platform="weibo",
        status="queued" if settings.weibo_enabled else "manual",
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


def enqueue_brief_post(
    db: Session, brief: Brief, *, min_score: float | None = None
) -> SocialPost | None:
    """Idempotent per (platform='weibo', brief_id). Skips low-scored briefs."""
    if min_score is None:
        min_score = float(settings.auto_tweet_min_score)

    pp = db.get(PainPoint, brief.pain_point_id) if brief.pain_point_id else None
    if pp is None or pp.total_score is None or pp.total_score < min_score:
        return None

    existing = db.scalar(
        select(SocialPost)
        .where(SocialPost.platform == "weibo")
        .where(SocialPost.brief_id == brief.id)
    )
    if existing is not None:
        return existing

    body = _compose_brief(brief, pp)
    row = SocialPost(
        platform="weibo",
        status="queued" if settings.weibo_enabled else "manual",
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
    """Send a single Weibo. Returns (ok, external_id, error)."""
    if not settings.weibo_enabled:
        return False, None, "weibo disabled"
    if not settings.weibo_access_token:
        return False, None, "WEIBO_ACCESS_TOKEN missing"
    payload: dict[str, Any] = {
        "access_token": settings.weibo_access_token,
        "status": post.body,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(WEIBO_API_URL, data=payload)
        if r.status_code >= 300:
            return False, None, f"HTTP {r.status_code}: {r.text[:200]}"
        data = r.json()
        return True, str(data.get("id") or data.get("idstr") or ""), None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def post_pending(db: Session, *, limit: int = 10) -> PostStats:
    """Drain queued Weibo posts. Skips silently when WEIBO_ENABLED=false."""
    stats = PostStats()
    if not settings.weibo_enabled:
        return stats

    rows: list[SocialPost] = list(
        db.execute(
            select(SocialPost)
            .where(SocialPost.platform == "weibo")
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
            logger.warning("weibo post failed: id={} err={}", row.id, err)
    db.commit()
    return stats


__all__ = [
    "PostStats",
    "enqueue_brief_post",
    "enqueue_weekly_post",
    "post_pending",
]
