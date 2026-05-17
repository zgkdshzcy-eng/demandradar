"""ProductHunt candidate generator.

PH disallows fully automated launches, so we never POST anywhere — we just
prepare the copy (title + tagline + comment) and store it as a `social_posts`
row with `status='manual'`. The admin dashboard renders these as a
copy-paste-ready cheat sheet.

Triggered manually by the admin via CLI / endpoint when a Brief crosses the
publish threshold (total_score >= 80).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.brief import Brief
from app.models.pain_point import PainPoint
from app.models.social_post import SocialPost

PH_TITLE_MAX = 60
PH_TAGLINE_MAX = 80


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _compose(brief: Brief, pp: PainPoint) -> tuple[str, str]:
    base = settings.public_base_url.rstrip("/") or "https://demandradar.example.com"
    title = _truncate(brief.title or pp.pain or "DemandRadar Brief", PH_TITLE_MAX)
    tagline = _truncate(
        f"{pp.target_user or 'indie devs'} · 高付费意愿痛点 + 13 段项目书"
        if pp.target_user
        else "高付费意愿痛点 + 13 段项目书",
        PH_TAGLINE_MAX,
    )
    body = (
        f"## {title}\n\n"
        f"**Tagline:** {tagline}\n\n"
        f"**First-comment template:**\n\n"
        f"Hi PH 👋 — sharing one of this week's top demand-radar finds:\n\n"
        f"- 🎯 Target user: {pp.target_user or 'indie developers'}\n"
        f"- 💸 Score: {(pp.total_score or 0):.0f}/100\n"
        f"- 📑 Brief (13 sections, evidence + monetization): {base}/briefs/{brief.id}\n"
        f"- 📡 Live radar: {base}/radar\n\n"
        f"Built solo. AMA on the brief structure or the data sources!\n"
    )
    return title, body


def enqueue_for_brief(db: Session, brief: Brief) -> SocialPost | None:
    """Create one PH candidate row per brief; idempotent on brief_id."""
    existing = db.scalar(
        select(SocialPost)
        .where(SocialPost.platform == "producthunt")
        .where(SocialPost.brief_id == brief.id)
    )
    if existing is not None:
        return existing

    pp = db.get(PainPoint, brief.pain_point_id) if brief.pain_point_id else None
    if pp is None:
        return None
    title, body = _compose(brief, pp)
    base = settings.public_base_url.rstrip("/")
    row = SocialPost(
        platform="producthunt",
        status="manual",  # PH never auto-posts
        kind="brief",
        brief_id=brief.id,
        pain_point_id=pp.id,
        title=title,
        body=body,
        url=f"{base}/briefs/{brief.id}" if base else None,
    )
    db.add(row)
    db.flush()
    return row


def list_candidates(db: Session, *, limit: int = 20) -> list[SocialPost]:
    """For admin dashboard — most recent candidates first."""
    return list(
        db.execute(
            select(SocialPost)
            .where(SocialPost.platform == "producthunt")
            .order_by(SocialPost.id.desc())
            .limit(limit)
        ).scalars()
    )


__all__ = ["enqueue_for_brief", "list_candidates"]
